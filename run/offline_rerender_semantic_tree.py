#!/usr/bin/env python3
"""Re-fit a completed semantic-tree node from durable outputs/checkpoints.

This intentionally provides an engine that raises if invoked: a rerender is valid only
when the completed run already contains every rule-bank and critic-feature checkpoint.
It never mutates ``run_results.json``; the requested output is a separate comparison file.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Prefer this worktree even when its shared virtualenv has an editable install pointing at
# another checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vejudge.checkpoint import CheckpointStore
from vejudge.interface.node_calibration import cl_semantic_tree_node as semantic_module
from vejudge.interface.node_calibration.cl_semantic_tree_node import ClSemanticTreeNodeExecutor
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
        run.close()
    if result.status != "done":
        raise RuntimeError(result.error or "Semantic rerender failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.outputs["judge_rule"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
