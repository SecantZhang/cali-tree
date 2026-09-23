"""A small, validation-guarded alternative to hierarchical Cali-Tree calibration.

Rubric-Lite learns one global rubric from balanced boundary errors.  It deliberately has no
prompt leaves, embeddings, clustering, routing, merge policy, editor prior, or ensemble.
The resulting prompt tree contains a single root so it remains compatible with the existing
Cali-Tree judge and evaluation sockets.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .calitree import LABELS, classification_metrics


DEFAULT_ORDINAL_THRESHOLDS = {
    "no_partial": 35.0,
    "partial_yes": 90.0,
}


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


def ordinal_label(
    score: float,
    thresholds: dict[str, float],
) -> str:
    """Map one visible-evidence score onto the ordered SC labels."""
    no_partial = float(thresholds["no_partial"])
    partial_yes = float(thresholds["partial_yes"])
    if no_partial >= partial_yes:
        raise ValueError("no_partial threshold must be below partial_yes")
    if float(score) < no_partial:
        return "no"
    if float(score) < partial_yes:
        return "partial"
    return "yes"


def apply_ordinal_thresholds(
    results: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Return calibrated copies while preserving each judge's raw label."""
    calibrated: dict[str, dict[str, Any]] = {}
    for item_id, result in results.items():
        row = dict(result)
        score = row.get("ordinal_score")
        if isinstance(score, (int, float)):
            raw_label = str(
                row.get("uncalibrated_label") or row.get("label") or ""
            )
            row["uncalibrated_label"] = raw_label
            row["label"] = ordinal_label(float(score), thresholds)
            row["ordinal_thresholds"] = {
                "no_partial": float(thresholds["no_partial"]),
                "partial_yes": float(thresholds["partial_yes"]),
            }
            row["threshold_calibrated"] = row["label"] != raw_label
        calibrated[item_id] = row
    return calibrated


def _threshold_candidates(scores: list[float]) -> list[float]:
    """Boundaries immediately above observed scores cover every partition."""
    values = {0.0, 100.000001}
    values.update(min(100.000001, float(score) + 0.000001) for score in scores)
    return sorted(values)


def fit_ordinal_thresholds(
    *,
    results: dict[str, dict[str, Any]],
    targets: dict[str, str],
    samples: dict[str, dict[str, Any]],
    ids: list[str],
    accuracy_tolerance: float = 0.01,
    minimum_class_recall: float = 0.10,
    default_thresholds: Optional[dict[str, float]] = None,
    selection_objective: str = "accuracy_guarded_partial",
) -> dict[str, Any]:
    """Fit two global cutpoints without editor, task, or instruction features.

    First retain pairs that meet ``minimum_class_recall`` for every class represented in
    calibration data. ``accuracy_guarded_partial`` preserves the original policy: stay
    within ``accuracy_tolerance`` of maximum accuracy, then prefer partial F1.
    ``macro_f1`` directly prefers macro F1, then partial F1, balanced accuracy, and ordinary
    accuracy. Both objectives reject a predict-one-class solution when a class-preserving
    pair exists.
    """
    if selection_objective not in {
        "accuracy_guarded_partial",
        "macro_f1",
    }:
        raise ValueError(
            "selection_objective must be 'accuracy_guarded_partial' or "
            "'macro_f1'"
        )
    defaults = dict(default_thresholds or DEFAULT_ORDINAL_THRESHOLDS)
    usable = [
        item_id
        for item_id in sorted(set(ids) & set(results) & set(targets) & set(samples))
        if isinstance(results[item_id].get("ordinal_score"), (int, float))
    ]
    if not usable:
        return {
            "version": "global-ordinal-cutpoints-v1",
            "thresholds": defaults,
            "n": 0,
            "max_accuracy": None,
            "accuracy_tolerance": max(0.0, float(accuracy_tolerance)),
            "minimum_class_recall": max(
                0.0, min(1.0, float(minimum_class_recall))
            ),
            "selection_objective": selection_objective,
            "metrics": classification_metrics({}, {}, samples),
            "fallback": "no_valid_ordinal_scores",
        }
    candidates = _threshold_candidates([
        float(results[item_id]["ordinal_score"]) for item_id in usable
    ])
    trials: list[dict[str, Any]] = []
    selected_targets = {item_id: targets[item_id] for item_id in usable}
    for index, no_partial in enumerate(candidates[:-1]):
        for partial_yes in candidates[index + 1:]:
            thresholds = {
                "no_partial": no_partial,
                "partial_yes": partial_yes,
            }
            calibrated = apply_ordinal_thresholds(
                {item_id: results[item_id] for item_id in usable},
                thresholds,
            )
            metrics = classification_metrics(
                selected_targets,
                {
                    item_id: str(calibrated[item_id].get("label") or "")
                    for item_id in usable
                },
                samples,
            )
            trials.append({"thresholds": thresholds, "metrics": metrics})
    recall_floor = max(0.0, min(1.0, float(minimum_class_recall)))
    represented_labels = [
        label
        for label in LABELS
        if any(targets[item_id] == label for item_id in usable)
    ]
    class_preserving = [
        trial
        for trial in trials
        if all(
            float(
                (trial["metrics"].get("per_label_accuracy") or {}).get(
                    label
                )
                or 0.0
            )
            + 1e-12
            >= recall_floor
            for label in represented_labels
        )
    ]
    candidate_pool = class_preserving or trials
    max_accuracy = max(
        float(trial["metrics"].get("accuracy") or 0.0)
        for trial in candidate_pool
    )
    tolerance = max(0.0, float(accuracy_tolerance))
    eligible = (
        candidate_pool
        if selection_objective == "macro_f1"
        else [
            trial
            for trial in candidate_pool
            if float(trial["metrics"].get("accuracy") or 0.0)
            + tolerance
            + 1e-12
            >= max_accuracy
        ]
    )

    def selection_key(trial: dict[str, Any]) -> tuple[float, ...]:
        metrics = trial["metrics"]
        thresholds = trial["thresholds"]
        partial_f1 = float(
            (metrics.get("per_label_f1") or {}).get("partial") or 0.0
        )
        macro_f1 = float(metrics.get("macro_f1") or 0.0)
        balanced = float(metrics.get("balanced_accuracy") or 0.0)
        accuracy = float(metrics.get("accuracy") or 0.0)
        stability = (
            -abs(thresholds["no_partial"] - defaults["no_partial"])
            - abs(thresholds["partial_yes"] - defaults["partial_yes"])
        )
        if selection_objective == "macro_f1":
            return (
                macro_f1,
                partial_f1,
                balanced,
                accuracy,
                stability,
            )
        return (
            partial_f1,
            macro_f1,
            balanced,
            accuracy,
            stability,
        )

    selected = max(eligible, key=selection_key)
    return {
        "version": "global-ordinal-cutpoints-v1",
        "thresholds": selected["thresholds"],
        "n": len(usable),
        "max_accuracy": max_accuracy,
        "accuracy_tolerance": tolerance,
        "minimum_class_recall": recall_floor,
        "selection_objective": selection_objective,
        "class_preserving_candidate_count": len(class_preserving),
        "metrics": selected["metrics"],
        "candidate_count": len(trials),
        "fallback": (
            None
            if class_preserving
            else "no_candidate_met_minimum_class_recall"
        ),
    }


DEFAULT_TWO_GATE_THRESHOLDS = {"presence_cut": 35.0, "completeness_cut": 90.0}


def _two_gate_axes(row: dict[str, Any]) -> Optional[tuple[float, float]]:
    """Return (change_evidence, specification_fidelity) — the presence/completeness axes."""
    scores = row.get("ordinal_scores") or row.get("normalized_ordinal_scores") or {}
    presence = scores.get("change_evidence")
    completeness = scores.get("specification_fidelity")
    if isinstance(presence, (int, float)) and isinstance(completeness, (int, float)):
        return float(presence), float(completeness)
    return None


def two_gate_label(
    change_evidence: float,
    specification_fidelity: float,
    presence_cut: float,
    completeness_cut: float,
) -> str:
    """Derive the label from two independent gates instead of one collapsed scalar.

    Presence gate: is any requested change visibly present? Completeness gate: is it exactly
    done? ``partial`` = present but not complete — the boundary a single ``min`` scalar hides.
    """
    if float(change_evidence) < float(presence_cut):
        return "no"
    if float(specification_fidelity) >= float(completeness_cut):
        return "yes"
    return "partial"


def apply_two_gate(
    results: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Return calibrated copies whose label comes from the two gates; raw label preserved."""
    presence_cut = float(thresholds["presence_cut"])
    completeness_cut = float(thresholds["completeness_cut"])
    calibrated: dict[str, dict[str, Any]] = {}
    for item_id, result in results.items():
        row = dict(result)
        axes = _two_gate_axes(row)
        if axes is not None:
            raw_label = str(row.get("uncalibrated_label") or row.get("label") or "")
            row["uncalibrated_label"] = raw_label
            row["label"] = two_gate_label(
                axes[0], axes[1], presence_cut, completeness_cut
            )
            row["two_gate_thresholds"] = {
                "presence_cut": presence_cut,
                "completeness_cut": completeness_cut,
            }
            row["threshold_calibrated"] = row["label"] != raw_label
        calibrated[item_id] = row
    return calibrated


def fit_two_gate_thresholds(
    *,
    results: dict[str, dict[str, Any]],
    targets: dict[str, str],
    samples: dict[str, dict[str, Any]],
    ids: list[str],
    accuracy_tolerance: float = 0.01,
    minimum_class_recall: float = 0.10,
    default_thresholds: Optional[dict[str, float]] = None,
    selection_objective: str = "macro_f1",
) -> dict[str, Any]:
    """Fit a presence cutpoint (on change_evidence) and a completeness cutpoint (on
    specification_fidelity) — two independent global cutpoints, no editor/task/instruction
    features. Same class-recall floor and objective options as ``fit_ordinal_thresholds``.
    """
    if selection_objective not in {"accuracy_guarded_partial", "macro_f1"}:
        raise ValueError(
            "selection_objective must be 'accuracy_guarded_partial' or 'macro_f1'"
        )
    defaults = dict(default_thresholds or DEFAULT_TWO_GATE_THRESHOLDS)
    usable = [
        item_id
        for item_id in sorted(set(ids) & set(results) & set(targets) & set(samples))
        if _two_gate_axes(results[item_id]) is not None
    ]
    if not usable:
        return {
            "version": "two-gate-cutpoints-v1",
            "thresholds": defaults,
            "n": 0,
            "selection_objective": selection_objective,
            "metrics": classification_metrics({}, {}, samples),
            "fallback": "no_valid_axis_scores",
        }
    axes = {item_id: _two_gate_axes(results[item_id]) for item_id in usable}
    presence_candidates = _threshold_candidates([axes[i][0] for i in usable])
    completeness_candidates = _threshold_candidates([axes[i][1] for i in usable])
    selected_targets = {item_id: targets[item_id] for item_id in usable}
    trials: list[dict[str, Any]] = []
    for presence_cut in presence_candidates:
        for completeness_cut in completeness_candidates:
            predictions = {
                item_id: two_gate_label(
                    axes[item_id][0], axes[item_id][1], presence_cut, completeness_cut
                )
                for item_id in usable
            }
            metrics = classification_metrics(selected_targets, predictions, samples)
            trials.append({
                "thresholds": {
                    "presence_cut": presence_cut,
                    "completeness_cut": completeness_cut,
                },
                "metrics": metrics,
            })
    recall_floor = max(0.0, min(1.0, float(minimum_class_recall)))
    represented_labels = [
        label for label in LABELS
        if any(targets[item_id] == label for item_id in usable)
    ]
    class_preserving = [
        trial for trial in trials
        if all(
            float((trial["metrics"].get("per_label_accuracy") or {}).get(label) or 0.0)
            + 1e-12 >= recall_floor
            for label in represented_labels
        )
    ]
    candidate_pool = class_preserving or trials
    max_accuracy = max(
        float(trial["metrics"].get("accuracy") or 0.0) for trial in candidate_pool
    )
    tolerance = max(0.0, float(accuracy_tolerance))
    eligible = (
        candidate_pool
        if selection_objective == "macro_f1"
        else [
            trial for trial in candidate_pool
            if float(trial["metrics"].get("accuracy") or 0.0) + tolerance + 1e-12
            >= max_accuracy
        ]
    )

    def selection_key(trial: dict[str, Any]) -> tuple[float, ...]:
        metrics = trial["metrics"]
        thresholds = trial["thresholds"]
        partial_f1 = float((metrics.get("per_label_f1") or {}).get("partial") or 0.0)
        macro_f1 = float(metrics.get("macro_f1") or 0.0)
        balanced = float(metrics.get("balanced_accuracy") or 0.0)
        accuracy = float(metrics.get("accuracy") or 0.0)
        stability = (
            -abs(thresholds["presence_cut"] - defaults["presence_cut"])
            - abs(thresholds["completeness_cut"] - defaults["completeness_cut"])
        )
        if selection_objective == "macro_f1":
            return (macro_f1, partial_f1, balanced, accuracy, stability)
        return (partial_f1, macro_f1, balanced, accuracy, stability)

    selected = max(eligible, key=selection_key)
    return {
        "version": "two-gate-cutpoints-v1",
        "thresholds": selected["thresholds"],
        "n": len(usable),
        "max_accuracy": max_accuracy,
        "accuracy_tolerance": tolerance,
        "minimum_class_recall": recall_floor,
        "selection_objective": selection_objective,
        "class_preserving_candidate_count": len(class_preserving),
        "metrics": selected["metrics"],
        "candidate_count": len(trials),
        "fallback": (
            None if class_preserving else "no_candidate_met_minimum_class_recall"
        ),
    }


def _assign_cv_folds(
    usable: list[str],
    targets: dict[str, str],
    samples: dict[str, dict[str, Any]],
    *,
    folds: int,
    seed: int,
    group_by_task: bool,
) -> tuple[list[list[str]], int]:
    """Deterministic fold assignment shared by the ordinal and two-gate cross-validators.

    Returns ``(fold_ids, n_folds)``; ``n_folds < 2`` signals too few examples to validate.
    Task grouping keeps every editor output of a task in one fold and balances label + case
    load; otherwise folds are per-label stratified.
    """
    label_groups = {
        label: [item_id for item_id in usable if targets[item_id] == label]
        for label in LABELS
    }
    task_groups: dict[str, list[str]] = {}
    for item_id in usable:
        task_groups.setdefault(_task_uid(item_id, samples[item_id]), []).append(item_id)
    if group_by_task:
        max_folds = len(task_groups)
    else:
        represented = [group for group in label_groups.values() if group]
        max_folds = min((len(group) for group in represented), default=0)
    n_folds = min(max(2, int(folds)), max_folds) if max_folds >= 2 else 0
    if n_folds < 2:
        return [], 0
    fold_ids: list[list[str]] = [[] for _ in range(n_folds)]
    if group_by_task:
        rng = random.Random(seed)
        tie_breakers = {task_uid: rng.random() for task_uid in task_groups}
        label_totals = Counter(targets[item_id] for item_id in usable)
        target_per_fold = {label: label_totals[label] / n_folds for label in LABELS}
        target_n = len(usable) / n_folds
        ordered_tasks = sorted(
            task_groups,
            key=lambda task_uid: (
                -len(task_groups[task_uid]),
                -max(
                    Counter(
                        targets[item_id] for item_id in task_groups[task_uid]
                    ).values()
                ),
                tie_breakers[task_uid],
                task_uid,
            ),
        )
        fold_counts = [Counter() for _ in range(n_folds)]
        fold_sizes = [0 for _ in range(n_folds)]
        for task_uid in ordered_tasks:
            task_counts = Counter(
                targets[item_id] for item_id in task_groups[task_uid]
            )
            empty_folds = [
                index for index, fold_size in enumerate(fold_sizes) if fold_size == 0
            ]
            candidate_folds = empty_folds if empty_folds else range(n_folds)
            choices = []
            for fold_index in candidate_folds:
                label_loss = sum(
                    (
                        (fold_counts[fold_index][label] + task_counts[label])
                        / max(target_per_fold[label], 1.0)
                    ) ** 2
                    for label in LABELS
                )
                size_loss = (
                    (fold_sizes[fold_index] + len(task_groups[task_uid]))
                    / max(target_n, 1.0)
                ) ** 2
                choices.append(
                    (label_loss + 0.1 * size_loss, fold_sizes[fold_index], fold_index)
                )
            selected_fold = min(choices)[2]
            fold_ids[selected_fold].extend(task_groups[task_uid])
            fold_counts[selected_fold].update(task_counts)
            fold_sizes[selected_fold] += len(task_groups[task_uid])
    else:
        for label_index, label in enumerate(LABELS):
            group = list(label_groups[label])
            random.Random(seed + label_index * 1009).shuffle(group)
            for index, item_id in enumerate(group):
                fold_ids[index % n_folds].append(item_id)
    return fold_ids, n_folds


def cross_validate_two_gate(
    *,
    results: dict[str, dict[str, Any]],
    targets: dict[str, str],
    samples: dict[str, dict[str, Any]],
    ids: list[str],
    folds: int = 5,
    seed: int = 44,
    accuracy_tolerance: float = 0.01,
    minimum_class_recall: float = 0.10,
    default_thresholds: Optional[dict[str, float]] = None,
    selection_objective: str = "macro_f1",
    group_by_task: bool = False,
) -> dict[str, Any]:
    """Out-of-fold estimate for the two-gate cutpoints (mirrors the ordinal CV)."""
    usable = [
        item_id
        for item_id in sorted(set(ids) & set(results) & set(targets) & set(samples))
        if targets[item_id] in LABELS and _two_gate_axes(results[item_id]) is not None
    ]
    fold_ids, n_folds = _assign_cv_folds(
        usable, targets, samples, folds=folds, seed=seed, group_by_task=group_by_task
    )
    if n_folds < 2:
        return {
            "version": "two-gate-cutpoints-cv-v1",
            "n": len(usable),
            "folds": 0,
            "selection_objective": selection_objective,
            "group_by_task": bool(group_by_task),
            "metrics": classification_metrics({}, {}, samples),
            "fold_reports": [],
            "fallback": "insufficient_examples_per_represented_class",
        }
    predictions: dict[str, str] = {}
    fold_reports: list[dict[str, Any]] = []
    usable_set = set(usable)
    for fold_index, held_out in enumerate(fold_ids):
        fit_ids = sorted(usable_set - set(held_out))
        fitted = fit_two_gate_thresholds(
            results=results,
            targets=targets,
            samples=samples,
            ids=fit_ids,
            accuracy_tolerance=accuracy_tolerance,
            minimum_class_recall=minimum_class_recall,
            default_thresholds=default_thresholds,
            selection_objective=selection_objective,
        )
        calibrated = apply_two_gate(
            {item_id: results[item_id] for item_id in held_out},
            fitted["thresholds"],
        )
        predictions.update({
            item_id: str(calibrated[item_id].get("label") or "")
            for item_id in held_out
        })
        fold_reports.append({
            "fold": fold_index,
            "n_fit": len(fit_ids),
            "n_validation": len(held_out),
            "thresholds": fitted["thresholds"],
            "fit_metrics": fitted["metrics"],
        })
    metrics = classification_metrics(
        {item_id: targets[item_id] for item_id in usable}, predictions, samples
    )
    return {
        "version": "two-gate-cutpoints-cv-v1",
        "n": len(usable),
        "folds": n_folds,
        "seed": int(seed),
        "selection_objective": selection_objective,
        "group_by_task": bool(group_by_task),
        "metrics": metrics,
        "fold_reports": fold_reports,
        "fallback": None,
    }


def cross_validate_ordinal_thresholds(
    *,
    results: dict[str, dict[str, Any]],
    targets: dict[str, str],
    samples: dict[str, dict[str, Any]],
    ids: list[str],
    folds: int = 5,
    seed: int = 44,
    accuracy_tolerance: float = 0.01,
    minimum_class_recall: float = 0.10,
    default_thresholds: Optional[dict[str, float]] = None,
    selection_objective: str = "macro_f1",
    group_by_task: bool = False,
) -> dict[str, Any]:
    """Estimate deployment behavior with deterministic out-of-fold predictions.

    Each item is predicted by cutpoints fitted without that item's label. This is a
    development estimate only; the returned deployment calibrator must still be checked on
    a separate frozen partition. When ``group_by_task`` is enabled, every editor output
    for the same task stays in one fold and fold assignment balances label and case load.
    """
    usable = [
        item_id
        for item_id in sorted(set(ids) & set(results) & set(targets) & set(samples))
        if (
            targets[item_id] in LABELS
            and isinstance(results[item_id].get("ordinal_score"), (int, float))
        )
    ]
    label_groups = {
        label: [
            item_id for item_id in usable
            if targets[item_id] == label
        ]
        for label in LABELS
    }
    task_groups: dict[str, list[str]] = {}
    for item_id in usable:
        task_groups.setdefault(
            _task_uid(item_id, samples[item_id]),
            [],
        ).append(item_id)
    if group_by_task:
        max_folds = len(task_groups)
    else:
        represented = [
            group for group in label_groups.values() if group
        ]
        max_folds = min((len(group) for group in represented), default=0)
    n_folds = min(max(2, int(folds)), max_folds) if max_folds >= 2 else 0
    if n_folds < 2:
        return {
            "version": "global-ordinal-cutpoints-cv-v1",
            "n": len(usable),
            "folds": 0,
            "selection_objective": selection_objective,
            "group_by_task": bool(group_by_task),
            "metrics": classification_metrics({}, {}, samples),
            "fold_reports": [],
            "fallback": "insufficient_examples_per_represented_class",
        }

    fold_ids: list[list[str]] = [[] for _ in range(n_folds)]
    if group_by_task:
        rng = random.Random(seed)
        tie_breakers = {
            task_uid: rng.random() for task_uid in task_groups
        }
        label_totals = Counter(targets[item_id] for item_id in usable)
        target_per_fold = {
            label: label_totals[label] / n_folds
            for label in LABELS
        }
        target_n = len(usable) / n_folds
        ordered_tasks = sorted(
            task_groups,
            key=lambda task_uid: (
                -len(task_groups[task_uid]),
                -max(
                    Counter(
                        targets[item_id]
                        for item_id in task_groups[task_uid]
                    ).values()
                ),
                tie_breakers[task_uid],
                task_uid,
            ),
        )
        fold_counts = [Counter() for _ in range(n_folds)]
        fold_sizes = [0 for _ in range(n_folds)]
        for task_uid in ordered_tasks:
            task_counts = Counter(
                targets[item_id]
                for item_id in task_groups[task_uid]
            )
            # Seed every requested fold with one whole task. A greedy squared-load
            # objective alone can keep choosing populated folds and silently leave
            # validation folds empty.
            empty_folds = [
                index
                for index, fold_size in enumerate(fold_sizes)
                if fold_size == 0
            ]
            candidate_folds = (
                empty_folds if empty_folds else range(n_folds)
            )
            choices = []
            for fold_index in candidate_folds:
                label_loss = sum(
                    (
                        (
                            fold_counts[fold_index][label]
                            + task_counts[label]
                        )
                        / max(target_per_fold[label], 1.0)
                    ) ** 2
                    for label in LABELS
                )
                size_loss = (
                    (
                        fold_sizes[fold_index]
                        + len(task_groups[task_uid])
                    )
                    / max(target_n, 1.0)
                ) ** 2
                choices.append(
                    (
                        label_loss + 0.1 * size_loss,
                        fold_sizes[fold_index],
                        fold_index,
                    )
                )
            selected_fold = min(choices)[2]
            fold_ids[selected_fold].extend(task_groups[task_uid])
            fold_counts[selected_fold].update(task_counts)
            fold_sizes[selected_fold] += len(task_groups[task_uid])
    else:
        for label_index, label in enumerate(LABELS):
            group = list(label_groups[label])
            random.Random(seed + label_index * 1009).shuffle(group)
            for index, item_id in enumerate(group):
                fold_ids[index % n_folds].append(item_id)

    predictions: dict[str, str] = {}
    fold_reports: list[dict[str, Any]] = []
    usable_set = set(usable)
    for fold_index, held_out in enumerate(fold_ids):
        held_out_set = set(held_out)
        fit_ids = sorted(usable_set - held_out_set)
        fitted = fit_ordinal_thresholds(
            results=results,
            targets=targets,
            samples=samples,
            ids=fit_ids,
            accuracy_tolerance=accuracy_tolerance,
            minimum_class_recall=minimum_class_recall,
            default_thresholds=default_thresholds,
            selection_objective=selection_objective,
        )
        calibrated = apply_ordinal_thresholds(
            {item_id: results[item_id] for item_id in held_out},
            fitted["thresholds"],
        )
        predictions.update({
            item_id: str(calibrated[item_id].get("label") or "")
            for item_id in held_out
        })
        fold_reports.append({
            "fold": fold_index,
            "n_fit": len(fit_ids),
            "n_validation": len(held_out),
            "thresholds": fitted["thresholds"],
            "fit_metrics": fitted["metrics"],
            "validation_task_uids": sorted({
                _task_uid(item_id, samples[item_id])
                for item_id in held_out
            }),
        })
    metrics = classification_metrics(
        {item_id: targets[item_id] for item_id in usable},
        predictions,
        samples,
    )
    return {
        "version": "global-ordinal-cutpoints-cv-v1",
        "n": len(usable),
        "folds": n_folds,
        "seed": int(seed),
        "selection_objective": selection_objective,
        "group_by_task": bool(group_by_task),
        "metrics": metrics,
        "fold_reports": fold_reports,
        "fallback": None,
    }


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
