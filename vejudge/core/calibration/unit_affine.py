"""Small-data Bayesian affine calibration for optional unit annotations."""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any


def _unit_index(area_results: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for bundle in area_results:
        for item_id, result in (bundle or {}).items():
            rubric_id = result.get("rubric_id")
            for unit in result.get("units") or []:
                if rubric_id and unit.get("unit_id"):
                    index[(item_id, rubric_id, unit["unit_id"])] = unit
    return index


def fit_unit_calibrators(
    area_results: list[dict[str, Any]], unit_labels: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index = _unit_index(area_results)
    grouped: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for label in unit_labels:
        key = (
            str(label.get("item_id") or ""),
            str(label.get("rubric_id") or ""),
            str(label.get("unit_id") or ""),
        )
        unit = index.get(key)
        rating = label.get("rating")
        if (
            unit is None or not unit.get("valid")
            or not isinstance(unit.get("score"), (int, float))
            or not isinstance(rating, (int, float))
            or isinstance(rating, bool)
            or not 1 <= float(rating) <= 5
        ):
            continue
        grouped[key[1]].append((float(unit["score"]), float(rating), key[0]))

    models: dict[str, dict[str, Any]] = {}
    for rubric_id, rows in grouped.items():
        unique_items = {row[2] for row in rows}
        unique_targets = {row[1] for row in rows}
        active = len(rows) >= 5 and len(unique_items) >= 3 and len(unique_targets) >= 2
        if not active:
            models[rubric_id] = {
                "active": False,
                "predict": None,
                "metadata": {
                    "version": "unit-affine-bayesian-v1",
                    "status": "identity",
                    "n_annotations": len(rows),
                    "n_videos": len(unique_items),
                    "n_target_values": len(unique_targets),
                },
            }
            continue
        from sklearn.linear_model import BayesianRidge

        estimator = BayesianRidge().fit([[row[0]] for row in rows], [row[1] for row in rows])
        models[rubric_id] = {
            "active": True,
            "predict": estimator,
            "metadata": {
                "version": "unit-affine-bayesian-v1",
                "status": "fitted",
                "n_annotations": len(rows),
                "n_videos": len(unique_items),
                "n_target_values": len(unique_targets),
                "coefficient": float(estimator.coef_[0]),
                "intercept": float(estimator.intercept_),
                "noise_precision": float(estimator.alpha_),
            },
        }
    return models


def calibrate_area_result_units(
    area_results: list[dict[str, Any]], models: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    calibrated = copy.deepcopy(area_results)
    for bundle in calibrated:
        for result in (bundle or {}).values():
            model = models.get(result.get("rubric_id"))
            if not model or not model.get("active"):
                continue
            estimator = model["predict"]
            for unit in result.get("units") or []:
                if not unit.get("valid") or not isinstance(unit.get("score"), (int, float)):
                    continue
                raw = float(unit["score"])
                predicted, std = estimator.predict([[raw]], return_std=True)
                score = min(5.0, max(1.0, float(predicted[0])))
                unit["raw_score"] = raw
                unit["score"] = score
                unit["calibrated_score"] = score
                unit["calibration_std"] = float(std[0])
                if isinstance(unit.get("parsed"), dict):
                    unit["parsed"]["score_1_to_5"] = score
    return calibrated
