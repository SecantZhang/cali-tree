"""A small, validation-guarded alternative to hierarchical Cali-Tree calibration.

Rubric-Lite learns one global rubric from balanced boundary errors.  It deliberately has no
prompt leaves, embeddings, clustering, routing, merge policy, editor prior, or ensemble.
The resulting prompt tree contains a single root so it remains compatible with the existing
Cali-Tree judge and evaluation sockets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .calitree import LABELS, classification_metrics


def _task_uid(item_id: str, sample: dict[str, Any]) -> str:
    return str(sample.get("task_uid") or item_id.rsplit("::", 1)[0])


def _boundary_bucket(target: str, prediction: str) -> str:
    if target == "partial" and prediction != "partial":
        return "missed_partial"
    if prediction == "partial" and target != "partial":
        return "false_partial"
    if target != prediction:
        return f"{target}_as_{prediction}"
    if target == "partial":
        return "correct_partial_anchor"
    return "correct_outer_anchor"


def select_boundary_cases(
    *,
    ids: list[str],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    results: dict[str, dict[str, Any]],
    per_bucket: int = 8,
) -> list[str]:
    """Select diverse errors and anchors without letting one task/editor dominate.

    Partial false negatives and false positives are separate buckets.  Correct partial and
    outer-class anchors keep a rewrite from increasing recall by simply predicting partial
    everywhere.  Within a bucket, the first pass takes at most one output per source task.
    """
    limit = max(1, int(per_bucket))
    buckets: dict[str, list[str]] = {}
    for item_id in sorted(ids):
        prediction = str((results.get(item_id) or {}).get("label") or "")
        target = targets[item_id]
        bucket = _boundary_bucket(target, prediction)
        buckets.setdefault(bucket, []).append(item_id)

    priority = (
        "missed_partial",
        "false_partial",
        "no_as_yes",
        "yes_as_no",
        "no_as_partial",
        "yes_as_partial",
        "partial_as_no",
        "partial_as_yes",
        "correct_partial_anchor",
        "correct_outer_anchor",
    )
    selected: list[str] = []
    for bucket in priority:
        candidates = buckets.get(bucket) or []
        if not candidates:
            continue
        chosen: list[str] = []
        seen_tasks: set[str] = set()
        for item_id in candidates:
            task = _task_uid(item_id, samples[item_id])
            if task in seen_tasks:
                continue
            chosen.append(item_id)
            seen_tasks.add(task)
            if len(chosen) == limit:
                break
        if len(chosen) < limit:
            chosen.extend(
                item_id
                for item_id in candidates
                if item_id not in chosen
            )
        selected.extend(chosen[:limit])
    return list(dict.fromkeys(selected))


def _metric_value(metrics: dict[str, Any], section: str, label: str) -> float:
    value = (metrics.get(section) or {}).get(label)
    return float(value) if value is not None else 0.0


def _selection_key(
    metrics: dict[str, Any],
    *,
    baseline_accuracy: float,
    max_accuracy_drop: float,
    prompt: str,
) -> tuple[float, ...]:
    accuracy = float(metrics.get("accuracy") or 0.0)
    eligible = accuracy + max_accuracy_drop >= baseline_accuracy
    partial_f1 = _metric_value(metrics, "per_label_f1", "partial")
    partial_recall = _metric_value(metrics, "per_label_accuracy", "partial")
    balanced = float(metrics.get("balanced_accuracy") or 0.0)
    return (
        float(eligible),
        partial_f1 if eligible else accuracy,
        partial_recall if eligible else balanced,
        balanced,
        accuracy,
        -float(len(prompt)),
    )


@dataclass
class RubricLiteResult:
    prompt: str
    initial_prompt: str
    fit_results: dict[str, dict[str, Any]]
    validation_results: dict[str, dict[str, Any]]
    report: dict[str, Any]

    def prompt_tree(self) -> dict[str, Any]:
        root_id = "rubric:global"
        validation = self.report["selected"]["validation"]
        return {
            "version": "rubric-lite-v1",
            "architecture": "rubric_lite",
            "roots": [root_id],
            "nodes": {
                root_id: {
                    "id": root_id,
                    "prompt": self.prompt,
                    "covered_ids": sorted(self.fit_results),
                    "embedding": [],
                    "components": {
                        "criteria": ["condition evidence: none | partial | full"],
                        "priorities": ["missing", "partial", "full"],
                        "constraints": ["single JSON judgment"],
                    },
                    "level": 0,
                    "status": "global_rubric",
                    "children": [],
                    "validation_accuracy": validation.get("accuracy") or 0.0,
                    "routing_threshold": -1.0,
                }
            },
            "timeline": self.report["trials"],
            "warm_start_prompt": self.prompt,
            "global_selection": self.report["selection"],
            "stats": {
                "leaves": 0,
                "accepted_merges": 0,
                "rejected_merges": 0,
                "promoted": 0,
                "roots": 1,
                "specialized_roots": 0,
                "optimizer_steps": self.report["optimizer_steps"],
            },
            "config": self.report["config"],
        }


class RubricLiteLearner:
    """Learn one global ordinal rubric and select it on task-disjoint validation."""

    def __init__(
        self,
        *,
        judge_many: Callable[
            [str, dict[str, dict[str, Any]]],
            dict[str, dict[str, Any]],
        ],
        optimize: Callable[[str, str], str],
        format_feedback: Callable[
            [list[str], dict[str, dict[str, Any]], dict[str, str], dict[str, dict[str, Any]]],
            str,
        ],
        max_steps: int = 3,
        feedback_cases_per_bucket: int = 8,
        max_validation_accuracy_drop: float = 0.01,
        progress: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        self.judge_many = judge_many
        self.optimize = optimize
        self.format_feedback = format_feedback
        self.max_steps = max(0, int(max_steps))
        self.feedback_cases_per_bucket = max(
            1, int(feedback_cases_per_bucket)
        )
        self.max_validation_accuracy_drop = max(
            0.0, float(max_validation_accuracy_drop)
        )
        self.progress = progress

    def _evaluate(
        self,
        prompt: str,
        ids: list[str],
        samples: dict[str, dict[str, Any]],
        targets: dict[str, str],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        selected = {item_id: samples[item_id] for item_id in ids}
        results = self.judge_many(prompt, selected) if selected else {}
        predictions = {
            item_id: str(result.get("label") or "")
            for item_id, result in results.items()
        }
        metrics = classification_metrics(
            {item_id: targets[item_id] for item_id in ids},
            predictions,
            samples,
        )
        return results, metrics

    def fit(
        self,
        *,
        initial_prompt: str,
        samples: dict[str, dict[str, Any]],
        targets: dict[str, str],
        fit_ids: list[str],
        validation_ids: list[str],
    ) -> RubricLiteResult:
        fit_ids = sorted(set(fit_ids) & set(samples) & set(targets))
        validation_ids = sorted(
            set(validation_ids) & set(samples) & set(targets)
        )
        selection_ids = validation_ids or fit_ids
        selection_split = (
            "task_grouped_internal_validation"
            if validation_ids
            else "fit_fallback_no_validation"
        )
        initial_fit_results, initial_fit_metrics = self._evaluate(
            initial_prompt, fit_ids, samples, targets
        )
        initial_validation_results, initial_validation_metrics = self._evaluate(
            initial_prompt, selection_ids, samples, targets
        )
        candidates: list[dict[str, Any]] = [{
            "step": 0,
            "prompt": initial_prompt,
            "fit_results": initial_fit_results,
            "fit": initial_fit_metrics,
            "validation_results": initial_validation_results,
            "validation": initial_validation_metrics,
            "feedback_ids": [],
            "selected": True,
        }]
        current_prompt = initial_prompt
        current_fit_results = initial_fit_results
        stop_reason = "max_steps"
        for step in range(1, self.max_steps + 1):
            feedback_ids = select_boundary_cases(
                ids=fit_ids,
                samples=samples,
                targets=targets,
                results=current_fit_results,
                per_bucket=self.feedback_cases_per_bucket,
            )
            mistakes = [
                item_id for item_id in fit_ids
                if str(current_fit_results[item_id].get("label") or "")
                != targets[item_id]
            ]
            if not mistakes:
                stop_reason = "fit_correct"
                break
            feedback = self.format_feedback(
                feedback_ids, samples, targets, current_fit_results
            )
            updated_prompt = self.optimize(current_prompt, feedback)
            if updated_prompt.strip() == current_prompt.strip():
                stop_reason = "optimizer_unchanged"
                break
            fit_results, fit_metrics = self._evaluate(
                updated_prompt, fit_ids, samples, targets
            )
            validation_results, validation_metrics = self._evaluate(
                updated_prompt, selection_ids, samples, targets
            )
            candidates.append({
                "step": step,
                "prompt": updated_prompt,
                "fit_results": fit_results,
                "fit": fit_metrics,
                "validation_results": validation_results,
                "validation": validation_metrics,
                "feedback_ids": feedback_ids,
                "selected": False,
            })
            current_prompt = updated_prompt
            current_fit_results = fit_results
            if self.progress:
                self.progress("rubric_lite_step", {
                    "completed": step,
                    "total": self.max_steps,
                    "fit_accuracy": fit_metrics.get("accuracy"),
                    "validation_accuracy": validation_metrics.get("accuracy"),
                    "validation_partial_f1": (
                        validation_metrics.get("per_label_f1") or {}
                    ).get("partial"),
                })

        baseline_accuracy = float(
            initial_validation_metrics.get("accuracy") or 0.0
        )
        selected = max(
            candidates,
            key=lambda candidate: _selection_key(
                candidate["validation"],
                baseline_accuracy=baseline_accuracy,
                max_accuracy_drop=self.max_validation_accuracy_drop,
                prompt=candidate["prompt"],
            ),
        )
        for candidate in candidates:
            candidate["selected"] = candidate is selected
        trials = [{
            "kind": "rubric_lite_candidate",
            "node_id": f"rubric:candidate:{candidate['step']}",
            "step": candidate["step"],
            "selected": candidate["selected"],
            "feedback_cases": len(candidate["feedback_ids"]),
            "fit": candidate["fit"],
            "validation": candidate["validation"],
            "prompt_chars": len(candidate["prompt"]),
        } for candidate in candidates]
        report = {
            "version": "rubric-lite-v1",
            "architecture": "rubric_lite",
            "selection_split": selection_split,
            "optimizer_steps": len(candidates) - 1,
            "stop_reason": stop_reason,
            "initial": {
                "fit": initial_fit_metrics,
                "validation": initial_validation_metrics,
            },
            "selected": {
                "step": selected["step"],
                "fit": selected["fit"],
                "validation": selected["validation"],
            },
            "selection": {
                "criterion": (
                    "maximize_partial_f1_with_validation_accuracy_guard"
                ),
                "baseline_validation_accuracy": baseline_accuracy,
                "max_validation_accuracy_drop": (
                    self.max_validation_accuracy_drop
                ),
                "selected_step": selected["step"],
                "selected_validation_accuracy": selected["validation"].get(
                    "accuracy"
                ),
                "selected_validation_partial_precision": (
                    selected["validation"].get("per_label_precision") or {}
                ).get("partial"),
                "selected_validation_partial_recall": (
                    selected["validation"].get("per_label_accuracy") or {}
                ).get("partial"),
                "selected_validation_partial_f1": (
                    selected["validation"].get("per_label_f1") or {}
                ).get("partial"),
            },
            "trials": trials,
            "config": {
                "max_steps": self.max_steps,
                "feedback_cases_per_bucket": (
                    self.feedback_cases_per_bucket
                ),
                "max_validation_accuracy_drop": (
                    self.max_validation_accuracy_drop
                ),
            },
        }
        return RubricLiteResult(
            prompt=selected["prompt"],
            initial_prompt=initial_prompt,
            fit_results=selected["fit_results"],
            validation_results=selected["validation_results"],
            report=report,
        )
