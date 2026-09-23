#!/usr/bin/env python3
"""Train and evaluate the Cali-Tree hierarchy on ImagenHub, with evidence-based referral.

Dry-run is the default and makes no gateway calls: it reports the expected judge/optimizer
call counts and the optimizer completion-token budget from each node's dry-run meta. Live
execution requires an explicit judge/optimizer ``--model`` and a routing ``--embedding-model``;
the persisted tree carries both the editor-reliability ``selective_policy`` and the new
``evidence_referral_policy`` fitted on training labels only.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

from vejudge import config
from vejudge.checkpoint import CheckpointStore
from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.schemas import GraphIn, to_graph_spec
from vejudge.logging.exp_logger import make_exp_run

DEFAULT_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "examples"
    / "calitree_imagenhub_evidence.json"
)


def _load_graph(
    workflow_path: Path,
    *,
    model: str,
    embedding_model: str,
    engine_kind: str,
    max_tokens: int,
    concurrency: int,
    timeout: int,
    health_check: bool,
    pilot: bool = False,
    pilot_train_ratio: float = 0.05,
    pilot_test_ratio: float = 0.02,
    pilot_group_by_task: bool = False,
    test_group_offset: int = 0,
    specialization_mode: Optional[str] = None,
    leaf_grouping: Optional[str] = None,
    change_signal: Optional[str] = None,
    clustering_algorithm: Optional[str] = None,
    semantic_similarity_weight: Optional[float] = None,
    behavior_similarity_weight: Optional[float] = None,
    cross_generalization_weight: Optional[float] = None,
    calibration_mode: Optional[str] = None,
    selection_objective: Optional[str] = None,
    optimizer_model: Optional[str] = None,
    optimizer_engine_kind: Optional[str] = None,
) -> GraphIn:
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        raise ValueError(f"Workflow {workflow_path} has no graph object")
    for node in graph.get("nodes") or []:
        node_type = node.get("type")
        if node_type == "imagenhub_source" and pilot:
            # Keep every editor represented while limiting each task/editor group.
            node.setdefault("params", {})["repeat"] = "1"
        elif node_type == "dataset" and pilot:
            node.setdefault("params", {}).update({
                "train_sampling_ratio": pilot_train_ratio,
                "test_sampling_ratio": pilot_test_ratio,
                # The production benchmark keeps task groups intact. For a tiny pilot,
                # sampling whole eight-editor groups can yield a single train task and no
                # internal validation split, so sample cases while retaining task_uid for
                # CaliTree's own grouped fit/validation partition.
                "group_by_task": pilot_group_by_task,
                "test_group_offset": test_group_offset,
            })
        elif node_type == "lm_engine":
            # A separate optimizer model lets the judge and the TextGrad optimizer be
            # different models (e.g. Gemma judges while gpt-4.1-mini optimizes, since Gemma
            # returns empty on the large optimizer prompt). Only the node wired into the
            # optimizer_engine socket is overridden.
            is_optimizer = str(node.get("id") or "").lower().find("optimizer") >= 0
            node_model = (
                optimizer_model if (is_optimizer and optimizer_model) else model
            )
            node_engine_kind = (
                optimizer_engine_kind
                if (is_optimizer and optimizer_engine_kind)
                else engine_kind
            )
            node.setdefault("params", {}).update({
                "engine_kind": node_engine_kind,
                "model": node_model,
                "temperature": 0,
                "max_tokens": max_tokens,
                "concurrency": concurrency,
                "timeout": timeout,
                # A live GPT-4o run must not burn several five-minute retries on a
                # rate-limited primary when the mirror is already healthy. Dry runs never
                # instantiate an engine, so this adds no calls unless --live is present.
                "health_check": health_check,
            })
        elif node_type == "calitree_train":
            params = node.setdefault("params", {})
            params["embedding_model"] = embedding_model
            # CLI overrides let the same workflow serve the frozen v2 baseline and the
            # opt-in delta-tree without editing JSON.
            if specialization_mode:
                params["specialization_mode"] = specialization_mode
            if leaf_grouping:
                params["leaf_grouping"] = leaf_grouping
            if change_signal:
                params["change_signal"] = change_signal
            if clustering_algorithm:
                params["clustering_algorithm"] = clustering_algorithm
            if semantic_similarity_weight is not None:
                params["semantic_similarity_weight"] = semantic_similarity_weight
            if behavior_similarity_weight is not None:
                params["behavior_similarity_weight"] = behavior_similarity_weight
            if cross_generalization_weight is not None:
                params["cross_generalization_weight"] = cross_generalization_weight
            if pilot:
                # Exercise the whole optimize/merge/optimize path with bounded spend.
                # Baselines remain enabled so the pilot also validates metric comparison.
                params.update({
                    "max_steps": 1,
                    "max_merge_attempts": 3,
                    "merge_validation_cap": 2,
                    "behavioral_probe_cap": 8,
                    "cross_generalization_cap": 2,
                    "run_baselines": True,
                    "run_conflict_resolver": False,
                })
        elif node_type == "rubric_lite_fit":
            params = node.setdefault("params", {})
            if calibration_mode:
                params["calibration_mode"] = calibration_mode
            if selection_objective:
                params["selection_objective"] = selection_objective
        elif node_type == "rubric_lite_train" and selection_objective:
            node.setdefault("params", {})["selection_objective"] = selection_objective
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
            }
            for node_id, node_result in result.node_results.items()
        },
    }


def _preflight(result: Any) -> dict[str, Any]:
    """Collect the dry-run node metas so expected calls/budget are visible before spend."""
    return {
        node_id: node_result.meta
        for node_id, node_result in result.node_results.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--pilot", action="store_true",
        help="Run a small end-to-end live-path validation before the benchmark.",
    )
    parser.add_argument(
        "--pilot-train-ratio", type=float, default=0.05,
        help="Fraction of the 232-case training split used by --pilot.",
    )
    parser.add_argument(
        "--pilot-test-ratio", type=float, default=0.02,
        help="Fraction of the 1200-case test split used by --pilot.",
    )
    parser.add_argument(
        "--pilot-group-by-task", action="store_true",
        help="Keep every editor output for each selected pilot task together.",
    )
    parser.add_argument(
        "--test-group-offset", type=int, default=0,
        help="Rotate grouped test tasks before sampling; useful for a disjoint holdout.",
    )
    parser.add_argument(
        "--model", default="gpt-4o",
        help="Main judge model; defaults to GPT-4o for optimize–merge–optimize runs.",
    )
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--engine-kind", default="gpt")
    parser.add_argument(
        "--optimizer-model", default="",
        help="Override only the optimizer_engine model (e.g. gpt-4.1-mini) so the judge and "
             "the TextGrad optimizer can differ; defaults to --model when unset.",
    )
    parser.add_argument(
        "--optimizer-engine-kind", default="",
        help="Engine family for the optimizer_engine node; defaults to --engine-kind.",
    )
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--timeout", type=int, default=90,
        help="Per-request timeout in seconds; lower bounds keep a stalled gateway from blocking a checkpoint resume.",
    )
    parser.add_argument(
        "--specialization-mode", choices=["replace", "additive"], default=None,
        help="additive = the delta-tree (accumulate validated deltas into the root)",
    )
    parser.add_argument(
        "--leaf-grouping",
        choices=["task", "failure_mode", "residual_context", "per_case"],
        default=None,
    )
    parser.add_argument(
        "--change-signal", choices=["off", "all"], default=None,
        help="all = attach the localized source→edited change map to every judge call",
    )
    parser.add_argument(
        "--clustering-algorithm",
        choices=["semantic_complete_link", "behavioral_complete_link"],
        default=None,
        help="behavioral_complete_link combines semantic similarity, error behavior, and cross-leaf transfer.",
    )
    parser.add_argument("--semantic-similarity-weight", type=float, default=None)
    parser.add_argument("--behavior-similarity-weight", type=float, default=None)
    parser.add_argument("--cross-generalization-weight", type=float, default=None)
    parser.add_argument(
        "--calibration-mode", choices=["min_scalar", "two_gate"], default=None,
        help="two_gate = presence (change_evidence) + completeness (specification_fidelity) cutpoints",
    )
    parser.add_argument(
        "--selection-objective", choices=["macro_f1", "accuracy_guarded_partial"], default=None,
    )
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
    if args.live and not args.embedding_model.strip():
        parser.error("--live requires an explicit --embedding-model for routing")
    if (
        args.max_tokens < 1
        or args.concurrency < 1
        or args.timeout < 1
        or args.test_group_offset < 0
    ):
        parser.error(
            "--max-tokens, --concurrency, and --timeout must be positive; "
            "--test-group-offset must be nonnegative"
        )
    if not 0 < args.pilot_train_ratio <= 1 or not 0 < args.pilot_test_ratio <= 1:
        parser.error("--pilot-train-ratio and --pilot-test-ratio must be in (0, 1]")

    manifest_path = config.IMAGENHUB_ROOT / "manifest.json"
    if not manifest_path.is_file():
        parser.error(
            f"ImagenHub manifest not found at {manifest_path}; "
            "run ./run/setup_imagenhub.sh first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    graph = _load_graph(
        args.workflow.resolve(),
        model=args.model.strip(),
        embedding_model=args.embedding_model.strip(),
        engine_kind=args.engine_kind,
        max_tokens=args.max_tokens,
        concurrency=args.concurrency,
        timeout=args.timeout,
        health_check=args.live,
        pilot=args.pilot,
        pilot_train_ratio=args.pilot_train_ratio,
        pilot_test_ratio=args.pilot_test_ratio,
        pilot_group_by_task=args.pilot_group_by_task,
        test_group_offset=args.test_group_offset,
        specialization_mode=args.specialization_mode,
        leaf_grouping=args.leaf_grouping,
        change_signal=args.change_signal,
        clustering_algorithm=args.clustering_algorithm,
        semantic_similarity_weight=args.semantic_similarity_weight,
        behavior_similarity_weight=args.behavior_similarity_weight,
        cross_generalization_weight=args.cross_generalization_weight,
        calibration_mode=args.calibration_mode,
        selection_objective=args.selection_objective,
        optimizer_model=args.optimizer_model.strip() or None,
        optimizer_engine_kind=args.optimizer_engine_kind.strip() or None,
    )
    run_id = args.run_id or (
        time.strftime("%y%m%d-%H:%M:%S") + "-imagenhub-calitree-evidence"
    )
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
        "experiment": "imagenhub_calitree_evidence",
        "dry_run": not args.live,
        "allow_live": args.live,
        "pilot": args.pilot,
        "pilot_train_ratio": args.pilot_train_ratio,
        "pilot_test_ratio": args.pilot_test_ratio,
        "pilot_group_by_task": args.pilot_group_by_task,
        "test_group_offset": args.test_group_offset,
        "model": args.model.strip() or None,
        "embedding_model": args.embedding_model.strip() or None,
        "engine_kind": args.engine_kind,
        "clustering_algorithm": args.clustering_algorithm,
        "semantic_similarity_weight": args.semantic_similarity_weight,
        "behavior_similarity_weight": args.behavior_similarity_weight,
        "cross_generalization_weight": args.cross_generalization_weight,
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "concurrency": args.concurrency,
        "timeout": args.timeout,
        "checkpoint_sources": [str(p.resolve()) for p in args.checkpoint_from],
        "seeded_entries": seeded,
        "workflow": str(args.workflow.resolve()),
        "dataset_root": str(config.IMAGENHUB_ROOT),
        "dataset_manifest": manifest,
    })
    try:
        preflight_result = GraphExecutionEngine(
            to_graph_spec(graph),
            run=run,
            checkpoint=checkpoint,
            dry_run=True,
            allow_live=False,
        ).execute()
        preflight = _preflight(preflight_result)
        run.write_json("preflight.json", preflight)
        if args.live:
            result = GraphExecutionEngine(
                to_graph_spec(graph),
                run=run,
                checkpoint=checkpoint,
                dry_run=False,
                allow_live=True,
            ).execute()
        else:
            result = preflight_result
        run.write_json("graph_result.json", _serializable_results(result))
    finally:
        run.close()

    print(f"run_dir={run.run_dir}")
    print(f"status={result.status}")
    print("preflight=" + json.dumps(preflight, sort_keys=True))
    for node_id in ("imagenhub", "dataset", "train", "route", "evaluate"):
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
