"""Shared data preparation for rule/tree calibration nodes."""

from __future__ import annotations

import hashlib
import json
from statistics import mean, median, pvariance
from typing import Any

from ...core.calibration.debate.semantic_summary import validate_summary


EVALUATION_VERSION = "calibration-eval-v4-graded-rubric-tree"


def stable_holdout_split(
    item_ids: list[str], *, validation_fraction: float, split_seed: int,
) -> tuple[list[str], list[str]]:
    ordered = sorted(
        item_ids,
        key=lambda item: hashlib.sha256(f"{split_seed}:{item}".encode()).hexdigest(),
    )
    if len(ordered) < 2:
        return ordered, []
    n_validation = min(
        len(ordered) - 1,
        max(1, round(len(ordered) * min(0.5, max(0.1, validation_fraction)))),
    )
    validation = sorted(ordered[:n_validation])
    training = sorted(ordered[n_validation:])
    return training, validation


def semantic_summary_text(calibration_result: dict[str, Any]) -> str:
    """Render only validated structured semantics; never fall back to the transcript."""
    summary = calibration_result.get("semantic_summary")
    if not isinstance(summary, dict):
        return ""
    validated, _error = validate_summary(summary)
    if validated is None:
        return ""
    summary = validated.to_dict()
    parts: list[str] = []
    for key in (
        "principle", "applies_when", "evidence_to_check", "scoring_guidance",
        "counter_consideration",
    ):
        value = summary.get(key)
        if isinstance(value, list):
            parts.extend(str(entry).strip() for entry in value if str(entry).strip())
        elif value is not None and str(value).strip():
            parts.append(str(value).strip())
    return "\n".join(parts)


def evaluation_cache_suffix(
    *, metric_id: str, training_ids: list[str], max_questions: int, critic_config: dict[str, Any],
) -> str:
    payload = {
        "version": EVALUATION_VERSION,
        "metric": metric_id,
        "training_ids": training_ids,
        "max_questions": max_questions,
        "critic": critic_config,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_observations(
    anchored: dict[str, dict[str, Any]], semantic_features: dict[str, list[float]],
) -> tuple[list[str], dict[str, str], dict[str, float], dict[str, float], dict[str, list[float]], dict[str, float]]:
    observation_ids: list[str] = []
    observation_item: dict[str, str] = {}
    bases: dict[str, float] = {}
    humans: dict[str, float] = {}
    feats: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    for item, record in anchored.items():
        targets = list(record["humans"])
        weight = 1.0 / len(targets)
        for index, target in enumerate(targets):
            obs = f"{item}::human::{index}"
            observation_ids.append(obs)
            observation_item[obs] = item
            bases[obs] = float(record["base"])
            humans[obs] = float(target)
            feats[obs] = [bases[obs], *[float(value) for value in semantic_features.get(item, [])]]
            weights[obs] = weight
    return observation_ids, observation_item, bases, humans, feats, weights


def filter_constant_questions(
    bank: list[dict[str, Any]], features: dict[str, list[float]], training_ids: list[str],
) -> tuple[list[dict[str, Any]], dict[str, list[float]], list[dict[str, Any]], list[dict[str, Any]]]:
    kept_indices: list[int] = []
    prevalence: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for index, question in enumerate(bank):
        values = [features.get(item, [])[index] for item in training_ids
                  if index < len(features.get(item, []))]
        rate = mean(values) if values else None
        info = {"question_index": index, "question": question.get("question"),
                "positive_rate": rate, "n_training": len(values)}
        prevalence.append(info)
        if not values or len(set(values)) <= 1:
            dropped.append({**info, "reason": "constant_on_training"})
        else:
            kept_indices.append(index)
    kept_bank = [bank[index] for index in kept_indices]
    filtered = {
        item: [values[index] for index in kept_indices if index < len(values)]
        for item, values in features.items()
    }
    return kept_bank, filtered, prevalence, dropped


def impute_missing_semantic_values(
    values: dict[str, list[float]],
    missing: dict[str, list[str]],
    training_ids: list[str],
) -> tuple[dict[str, list[float]], list[dict[str, Any]]]:
    """Impute critic failures with training-only feature medians.

    Zero is meaningful evidence strength (uncertain), so failed answers must not silently
    masquerade as zeros. Each question is imputed independently and validation values never
    influence the fill value.
    """
    width = max((len(row) for row in values.values()), default=0)
    fill: list[float] = []
    diagnostics: list[dict[str, Any]] = []
    for index in range(width):
        qid = f"q{index + 1}"
        observed = [
            values[item][index]
            for item in training_ids
            if index < len(values.get(item, [])) and qid not in set(missing.get(item, []))
        ]
        replacement = float(median(observed)) if observed else 0.0
        fill.append(replacement)
        diagnostics.append({
            "question_index": index,
            "training_median": replacement,
            "n_training_observed": len(observed),
        })
    imputed: dict[str, list[float]] = {}
    for item, row in values.items():
        missing_set = set(missing.get(item, []))
        imputed[item] = [
            fill[index] if f"q{index + 1}" in missing_set else float(value)
            for index, value in enumerate(row)
        ]
    return imputed, diagnostics


def preflight_diagnostics(
    *, metric_id: str, dimensions: list[str], usable_cr: dict[str, Any],
    anchored: dict[str, dict[str, Any]], skipped: dict[str, str],
    training_ids: list[str], validation_ids: list[str],
) -> tuple[dict[str, Any], list[str]]:
    bases = [float(record["base"]) for record in anchored.values()]
    warnings: list[str] = []
    variance = pvariance(bases) if len(bases) > 1 else 0.0
    if variance < 1e-8:
        warnings.append(
            "All usable raw judge scores are constant; score-only calibration cannot learn item ordering."
        )
    if len(training_ids) < 20:
        warnings.append(f"Only {len(training_ids)} independent training videos; results are exploratory.")
    if validation_ids and len(validation_ids) < 5:
        warnings.append(
            f"Only {len(validation_ids)} validation videos; do not claim a reliable improvement."
        )
    if skipped:
        warnings.append(
            f"Skipped {len(skipped)} item(s) without usable metric-aligned targets."
        )
    score_field = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
    return {
        "metric_id": metric_id,
        "human_dimensions": dimensions,
        "score_source": {"parsed_field": score_field, "aggregation": "raw judge output"},
        "n_overlapping_items": len(usable_cr),
        "n_usable_items": len(anchored),
        "n_raw_ratings": sum(len(record["humans"]) for record in anchored.values()),
        "ratings_per_item": {item: len(record["humans"]) for item, record in anchored.items()},
        "skipped_items": skipped,
        "base_score_values": {item: record["base"] for item, record in anchored.items()},
        "base_score_variance": variance,
        "n_unique_base_scores": len(set(bases)),
        "effective_train_items": len(training_ids),
        "effective_validation_items": len(validation_ids),
    }, warnings
