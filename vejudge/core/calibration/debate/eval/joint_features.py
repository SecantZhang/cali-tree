"""Prompt-aware features for joint M3/M5/M6 semantic calibration.

Temperature repeats are variants of one video/metric judgment, not extra independent
training examples. They are collapsed into a score distribution. Metrics remain separate
tasks, but every task from the same video stays in the same train/validation group and the
task/rating weights sum to one per video.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean, median, pstdev
from typing import Any


def group_calibration_variants(
    calibration_inputs: Any,
) -> dict[str, dict[str, Any]]:
    sources = calibration_inputs if isinstance(calibration_inputs, list) else [calibration_inputs]
    grouped: dict[str, dict[str, Any]] = {}
    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        for fallback_item_id, result in source.items():
            if not isinstance(result, dict):
                continue
            item_id = str(result.get("item_id") or fallback_item_id)
            metric_id = str(result.get("metric_id") or "")
            score = result.get("original_score")
            if not metric_id or not isinstance(score, (int, float)) or isinstance(score, bool):
                continue
            task_key = f"{item_id}::metric::{metric_id}"
            task = grouped.setdefault(task_key, {
                "task_key": task_key,
                "item_id": item_id,
                "metric_id": metric_id,
                "variants": [],
            })
            provenance = dict(result.get("judge_provenance") or {})
            provenance.setdefault("source_index", source_index)
            nested_variants = result.get("judge_variants") or []
            if nested_variants:
                for nested in nested_variants:
                    nested_score = nested.get("score")
                    if isinstance(nested_score, (int, float)) and not isinstance(nested_score, bool):
                        task["variants"].append({
                            "score": float(nested_score), "result": result,
                            "provenance": dict(nested.get("judge_provenance") or provenance),
                        })
            else:
                task["variants"].append({
                    "score": float(score),
                    "result": result,
                    "provenance": provenance,
                })

    for task in grouped.values():
        scores = [variant["score"] for variant in task["variants"]]
        task["base"] = mean(scores)
        task["base_median"] = median(scores)
        task["score_std"] = pstdev(scores) if len(scores) > 1 else 0.0
        task["score_range"] = max(scores) - min(scores)
        task["variant_count"] = len(scores)
        task["temperatures"] = sorted({
            float(temp)
            for variant in task["variants"]
            for temp in [variant["provenance"].get("temperature")]
            if isinstance(temp, (int, float)) and not isinstance(temp, bool)
        })
    return grouped


def joint_base_feature_names(metric_ids: list[str]) -> list[str]:
    return [
        "base_score", "score_std", "score_range",
        *[f"prompt:{metric_id}" for metric_id in sorted(set(metric_ids))],
    ]


def build_joint_feature_rows(
    tasks: dict[str, dict[str, Any]],
    semantic_features: dict[str, list[float]],
    metric_ids: list[str],
) -> tuple[list[str], dict[str, list[float]]]:
    metrics = sorted(set(metric_ids))
    names = joint_base_feature_names(metrics)
    rows = {
        task_key: [
            float(task["base"]),
            float(task["score_std"]),
            float(task["score_range"]),
            *[1.0 if task["metric_id"] == metric else 0.0 for metric in metrics],
            *[float(value) for value in semantic_features.get(task_key, [])],
        ]
        for task_key, task in tasks.items()
    }
    return names, rows


def build_joint_observations(
    tasks: dict[str, dict[str, Any]],
    feature_rows: dict[str, list[float]],
) -> tuple[
    list[str], dict[str, str], dict[str, str], dict[str, float],
    dict[str, float], dict[str, list[float]], dict[str, float],
]:
    tasks_per_item = Counter(task["item_id"] for task in tasks.values() if task.get("humans"))
    observation_ids: list[str] = []
    observation_item: dict[str, str] = {}
    observation_task: dict[str, str] = {}
    bases: dict[str, float] = {}
    humans: dict[str, float] = {}
    features: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    for task_key, task in tasks.items():
        targets = list(task.get("humans") or [])
        if not targets:
            continue
        task_weight = 1.0 / tasks_per_item[task["item_id"]]
        for index, target in enumerate(targets):
            obs = f"{task_key}::human::{index}"
            observation_ids.append(obs)
            observation_item[obs] = task["item_id"]
            observation_task[obs] = task_key
            bases[obs] = float(task["base"])
            humans[obs] = float(target)
            features[obs] = list(feature_rows[task_key])
            weights[obs] = task_weight / len(targets)
    return (
        observation_ids, observation_item, observation_task, bases, humans, features, weights,
    )


def filter_joint_constant_questions(
    bank: list[dict[str, Any]], values: dict[str, list[float]],
    tasks: dict[str, dict[str, Any]], training_items: list[str],
) -> tuple[list[dict[str, Any]], dict[str, list[float]], list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    """Drop questions constant among applicable training tasks, not across prompt zeros."""
    training_set = set(training_items)
    kept: list[int] = []
    prevalence: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for index, question in enumerate(bank):
        applies = set(question.get("metric_ids") or [])
        observed = [
            row[index]
            for task_key, row in values.items()
            if tasks[task_key]["item_id"] in training_set
            and (not applies or tasks[task_key]["metric_id"] in applies)
            and index < len(row)
        ]
        info = {
            "question_index": index,
            "question": question.get("question"),
            "metric_ids": sorted(applies),
            "positive_rate": mean(observed) if observed else None,
            "n_training": len(observed),
        }
        prevalence.append(info)
        if not observed or len(set(observed)) <= 1:
            dropped.append({**info, "reason": "constant_on_applicable_training_tasks"})
        else:
            kept.append(index)
    return (
        [bank[index] for index in kept],
        {
            task_key: [row[index] for index in kept if index < len(row)]
            for task_key, row in values.items()
        },
        prevalence,
        dropped,
        kept,
    )
