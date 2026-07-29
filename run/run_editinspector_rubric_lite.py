#!/usr/bin/env python3
"""Run the frozen Rubric-Lite v4 model on the local EditInspector slice.

The default is a no-call dry run. Live execution requires both ``--live`` and an
explicit ``--model``; it uses the same graph, checkpoint, history, and call gating as
the workflow UI.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from vejudge import config
from vejudge.checkpoint import CheckpointStore
from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.schemas import GraphIn, to_graph_spec
from vejudge.logging.exp_logger import make_exp_run

DEFAULT_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "examples"
    / "rubric_lite_editinspector_zero_shot.json"
)


def _load_graph(
    workflow_path: Path,
    *,
    model: str,
    engine_kind: str,
    max_tokens: int,
    concurrency: int,
    eligible_base_labels: list[str],
    partition: str,
    boundary_enabled: bool,
) -> GraphIn:
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        raise ValueError(f"Workflow {workflow_path} has no graph object")
    for node in graph.get("nodes") or []:
        if node.get("type") == "lm_engine":
            params = node.setdefault("params", {})
            params.update({
                "engine_kind": engine_kind,
                "model": model,
                "temperature": 0,
                "max_tokens": max_tokens,
                "concurrency": concurrency,
                "health_check": False,
            })
        elif node.get("type") == "rubric_lite_boundary":
            params = node.setdefault("params", {})
            params["eligible_base_labels"] = eligible_base_labels
            params["enabled"] = boundary_enabled
        elif node.get("type") == "editinspector_source":
            node.setdefault("params", {})["partition"] = partition
    return GraphIn(**graph)


def _serializable_results(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "error": result.error,
        "order": result.order,
        "node_results": {
            node_id: {
                "status": node_result.status,
                "error": node_result.error,
                "meta": node_result.meta,
                "outputs": node_result.outputs,
            }
            for node_id, node_result in result.node_results.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--engine-kind", default="gpt")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--eligible-base-labels",
        nargs="+",
        choices=("no", "partial", "yes"),
        default=["yes"],
    )
    parser.add_argument(
        "--partition",
        choices=(
            "all", "calibration", "development",
            "confirmation", "final",
        ),
        default="all",
    )
    parser.add_argument("--disable-boundary", action="store_true")
    parser.add_argument(
        "--checkpoint-from",
        type=Path,
        default=None,
        help="Seed a fresh run from a prior run directory or checkpoint JSONL",
    )
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.live and not args.model.strip():
        parser.error("--live requires an explicit --model")
    if args.max_tokens < 1 or args.concurrency < 1:
        parser.error("--max-tokens and --concurrency must be positive")

    manifest_path = config.EDITINSPECTOR_ROOT / "manifest.json"
    if not manifest_path.is_file():
        parser.error(
            f"EditInspector manifest not found at {manifest_path}; "
            "run ./run/setup_editinspector.sh first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    graph = _load_graph(
        args.workflow.resolve(),
        model=args.model.strip(),
        engine_kind=args.engine_kind,
        max_tokens=args.max_tokens,
        concurrency=args.concurrency,
        eligible_base_labels=list(args.eligible_base_labels),
        partition=args.partition,
        boundary_enabled=not args.disable_boundary,
    )
    run_id = args.run_id or (
        time.strftime("%y%m%d-%H:%M:%S")
        + "-editinspector-rubric-lite"
    )
    run = make_exp_run(run_id=run_id)
    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")
    seeded_checkpoint_entries = 0
    if args.checkpoint_from is not None:
        source_path = args.checkpoint_from.resolve()
        if source_path.is_dir():
            source_path = source_path / "judge_results.jsonl"
        if not source_path.is_file():
            parser.error(f"Checkpoint source not found: {source_path}")
        source_checkpoint = CheckpointStore(source_path)
        for key, value in source_checkpoint.items():
            checkpoint.put(key, value)
            seeded_checkpoint_entries += 1
    run.save_config({
        "experiment": "editinspector_rubric_lite_zero_shot",
        "dry_run": not args.live,
        "allow_live": args.live,
        "model": args.model.strip() or None,
        "engine_kind": args.engine_kind,
        "max_tokens": args.max_tokens,
        "concurrency": args.concurrency,
        "eligible_base_labels": list(args.eligible_base_labels),
        "partition": args.partition,
        "boundary_enabled": not args.disable_boundary,
        "checkpoint_from": (
            str(args.checkpoint_from.resolve())
            if args.checkpoint_from is not None
            else None
        ),
        "seeded_checkpoint_entries": seeded_checkpoint_entries,
        "workflow": str(args.workflow.resolve()),
        "dataset_root": str(config.EDITINSPECTOR_ROOT),
        "dataset_manifest": manifest,
    })
    try:
        result = GraphExecutionEngine(
            to_graph_spec(graph),
            run=run,
            checkpoint=checkpoint,
            dry_run=not args.live,
            allow_live=args.live,
        ).execute()
        payload = _serializable_results(result)
        run.write_json("graph_result.json", payload)
    finally:
        run.close()

    print(f"run_dir={run.run_dir}")
    print(f"status={result.status}")
    for node_id in ("editinspector", "dataset", "judge", "boundary", "evaluate"):
        node_result = result.node_results.get(node_id)
        if node_result is not None:
            print(
                f"{node_id}: status={node_result.status} "
                f"meta={json.dumps(node_result.meta, sort_keys=True)}"
            )
    if result.error:
        print(f"error={result.error}")
    return 0 if result.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
