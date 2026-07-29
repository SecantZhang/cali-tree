"""Workflow node for the single-prompt Rubric-Lite calibration alternative."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core.calibration.rubric_lite import RubricLiteLearner
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
RUBRIC_VERSIONS = ("rubric_lite_v1", "rubric_lite_v2")


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
                            (max_steps + 2) * len(learning_ids)
                            + len(test_ids)
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
        tree = learned.prompt_tree()
        tree["prompt_version"] = rubric_version
        tree["rubric_version"] = rubric_version
        selected_results = runtime.judge_many(
            learned.prompt,
            {item_id: samples[item_id] for item_id in all_ids},
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
