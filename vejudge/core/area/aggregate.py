"""Aggregate local area judgments into Eval-compatible video-level signals."""

from __future__ import annotations

import math
from statistics import mean, pvariance
from typing import Any

RUBRIC_WEIGHTS = {
    "transition_smoothness": 1.0,
    "visual_quality_temporal_stability": 1.0,
    "pacing_narrative_coherence": 1.0,
    "audio_continuity_av_sync": 1.0,
}

EDIT_DIMENSIONS = {
    "story_flow_voiceover",
    "story_flow_visuals",
    "section_placement_opening",
    "section_placement_middle",
    "section_placement_closing",
}
AV_DIMENSIONS = {
    "voiceover_matches_visuals",
    "abrupt_cutoffs_voiceover",
    "abrupt_cutoffs_video",
}


def _percentile(values: list[float], q: float) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _unit_weight(unit: dict[str, Any]) -> float:
    return 1.0 if unit.get("unit_type") == "edit_boundary" else max(
        1e-6, float(unit.get("duration_seconds") or 0.0)
    )


def _rubric_summary(
    entries: list[dict[str, Any]], coverage: dict[str, Any],
) -> dict[str, Any]:
    valid = [entry for entry in entries if entry.get("valid") and entry.get("score") is not None]
    if not valid:
        return {
            "score_1_to_5": None, "mean": None, "minimum": None, "p20": None,
            "variance": None, "severe_fraction": None, "affected_duration_fraction": None,
            "coverage": coverage.get("coverage", 0.0), "n_valid": 0,
            "n_selected": coverage.get("selected", 0), "n_total": coverage.get("total", 0),
        }
    weights = [_unit_weight(entry) for entry in valid]
    scores = [float(entry["score"]) for entry in valid]
    weight_total = sum(weights)
    weighted_mean = sum(score * weight for score, weight in zip(scores, weights)) / weight_total
    critical = any(
        entry.get("severity") == "critical" or float(entry["score"]) <= 1.0 for entry in valid
    )
    major_weight = sum(
        weight for entry, weight in zip(valid, weights)
        if entry.get("severity") == "major" or float(entry["score"]) <= 2.0
    )
    major_fraction = major_weight / weight_total
    cap = 2.0 if critical else (3.0 if major_fraction >= 0.2 else 5.0)
    return {
        "score_1_to_5": min(weighted_mean, cap),
        "weighted_mean_before_cap": weighted_mean,
        "severe_error_cap": cap,
        "mean": mean(scores),
        "minimum": min(scores),
        "p20": _percentile(scores, 0.2),
        "variance": pvariance(scores) if len(scores) > 1 else 0.0,
        "severe_fraction": sum(score <= 2 for score in scores) / len(scores),
        "affected_duration_fraction": major_fraction,
        "coverage": coverage.get("coverage", 0.0),
        "n_valid": len(valid),
        "n_selected": coverage.get("selected", 0),
        "n_total": coverage.get("total", 0),
    }


def _weighted_rubric_score(
    summaries: dict[str, dict[str, Any]], weights: dict[str, float],
) -> float | None:
    usable = [
        (float(summary["score_1_to_5"]), weights.get(rubric, 1.0))
        for rubric, summary in summaries.items()
        if summary.get("score_1_to_5") is not None and weights.get(rubric, 0.0) > 0
    ]
    if not usable:
        return None
    return sum(score * weight for score, weight in usable) / sum(weight for _, weight in usable)


def aggregate_area_results(
    area_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(judge_result, decomposition_features)`` across fan-in result bundles."""
    merged: dict[str, dict[str, Any]] = {}
    for bundle in area_results:
        for item_id, result in (bundle or {}).items():
            target = merged.setdefault(item_id, {"rubrics": {}, "evidence_hashes": set()})
            rubric_id = result.get("rubric_id")
            if rubric_id:
                target["rubrics"][rubric_id] = result
            if result.get("evidence_hash"):
                target["evidence_hashes"].add(result["evidence_hash"])

    judge_result: dict[str, Any] = {}
    features: dict[str, Any] = {}
    for item_id, item in merged.items():
        summaries: dict[str, dict[str, Any]] = {}
        all_units: list[dict[str, Any]] = []
        for rubric_id, rubric_result in item["rubrics"].items():
            entries = rubric_result.get("units") or []
            summaries[rubric_id] = _rubric_summary(
                entries, rubric_result.get("selection") or {}
            )
            all_units.extend(entries)

        edit_score = _weighted_rubric_score(summaries, RUBRIC_WEIGHTS)
        av_score = _weighted_rubric_score(summaries, {
            "transition_smoothness": 0.2,
            "visual_quality_temporal_stability": 0.3,
            "pacing_narrative_coherence": 0.1,
            "audio_continuity_av_sync": 0.4,
        })
        entries: dict[str, Any] = {}
        for dimension in sorted(EDIT_DIMENSIONS):
            entries[f"area::{dimension}"] = {
                "judge": "Edit-aware area aggregation",
                "metric_id": "AREA_EDIT",
                "spec_kind": "area_aggregate",
                "parsed": {"score_1_to_5": edit_score, "rubrics": summaries},
                "align": {"dimension": dimension, "score_path": "score_1_to_5"},
                "units": all_units,
                "valid": edit_score is not None,
            }
        for dimension in sorted(AV_DIMENSIONS):
            entries[f"area::{dimension}"] = {
                "judge": "Edit-aware AV aggregation",
                "metric_id": "AREA_AV",
                "spec_kind": "area_aggregate",
                "parsed": {"score_1_to_5": av_score, "rubrics": summaries},
                "align": {"dimension": dimension, "score_path": "score_1_to_5"},
                "units": all_units,
                "valid": av_score is not None,
            }
        judge_result[item_id] = entries

        flat: dict[str, float] = {}
        for rubric_id, summary in summaries.items():
            for key in (
                "score_1_to_5", "mean", "minimum", "p20", "variance",
                "severe_fraction", "affected_duration_fraction", "coverage",
            ):
                value = summary.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    flat[f"area:{rubric_id}:{key}"] = float(value)
        features[item_id] = {
            "item_id": item_id,
            "evidence_hashes": sorted(item["evidence_hashes"]),
            "features": flat,
            "rubric_summaries": summaries,
        }
    return judge_result, features
