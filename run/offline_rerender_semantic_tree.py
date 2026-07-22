#!/usr/bin/env python3
"""Re-fit a completed semantic-tree node from durable outputs/checkpoints.

This intentionally provides an engine that raises if invoked: a rerender is valid only
when the completed run already contains every rule-bank and critic-feature checkpoint.
It never mutates the source ``run_results.json``. With ``--register-interface-run`` it
creates a separate derived run directory that the interface Runs column can discover.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# Prefer this worktree even when its shared virtualenv has an editable install pointing at
# another checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vejudge.checkpoint import CheckpointStore
from vejudge.interface.node_calibration import cl_semantic_tree_node as semantic_module
from vejudge.interface.node_calibration.cl_semantic_tree_node import ClSemanticTreeNodeExecutor
from vejudge.interface.node_eval.cl_rule_eval_node import ClRuleEvalNodeExecutor
from vejudge.interface.server.registry import NodeRunContext
from vejudge.logging.exp_logger import make_exp_run


class _NoCallEngine:
    def generate(self, *args, **kwargs):
        raise RuntimeError("Offline semantic rerender attempted an unexpected LLM call")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--node-id", default="joint_tree")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--register-interface-run", action="store_true",
        help="create a separate derived interface run beside the source run",
    )
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    completed = json.loads((run_dir / "run_results.json").read_text())
    graph = json.loads((run_dir / "workflow_graph.json").read_text())
    results = completed["node_results"]
    node = next(entry for entry in graph["nodes"] if entry["id"] == args.node_id)
    incoming = [edge for edge in graph["edges"] if edge["target"] == args.node_id]
    inputs: dict[str, object] = {}
    for edge in incoming:
        value = results[edge["source"]]["outputs"][edge["source_socket"]]
        socket = edge["target_socket"]
        if socket == "calibration_results":
            inputs.setdefault(socket, []).append(value)
        else:
            inputs[socket] = value

    # ``run_results.json`` stringifies database dataclasses. The completed debate outputs
    # retain the exact raw human arrays, so rebuild the small label interface the fitter
    # needs without re-reading or re-aggregating the source databases.
    labels: dict[str, SimpleNamespace] = {}
    for calibration_source in inputs.get("calibration_results", []):
        for result in calibration_source.values():
            item_id = result.get("item_id")
            if not item_id:
                continue
            label = labels.setdefault(
                item_id, SimpleNamespace(aggregation="none", raw_scores={}),
            )
            for dimension, values in (result.get("human_scores") or {}).items():
                scores = values.get("scores") if isinstance(values, dict) else None
                if scores:
                    label.raw_scores[dimension] = [float(score) for score in scores]
    inputs["labels"] = labels

    semantic_module.require_live = lambda *args, **kwargs: None
    semantic_module.load_creds = lambda: None
    semantic_module.get_engine = lambda *args, **kwargs: _NoCallEngine()
    with tempfile.TemporaryDirectory(prefix="vejudge-semantic-rerender-") as temp_dir:
        run = make_exp_run(run_dir=Path(temp_dir))
        context = NodeRunContext(
            node_id=args.node_id,
            params=node.get("params") or {},
            inputs=inputs,
            run=run,
            checkpoint=CheckpointStore(run_dir / "judge_results.jsonl"),
            dry_run=False,
            allow_live=True,
        )
        result = ClSemanticTreeNodeExecutor().run(context)
        if result.status != "done":
            raise RuntimeError(result.error or "Semantic rerender failed")
        eval_context = NodeRunContext(
            node_id="rule_eval",
            params={},
            inputs={"judge_rule": result.outputs["judge_rule"]},
            run=run,
            checkpoint=CheckpointStore(Path(temp_dir) / "judge_results.jsonl"),
            dry_run=False,
            allow_live=False,
        )
        eval_result = ClRuleEvalNodeExecutor().run(eval_context)
        run.close()
    if eval_result.status != "done":
        raise RuntimeError(eval_result.error or "Rule comparison rerender failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.outputs["judge_rule"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if args.register_interface_run:
        now = datetime.now().astimezone()
        derived_run_id = now.strftime("%y%m%d-%H:%M:%S-semantic-first")
        derived_dir = run_dir.parent / f"{derived_run_id}-exps"
        derived_dir.mkdir(parents=False, exist_ok=False)

        source_config = json.loads((run_dir / "run_config.json").read_text())
        workflow_name = source_config.get("workflow_name") or "unnamed"
        derived_config = {
            **source_config,
            "workflow_name": f"{workflow_name} [semantic-first rerender]",
            "offline_rerender": True,
            "derived_from_run": run_dir.name.removesuffix("-exps"),
            "allow_live": False,
        }
        derived_results = json.loads(json.dumps(completed))
        derived_results["node_results"][args.node_id] = {
            "status": result.status,
            "error": result.error,
            "meta": result.meta,
            "outputs": result.outputs,
        }
        derived_results["node_results"]["rule_eval"] = {
            "status": eval_result.status,
            "error": eval_result.error,
            "meta": eval_result.meta,
            "outputs": eval_result.outputs,
        }
        status = {
            "run_id": derived_run_id,
            "status": "done",
            "error": None,
            "finished_at": now.isoformat(),
            "order": derived_results.get("order", []),
        }
        files = {
            "run_config.json": derived_config,
            "workflow_graph.json": graph,
            "run_results.json": derived_results,
            "run_status.json": status,
            "rule_eval_rule_eval.json": eval_result.outputs["comparison"],
            "semantic_first_rerender.json": result.outputs["judge_rule"],
        }
        for filename, payload in files.items():
            (derived_dir / filename).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
            )
        (derived_dir / "run.log").write_text(
            f"Offline semantic-first rerender derived from {run_dir.name}. No LLM calls.\n",
            encoding="utf-8",
        )
        (derived_dir / "llm-histories.log").write_text("", encoding="utf-8")
        print(derived_run_id)


if __name__ == "__main__":
    main()
