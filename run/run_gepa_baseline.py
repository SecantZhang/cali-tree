#!/usr/bin/env python3
"""Evaluate the frozen GEPA-optimized global prompt against the ImagenHub dev slice.

The GEPA optimization itself runs offline in the isolated `.venv-gepa` (see
`run/gepa_baseline/optimize.py`); this script only evaluates its already-committed artifact
(`vejudge/core/calibration/artifacts/gepa_v1_imagenhub.json`) through the ordinary
`gepa_frozen -> calitree_judge -> calitree_eval` graph, exactly like the other baselines this
project reports (Initial rubric, Global TextGrad, Cali-Tree v2). Dry-run is the default and
makes zero gateway calls.
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
    / "calitree_imagenhub_gepa_baseline.json"
)


def _load_graph(
    workflow_path: Path, *, model: str, engine_kind: str, max_tokens: int, concurrency: int,
) -> GraphIn:
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        raise ValueError(f"Workflow {workflow_path} has no graph object")
    for node in graph.get("nodes") or []:
        if node.get("type") == "lm_engine":
            node.setdefault("params", {}).update({
                "engine_kind": engine_kind, "model": model, "temperature": 0,
                "max_tokens": max_tokens, "concurrency": concurrency, "health_check": False,
            })
    return GraphIn(**graph)


def _serializable_results(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "error": result.error,
        "order": result.order,
        "node_results": {
            node_id: {"status": nr.status, "error": nr.error, "meta": nr.meta}
            for node_id, nr in result.node_results.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--engine-kind", default="gpt")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--checkpoint-from", type=Path, action="append", default=[])
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.live and not args.model.strip():
        parser.error("--live requires an explicit --model")

    manifest_path = config.IMAGENHUB_ROOT / "manifest.json"
    if not manifest_path.is_file():
        parser.error(
            f"ImagenHub manifest not found at {manifest_path}; run ./run/setup_imagenhub.sh first"
        )

    graph = _load_graph(
        args.workflow.resolve(), model=args.model.strip(), engine_kind=args.engine_kind,
        max_tokens=args.max_tokens, concurrency=args.concurrency,
    )
    run_id = args.run_id or (time.strftime("%y%m%d-%H:%M:%S") + "-gepa-baseline")
    run = make_exp_run(run_id=run_id)
    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")
    seeded = 0
    for source in args.checkpoint_from:
        path = source.resolve()
        path = path / "judge_results.jsonl" if path.is_dir() else path
        if not path.is_file():
            parser.error(f"Checkpoint source not found: {path}")
        for key, value in CheckpointStore(path).items():
            checkpoint.put(key, value)
            seeded += 1

    run.save_config({
        "experiment": "gepa_baseline",
        "dry_run": not args.live, "allow_live": args.live,
        "model": args.model.strip() or None, "engine_kind": args.engine_kind,
        "max_tokens": args.max_tokens, "temperature": 0, "concurrency": args.concurrency,
        "checkpoint_sources": [str(p.resolve()) for p in args.checkpoint_from],
        "seeded_entries": seeded, "workflow": str(args.workflow.resolve()),
    })
    try:
        preflight_result = GraphExecutionEngine(
            to_graph_spec(graph), run=run, checkpoint=checkpoint,
            dry_run=True, allow_live=False,
        ).execute()
        run.write_json("preflight.json", _serializable_results(preflight_result))
        if args.live:
            result = GraphExecutionEngine(
                to_graph_spec(graph), run=run, checkpoint=checkpoint,
                dry_run=False, allow_live=True,
            ).execute()
        else:
            result = preflight_result
        run.write_json("graph_result.json", _serializable_results(result))
    finally:
        run.close()

    print(f"run_dir={run.run_dir}")
    print(f"status={result.status}")
    for node_id in ("imagenhub", "dataset", "gepa_frozen", "judge", "evaluate"):
        nr = result.node_results.get(node_id)
        if nr is not None:
            print(f"{node_id}: status={nr.status} meta={json.dumps(nr.meta, sort_keys=True)}")
    if result.error:
        print(f"error={result.error}")
    return 0 if result.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
