"""Workflow node for the single-prompt Rubric-Lite calibration alternative."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ...core.calibration.rubric_lite import (
    RubricLiteLearner,
    apply_ordinal_thresholds,
    fit_ordinal_thresholds,
)
from ...lm_engine import require_live
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .calitree_nodes import (
    _CaliTreeRuntime,
    _calibration_split,
    _engine_from,
    _hash,
    _human_agreement_bucket,
    _metrics_with_human_agreement,
    _target,
)


PROMPT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "core"
    / "prompts"
    / "templates"
)
RUBRIC_VERSIONS = (
    "rubric_lite_v1",
    "rubric_lite_v2",
    "rubric_lite_v3",
    "rubric_lite_v4",
)


def _prompt(name: str, version: str) -> str:
    if version not in RUBRIC_VERSIONS:
        raise ValueError(f"Unknown Rubric-Lite version {version!r}")
    return (PROMPT_ROOT / version / name).read_text(encoding="utf-8").strip()


def _format_feedback(
    ids: list[str],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    results: dict[str, dict[str, Any]],
    *,
    rubric_version: str,
) -> str:
    template = _prompt("gradient_feedback.txt", rubric_version)
    return "\n\n".join(
        template.format(
            instruction=str(
                (samples[item_id].get("input") or {}).get("instruction") or ""
            ),
            prediction=str(results[item_id].get("label") or ""),
            target=targets[item_id],
            rationale=str(results[item_id].get("rationale") or ""),
        )
        for item_id in ids
    )


@register
class RubricLiteTrainNodeExecutor(NodeExecutor):
    node_type = "rubric_lite_train"
    category = "node_calibration"
    subcategory = "prompt"
    input_sockets = {
        "samples": "samples",
        "labels": "labels",
        "judge_engine": "engine_config",
        "optimizer_engine": "engine_config",
    }
    output_sockets = {
        "prompt_tree": "prompt_tree",
        "calitree_report": "calitree_report",
    }
    param_schema = {
        "rubric_version": {
            "type": "enum",
            "options": list(RUBRIC_VERSIONS),
            "default": "rubric_lite_v1",
        },
        "max_steps": {"type": "number", "default": 3, "min": 0, "max": 10},
        "feedback_cases_per_bucket": {
            "type": "number", "default": 8, "min": 1, "max": 50,
        },
        "max_validation_accuracy_drop": {
            "type": "number", "default": 0.01, "min": 0, "max": 0.2,
        },
        "ordinal_accuracy_tolerance": {
            "type": "number", "default": 0.01, "min": 0, "max": 0.2,
        },
        "ordinal_minimum_class_recall": {
            "type": "number", "default": 0.10, "min": 0, "max": 1,
        },
        "validation_fraction": {
            "type": "number", "default": 0.25, "min": 0.1, "max": 0.5,
        },
        "split_seed": {"type": "number", "default": 44, "min": 0},
        "agreement_filter": {
            "type": "enum",
            "options": ["all", "unanimous"],
            "default": "unanimous",
        },
        "run_initial_baseline": {"type": "bool", "default": True},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        labels = ctx.inputs.get("labels")
        judge_config = ctx.inputs.get("judge_engine")
        optimizer_config = ctx.inputs.get("optimizer_engine")
        if not all(
            value is not None
            for value in (samples, labels, judge_config, optimizer_config)
        ):
            return NodeRunResult(
                status="error",
                error=(
                    "Rubric-Lite Train requires samples, labels, judge_engine, "
                    "and optimizer_engine"
                ),
            )
        train_ids = sorted(
            item_id
            for item_id in set(samples) & set(labels)
            if samples[item_id].get("split") == "train"
            and _target(labels[item_id]) in {"no", "partial", "yes"}
        )
        test_ids = sorted(
            item_id
            for item_id in set(samples) & set(labels)
            if samples[item_id].get("split") == "test"
            and _target(labels[item_id]) in {"no", "partial", "yes"}
        )
        agreement_filter = str(
            ctx.params.get("agreement_filter") or "unanimous"
        )
        if agreement_filter not in {"all", "unanimous"}:
            return NodeRunResult(
                status="error",
                error="agreement_filter must be 'all' or 'unanimous'",
            )
        learning_ids = [
            item_id
            for item_id in train_ids
            if agreement_filter == "all"
            or _human_agreement_bucket(labels[item_id]) == "unanimous"
        ]
        fit_ids, validation_ids = _calibration_split(
            learning_ids,
            labels,
            validation_fraction=float(
                ctx.params.get("validation_fraction", 0.25)
            ),
            seed=int(ctx.params.get("split_seed", 44)),
        )
        max_steps = int(ctx.params.get("max_steps", 3))
        rubric_version = str(
            ctx.params.get("rubric_version") or "rubric_lite_v1"
        )
        if rubric_version not in RUBRIC_VERSIONS:
            return NodeRunResult(
                status="error",
                error=f"Unknown rubric_version {rubric_version!r}",
            )
        max_tokens = int(optimizer_config.get("max_tokens") or 4096)
        optimizer_budget = max_steps * max_tokens
        if ctx.dry_run:
            remaining_after_learning = (
                len(train_ids) - len(learning_ids) + len(test_ids)
            )
            candidate_calls = (max_steps + 1) * len(learning_ids)
            baseline_worst_case = (
                remaining_after_learning
                if bool(ctx.params.get("run_initial_baseline", True))
                and max_steps > 0
                else 0
            )
            return NodeRunResult(
                outputs={"prompt_tree": {}, "calitree_report": {}},
                meta={
                    "dry_run": True,
                    "architecture": "rubric_lite",
                    "n_train": len(train_ids),
                    "n_learning": len(learning_ids),
                    "n_fit": len(fit_ids),
                    "n_validation": len(validation_ids),
                    "n_test": len(test_ids),
                    "optimizer_completion_token_budget": optimizer_budget,
                    "estimated_calls": {
                        "judge_max": (
                            candidate_calls
                            + remaining_after_learning
                            + baseline_worst_case
                        ),
                        "judge_if_initial_selected": (
                            candidate_calls + remaining_after_learning
                        ),
                        "optimizer_max": max_steps,
                        "embedding": 0,
                        "critic": 0,
                    },
                },
            )
        if not learning_ids:
            return NodeRunResult(
                status="error",
                error=(
                    "Rubric-Lite found no training cases matching "
                    f"agreement_filter={agreement_filter!r}"
                ),
            )
        try:
            require_live(ctx.allow_live, context="Rubric-Lite training")
            judge_engine = _engine_from(judge_config, ctx)
            optimizer_engine = _engine_from(optimizer_config, ctx)
        except (ValueError, RuntimeError) as exc:
            return NodeRunResult(status="error", error=str(exc))
        runtime = _CaliTreeRuntime(
            ctx,
            judge_engine=judge_engine,
            optimizer_engine=optimizer_engine,
            embedding_model="",
            optimizer_budget=optimizer_budget,
            prompt_version=rubric_version,
            concurrency=int(judge_config.get("concurrency") or 1),
        )
        all_ids = train_ids + test_ids
        targets = {
            item_id: _target(labels[item_id]) for item_id in all_ids
        }
        initial_prompt = _prompt("initial_rubric.txt", rubric_version)
        learned = RubricLiteLearner(
            judge_many=runtime.judge_many,
            optimize=runtime.optimize,
            format_feedback=lambda ids, case_samples, case_targets, results: (
                _format_feedback(
                    ids,
                    case_samples,
                    case_targets,
                    results,
                    rubric_version=rubric_version,
                )
            ),
            max_steps=max_steps,
            feedback_cases_per_bucket=int(
                ctx.params.get("feedback_cases_per_bucket", 8)
            ),
            max_validation_accuracy_drop=float(
                ctx.params.get("max_validation_accuracy_drop", 0.01)
            ),
            progress=ctx.progress_cb,
        ).fit(
            initial_prompt=initial_prompt,
            samples=samples,
            targets=targets,
            fit_ids=fit_ids,
            validation_ids=validation_ids,
        )
        learned.report["version"] = rubric_version
        tree = learned.prompt_tree()
        tree["version"] = rubric_version.replace("_", "-")
        tree["prompt_version"] = rubric_version
        tree["rubric_version"] = rubric_version
        raw_selected_results = runtime.judge_many(
            learned.prompt,
            {item_id: samples[item_id] for item_id in all_ids},
        )
        selected_results = raw_selected_results
        ordinal_calibration: Optional[dict[str, Any]] = None
        if rubric_version in {"rubric_lite_v3", "rubric_lite_v4"}:
            accuracy_tolerance = float(
                ctx.params.get("ordinal_accuracy_tolerance", 0.01)
            )
            minimum_class_recall = float(
                ctx.params.get("ordinal_minimum_class_recall", 0.10)
            )
            fit_calibration = fit_ordinal_thresholds(
                results=raw_selected_results,
                targets=targets,
                samples=samples,
                ids=fit_ids,
                accuracy_tolerance=accuracy_tolerance,
                minimum_class_recall=minimum_class_recall,
            )
            validation_calibrated = apply_ordinal_thresholds(
                {
                    item_id: raw_selected_results[item_id]
                    for item_id in validation_ids
                },
                fit_calibration["thresholds"],
            )
            validation_metrics = _metrics_with_human_agreement(
                {
                    item_id: targets[item_id]
                    for item_id in validation_ids
                },
                {
                    item_id: str(result.get("label") or "")
                    for item_id, result in validation_calibrated.items()
                },
                samples,
                labels,
            )
            deployment_calibration = fit_ordinal_thresholds(
                results=raw_selected_results,
                targets=targets,
                samples=samples,
                ids=learning_ids,
                accuracy_tolerance=accuracy_tolerance,
                minimum_class_recall=minimum_class_recall,
            )
            selected_results = apply_ordinal_thresholds(
                raw_selected_results,
                deployment_calibration["thresholds"],
            )
            ordinal_calibration = {
                "version": "rubric-lite-ordinal-cutpoints-v1",
                "selection_split": "task_grouped_internal_validation",
                "feature": "minimum_visible_evidence_score",
                "uses_editor_identity": False,
                "uses_instruction_features": False,
                "fit": fit_calibration,
                "validation": validation_metrics,
                "deployment": deployment_calibration,
            }
            tree["ordinal_thresholds"] = deployment_calibration[
                "thresholds"
            ]
            tree["ordinal_calibration"] = ordinal_calibration
            root = tree["nodes"][tree["roots"][0]]
            root["ordinal_thresholds"] = deployment_calibration[
                "thresholds"
            ]
            root["validation_accuracy"] = float(
                validation_metrics.get("accuracy") or 0.0
            )
            root["components"] = {
                "criteria": [
                    "change evidence: 0..100",
                    "specification fidelity: 0..100",
                    "source preservation: 0..100",
                ],
                "priorities": [
                    "minimum visible-evidence score",
                    "training-fitted global ordinal cutpoints",
                ],
                "constraints": [
                    "one judge call",
                    "no editor/task/instruction calibration features",
                ],
            }
            tree["config"]["ordinal_accuracy_tolerance"] = (
                accuracy_tolerance
            )
            tree["config"]["ordinal_minimum_class_recall"] = (
                minimum_class_recall
            )
        tree["prediction_cache"] = {
            item_id: {
                "prompt_hash": _hash(
                    "calitree_prediction", learned.prompt
                ),
                "result": selected_results[item_id],
            }
            for item_id in all_ids
        }
        predictions = {
            item_id: selected_results[item_id]["label"]
            for item_id in all_ids
        }
        report: dict[str, Any] = {
            **learned.report,
            "n_train": len(train_ids),
            "n_learning": len(learning_ids),
            "n_fit": len(fit_ids),
            "n_validation": len(validation_ids),
            "n_test": len(test_ids),
            "agreement_filter": agreement_filter,
            "rubric_version": rubric_version,
            "optimizer_completion_token_budget": optimizer_budget,
            "usage": runtime.usage,
            "tree_stats": tree["stats"],
            "timeline": learned.report["trials"],
            "rubric_lite": {
                "train": _metrics_with_human_agreement(
                    {item_id: targets[item_id] for item_id in train_ids},
                    {item_id: predictions[item_id] for item_id in train_ids},
                    samples,
                    labels,
                ),
                "test": _metrics_with_human_agreement(
                    {item_id: targets[item_id] for item_id in test_ids},
                    {item_id: predictions[item_id] for item_id in test_ids},
                    samples,
                    labels,
                ),
            },
            "predictions": selected_results,
            "cases": {
                item_id: {
                    "item_id": item_id,
                    "instruction": str(
                        (samples[item_id].get("input") or {}).get(
                            "instruction"
                        ) or ""
                    ),
                    "source_image_path": str(
                        (samples[item_id].get("input") or {}).get(
                            "source_image_path"
                        ) or ""
                    ),
                    "edited_image_path": str(
                        (samples[item_id].get("output") or {}).get(
                            "edited_image_path"
                        ) or ""
                    ),
                    "editor": str(
                        samples[item_id].get("editor") or "unknown"
                    ),
                    "split": samples[item_id].get("split"),
                    "target_label": targets[item_id],
                }
                for item_id in all_ids
            },
        }
        if ordinal_calibration is not None:
            report["ordinal_calibration"] = ordinal_calibration
        if bool(ctx.params.get("run_initial_baseline", True)):
            initial_results = runtime.judge_many(
                initial_prompt,
                {item_id: samples[item_id] for item_id in all_ids},
            )
            initial_predictions = {
                item_id: initial_results[item_id]["label"]
                for item_id in all_ids
            }
            report["initial_baseline"] = {
                "train": _metrics_with_human_agreement(
                    {item_id: targets[item_id] for item_id in train_ids},
                    {
                        item_id: initial_predictions[item_id]
                        for item_id in train_ids
                    },
                    samples,
                    labels,
                ),
                "test": _metrics_with_human_agreement(
                    {item_id: targets[item_id] for item_id in test_ids},
                    {
                        item_id: initial_predictions[item_id]
                        for item_id in test_ids
                    },
                    samples,
                    labels,
                ),
            }
        ctx.run.write_json(f"rubric_lite_tree_{ctx.node_id}.json", tree)
        ctx.run.write_json(f"rubric_lite_{ctx.node_id}.json", report)
        return NodeRunResult(
            outputs={"prompt_tree": tree, "calitree_report": report},
            meta={
                "architecture": "rubric_lite",
                "n_train": len(train_ids),
                "n_fit": len(fit_ids),
                "n_validation": len(validation_ids),
                "n_test": len(test_ids),
                "usage": runtime.usage,
            },
        )


@register
class RubricLiteBoundaryNodeExecutor(NodeExecutor):
    """Conditionally ask one independent rubric to verify the partial boundary."""

    node_type = "rubric_lite_boundary"
    category = "node_calibration"
    subcategory = "prompt"
    input_sockets = {
        "samples": "samples",
        "judge_result": "judge_result",
        "judge_engine": "engine_config",
    }
    output_sockets = {"judge_result": "judge_result"}
    param_schema = {
        "verifier_version": {
            "type": "enum",
            "options": ["rubric_lite_v1"],
            "default": "rubric_lite_v1",
        },
        "minimum_ordinal_score": {
            "type": "number", "default": 50, "min": 0, "max": 100,
        },
        "apply_split": {
            "type": "enum",
            "options": ["all", "train", "test"],
            "default": "all",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        judge_result = ctx.inputs.get("judge_result")
        judge_config = ctx.inputs.get("judge_engine")
        if samples is None or judge_result is None or judge_config is None:
            return NodeRunResult(
                status="error",
                error=(
                    "Rubric-Lite Boundary requires samples, judge_result, "
                    "and judge_engine"
                ),
            )
        minimum_score = float(
            ctx.params.get("minimum_ordinal_score", 50)
        )
        apply_split = str(ctx.params.get("apply_split") or "all")
        if apply_split not in {"all", "train", "test"}:
            return NodeRunResult(
                status="error",
                error="apply_split must be 'all', 'train', or 'test'",
            )
        verifier_version = str(
            ctx.params.get("verifier_version") or "rubric_lite_v1"
        )
        if verifier_version != "rubric_lite_v1":
            return NodeRunResult(
                status="error",
                error=f"Unknown boundary verifier {verifier_version!r}",
            )

        def row_for(item_id: str) -> dict[str, Any]:
            value = judge_result.get(item_id) or {}
            row = value.get("calitree") if isinstance(value, dict) else None
            return row if isinstance(row, dict) else {}

        eligible_split_ids = [
            item_id
            for item_id in sorted(set(samples) & set(judge_result))
            if apply_split == "all"
            or str(samples[item_id].get("split") or "") == apply_split
        ]
        candidate_ids = [
            item_id
            for item_id in eligible_split_ids
            if isinstance(row_for(item_id).get("ordinal_score"), (int, float))
            and float(row_for(item_id)["ordinal_score"]) >= minimum_score
        ]
        if ctx.dry_run:
            return NodeRunResult(
                outputs={"judge_result": judge_result},
                meta={
                    "dry_run": True,
                    "architecture": "rubric_lite_boundary",
                    "n_items": len(judge_result),
                    "n_split_eligible": len(eligible_split_ids),
                    "n_score_eligible": len(candidate_ids),
                    "estimated_calls": len(candidate_ids),
                    "estimated_calls_max": len(eligible_split_ids),
                },
            )
        try:
            require_live(
                ctx.allow_live,
                context="Rubric-Lite partial boundary verification",
            )
            judge_engine = _engine_from(judge_config, ctx)
        except (ValueError, RuntimeError) as exc:
            return NodeRunResult(status="error", error=str(exc))
        runtime = _CaliTreeRuntime(
            ctx,
            judge_engine=judge_engine,
            optimizer_engine=judge_engine,
            embedding_model="",
            optimizer_budget=0,
            prompt_version=verifier_version,
            concurrency=int(judge_config.get("concurrency") or 1),
        )
        verifier_results = runtime.judge_many(
            _prompt("initial_rubric.txt", verifier_version),
            {item_id: samples[item_id] for item_id in candidate_ids},
        )
        output: dict[str, Any] = {}
        overrides = 0
        for item_id, value in judge_result.items():
            value_copy = dict(value) if isinstance(value, dict) else {}
            base = row_for(item_id)
            if not base:
                output[item_id] = value_copy
                continue
            row = dict(base)
            verifier = verifier_results.get(item_id)
            if verifier is not None:
                verifier_label = str(verifier.get("label") or "")
                row["boundary_verifier_label"] = verifier_label
                row["boundary_verifier_rationale"] = str(
                    verifier.get("rationale") or ""
                )
                row["boundary_verifier_version"] = verifier_version
                row["boundary_verifier_minimum_score"] = minimum_score
                if verifier_label == "partial" and row.get("label") != "partial":
                    row["pre_boundary_label"] = row.get("label")
                    row["pre_boundary_rationale"] = row.get("rationale")
                    row["label"] = "partial"
                    row["rationale"] = str(
                        verifier.get("rationale") or row.get("rationale") or ""
                    )
                    row["boundary_action"] = "override_partial"
                    overrides += 1
                else:
                    row["boundary_action"] = "retain_base"
            else:
                row["boundary_action"] = "not_score_eligible"
            parsed = dict(row.get("parsed") or {})
            parsed.update({
                "label": row.get("label"),
                "rationale": row.get("rationale"),
            })
            row["parsed"] = parsed
            value_copy["calitree"] = row
            output[item_id] = value_copy
        report = {
            "version": "rubric-lite-boundary-v1",
            "verifier_version": verifier_version,
            "minimum_ordinal_score": minimum_score,
            "apply_split": apply_split,
            "n_items": len(judge_result),
            "n_split_eligible": len(eligible_split_ids),
            "n_score_eligible": len(candidate_ids),
            "n_partial_overrides": overrides,
            "usage": runtime.usage,
            "verifier_results": verifier_results,
        }
        ctx.run.write_json(
            f"rubric_lite_boundary_{ctx.node_id}.json", report
        )
        return NodeRunResult(
            outputs={"judge_result": output},
            meta={
                "architecture": "rubric_lite_boundary",
                "n_items": len(judge_result),
                "n_score_eligible": len(candidate_ids),
                "n_partial_overrides": overrides,
                "usage": runtime.usage,
            },
        )
