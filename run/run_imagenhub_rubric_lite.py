#!/usr/bin/env python3
"""Run the frozen Rubric-Lite v4 model on all ImagenHub held-out cases.

Dry-run is the default. Live execution requires an explicit model. Compatible prior
checkpoints can seed a fresh run; CaliTree judge keys are normalized to the workflow's
``judge`` node, while the prompt hash inside each key prevents cross-prompt reuse.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from vejudge import config
from vejudge.checkpoint import CheckpointStore
from vejudge.interface.node_calibration.calitree_nodes import _hash
from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.schemas import GraphIn, to_graph_spec
from vejudge.logging.exp_logger import make_exp_run

DEFAULT_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "examples"
    / "rubric_lite_imagenhub_full_1200.json"
)


def _load_graph(
    workflow_path: Path,
    *,
    model: str,
    engine_kind: str,
    max_tokens: int,
    concurrency: int,
) -> GraphIn:
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        raise ValueError(f"Workflow {workflow_path} has no graph object")
    for node in graph.get("nodes") or []:
        if node.get("type") == "lm_engine":
            node.setdefault("params", {}).update({
                "engine_kind": engine_kind,
                "model": model,
                "temperature": 0,
                "max_tokens": max_tokens,
                "concurrency": concurrency,
                "health_check": False,
            })
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


def _checkpoint_path(source: Path) -> Path:
    path = source.resolve()
    return path / "judge_results.jsonl" if path.is_dir() else path


def _validate_source_config(
    source: Path,
    *,
    model: str,
    engine_kind: str,
    max_tokens: int,
) -> None:
    run_dir = source.resolve() if source.is_dir() else source.resolve().parent
    graph_path = run_dir / "workflow_graph.json"
    if not graph_path.is_file():
        return
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    engines = [
        node.get("params") or {}
        for node in graph.get("nodes") or []
        if node.get("type") == "lm_engine"
    ]
    judge = next((row for row in engines if row.get("model")), None)
    if not judge:
        return
    observed = {
        "model": str(judge.get("model") or ""),
        "engine_kind": str(judge.get("engine_kind") or "gpt"),
        "max_tokens": int(judge.get("max_tokens") or 0),
        "temperature": float(judge.get("temperature") or 0),
    }
    expected = {
        "model": model,
        "engine_kind": engine_kind,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    if observed != expected:
        raise ValueError(
            f"Incompatible checkpoint source {source}: "
            f"observed={observed}, expected={expected}"
        )


def _seed_checkpoints(
    checkpoint: CheckpointStore,
    sources: list[Path],
    *,
    model: str,
    engine_kind: str,
    max_tokens: int,
) -> dict[str, int]:
    source_entries = 0
    normalized_entries = 0
    for source in sources:
        _validate_source_config(
            source,
            model=model,
            engine_kind=engine_kind,
            max_tokens=max_tokens,
        )
        path = _checkpoint_path(source)
        if not path.is_file():
            raise ValueError(f"Checkpoint source not found: {path}")
        for key, value in CheckpointStore(path).items():
            checkpoint.put(key, value)
            source_entries += 1
            marker = "::calitree::judge::"
            if marker in key:
                normalized = "judge" + marker + key.split(marker, 1)[1]
                checkpoint.put(normalized, value)
                normalized_entries += 1
    return {
        "source_entries": source_entries,
        "normalized_entries": normalized_entries,
        "unique_seeded_entries": len(checkpoint),
    }


def _preflight(
    result: Any,
    checkpoint: CheckpointStore,
) -> dict[str, Any]:
    samples = result.node_results["dataset"].outputs["samples"]
    tree = result.node_results["frozen_rubric"].outputs["prompt_tree"]
    root_id = tree["roots"][0]
    prompt = str(tree["nodes"][root_id]["prompt"])
    expected_keys = {
        item_id: (
            f"judge::calitree::judge::"
            f"{_hash(prompt, sample.get('item_id'))}"
        )
        for item_id, sample in samples.items()
    }
    hits = sorted(
        item_id
        for item_id, key in expected_keys.items()
        if checkpoint.has(key)
    )
    missing = sorted(set(expected_keys) - set(hits))
    task_uids = {
        str(samples[item_id].get("task_uid") or item_id.split("::", 1)[0])
        for item_id in samples
    }
    return {
        "n_cases": len(samples),
        "n_tasks": len(task_uids),
        "checkpoint_hits": len(hits),
        "expected_live_calls": len(missing),
        "missing_item_ids": missing,
        "prompt_hash": _hash(prompt),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--engine-kind", default="gpt")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--checkpoint-from",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.live and not args.model.strip():
        parser.error("--live requires an explicit --model")
    if args.max_tokens < 1 or args.concurrency < 1:
        parser.error("--max-tokens and --concurrency must be positive")

    manifest_path = config.IMAGENHUB_ROOT / "manifest.json"
    if not manifest_path.is_file():
        parser.error(
            f"ImagenHub manifest not found at {manifest_path}; "
            "run ./run/setup_imagenhub.sh first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("tasks") or 0) != 179:
        parser.error(
            f"Expected the complete 179-task dataset, found "
            f"{manifest.get('tasks')!r}"
        )

    graph = _load_graph(
        args.workflow.resolve(),
        model=args.model.strip(),
        engine_kind=args.engine_kind,
        max_tokens=args.max_tokens,
        concurrency=args.concurrency,
    )
    run_id = args.run_id or (
        time.strftime("%y%m%d-%H:%M:%S")
        + "-imagenhub-rubric-lite-v4-full1200"
    )
    run = make_exp_run(run_id=run_id)
    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")
    try:
        seed_stats = _seed_checkpoints(
            checkpoint,
            list(args.checkpoint_from),
            model=args.model.strip(),
            engine_kind=args.engine_kind,
            max_tokens=args.max_tokens,
        )
    except ValueError as exc:
        parser.error(str(exc))

    run.save_config({
        "experiment": "imagenhub_rubric_lite_v4_full1200",
        "dry_run": not args.live,
        "allow_live": args.live,
        "model": args.model.strip() or None,
        "engine_kind": args.engine_kind,
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "concurrency": args.concurrency,
        "checkpoint_sources": [
            str(path.resolve()) for path in args.checkpoint_from
        ],
        "seed_stats": seed_stats,
        "workflow": str(args.workflow.resolve()),
        "dataset_root": str(config.IMAGENHUB_ROOT),
        "dataset_manifest": manifest,
    })
    try:
        if args.live:
            preflight_result = GraphExecutionEngine(
                to_graph_spec(graph),
                run=run,
                checkpoint=checkpoint,
                dry_run=True,
                allow_live=False,
            ).execute()
            preflight = _preflight(preflight_result, checkpoint)
            run.write_json("preflight.json", preflight)
            result = GraphExecutionEngine(
                to_graph_spec(graph),
                run=run,
                checkpoint=checkpoint,
                dry_run=False,
                allow_live=True,
            ).execute()
        else:
            result = GraphExecutionEngine(
                to_graph_spec(graph),
                run=run,
                checkpoint=checkpoint,
                dry_run=True,
                allow_live=False,
            ).execute()
            preflight = _preflight(result, checkpoint)
            run.write_json("preflight.json", preflight)
        run.write_json("graph_result.json", _serializable_results(result))
    finally:
        run.close()

    print(f"run_dir={run.run_dir}")
    print(f"status={result.status}")
    print(f"preflight={json.dumps(preflight, sort_keys=True)}")
    for node_id in ("imagenhub", "dataset", "frozen_rubric", "judge", "evaluate"):
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
