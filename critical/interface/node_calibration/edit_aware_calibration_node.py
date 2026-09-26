"""Regularized video-level calibration over whole-video and decomposition features."""

from __future__ import annotations

import copy
from statistics import mean
from typing import Any, Optional

import numpy as np

from ... import config
from ...core.calibration.registry import CalibrationRegistry
from ...core.eval import metrics
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...postprocessing.align import judge_signal_for_dimension
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .evaluation_support import stable_holdout_split


def _label_target(label: Any, dimension: str) -> Optional[float]:
    scores = getattr(label, "scores", None)
    raw_scores = getattr(label, "raw_scores", None)
    if isinstance(label, dict):
        scores = label.get("scores")
        raw_scores = label.get("raw_scores")
    value = (scores or {}).get(dimension)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raw = [
        float(entry) for entry in (raw_scores or {}).get(dimension, [])
        if isinstance(entry, (int, float)) and not isinstance(entry, bool)
    ]
    return mean(raw) if raw else None


def _human_rater_variance(label: Any, dimension: str) -> Optional[float]:
    raw_scores = getattr(label, "raw_scores", None)
    if isinstance(label, dict):
        raw_scores = label.get("raw_scores")
    raw = [
        float(entry) for entry in (raw_scores or {}).get(dimension, [])
        if isinstance(entry, (int, float)) and not isinstance(entry, bool)
    ]
    return float(np.var(raw)) if len(raw) > 1 else None


def _merge_judge_results(value: Any) -> dict[str, dict[str, Any]]:
    sources = value if isinstance(value, list) else [value]
    merged: dict[str, dict[str, Any]] = {}
    for source in sources:
        for item_id, entries in (source or {}).items():
            merged.setdefault(item_id, {}).update(copy.deepcopy(entries))
    return merged


def _feature_rows(
    samples: dict[str, Any], judge_results: dict[str, Any],
    decomposition_features: dict[str, Any], dimension: str,
) -> tuple[list[str], dict[str, list[float]], list[str]]:
    scalar_names = sorted({
        name
        for record in decomposition_features.values()
        for name, value in (record.get("features") or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    })
    categories = sorted({
        str(sample.get("use_case") or "unknown") for sample in samples.values()
    })
    names = ["base_score", *scalar_names, *[f"category:{value}" for value in categories]]
    rows: dict[str, list[float]] = {}
    for item_id in sorted(set(samples) & set(judge_results)):
        base = judge_signal_for_dimension(judge_results[item_id], dimension)
        if base is None:
            continue
        scalars = (decomposition_features.get(item_id) or {}).get("features") or {}
        category = str(samples[item_id].get("use_case") or "unknown")
        rows[item_id] = [
            float(base),
            *[float(scalars.get(name, 0.0)) for name in scalar_names],
            *[1.0 if category == value else 0.0 for value in categories],
        ]
    return names, rows, categories


def _fit_ridge(X: list[list[float]], y: list[float]) -> Any:
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X, y)


def _repeat_disagreement(entries: dict[str, Any]) -> float:
    values: list[float] = []
    for entry in entries.values():
        repeats = entry.get("repeat_scores") if isinstance(entry, dict) else None
        if isinstance(repeats, list):
            clean = [
                float(value) for value in repeats
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if len(clean) > 1:
                values.append(float(np.std(clean)))
    return mean(values) if values else 0.0


def _novelty_and_influence(
    item_ids: list[str], training_ids: list[str], decomposition_features: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    names = sorted({
        name for record in decomposition_features.values()
        for name, value in (record.get("features") or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    })
    if not names:
        zeros = {item_id: 0.0 for item_id in item_ids}
        return zeros, dict(zeros)
    matrix = np.asarray([
        [
            float((decomposition_features.get(item_id) or {}).get("features", {}).get(name, 0.0))
            for name in names
        ]
        for item_id in item_ids
    ])
    train_indexes = [item_ids.index(item_id) for item_id in training_ids if item_id in item_ids]
    train = matrix[train_indexes] if train_indexes else matrix
    center = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale < 1e-9] = 1.0
    standardized = (matrix - center) / scale
    novelty = np.linalg.norm(standardized, axis=1) / max(1.0, np.sqrt(len(names)))
    gram_inverse = np.linalg.pinv(standardized[train_indexes].T @ standardized[train_indexes] + np.eye(len(names)))
    influence = np.asarray([
        float(row @ gram_inverse @ row.T) for row in standardized
    ])
    return (
        {item_id: float(novelty[index]) for index, item_id in enumerate(item_ids)},
        {item_id: float(influence[index]) for index, item_id in enumerate(item_ids)},
    )


def _normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if high - low < 1e-12:
        return {key: 0.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def _bootstrap_intervals(
    train_X: list[list[float]], train_y: list[float],
    predict_X: list[list[float]], *, repeats: int, seed: int,
) -> tuple[list[float], list[tuple[float, float]], list[float]]:
    model = _fit_ridge(train_X, train_y)
    central = [float(value) for value in model.predict(predict_X)]
    if len(train_X) < 2 or repeats <= 0:
        return central, [(value, value) for value in central], [0.0] * len(central)
    rng = np.random.default_rng(seed)
    draws: list[list[float]] = []
    for _ in range(repeats):
        indexes = rng.integers(0, len(train_X), size=len(train_X))
        if len({float(train_y[index]) for index in indexes}) < 2:
            continue
        fitted = _fit_ridge(
            [train_X[index] for index in indexes],
            [train_y[index] for index in indexes],
        )
        draws.append([float(value) for value in fitted.predict(predict_X)])
    if not draws:
        return central, [(value, value) for value in central], [0.0] * len(central)
    array = np.asarray(draws)
    intervals = [
        (float(np.percentile(array[:, index], 2.5)), float(np.percentile(array[:, index], 97.5)))
        for index in range(array.shape[1])
    ]
    std = [float(value) for value in np.std(array, axis=0)]
    return central, intervals, std


@register
class EditAwareCalibrationNodeExecutor(NodeExecutor):
    node_type = "edit_aware_calibration"
    category = "node_calibration"
    subcategory = "model"
    input_sockets = {
        "samples": "samples",
        "judge_result": "judge_result",
        "labels": "labels",
        "decomposition_features": "decomposition_features",
        "unit_labels": "unit_labels",
    }
    multi_input_sockets = frozenset({"judge_result"})
    output_sockets = {
        "judge_result": "judge_result",
        "judge_rule": "judge_rule",
        "active_labeling_report": "active_labeling_report",
    }
    param_schema = {
        "validation_fraction": {"type": "number", "default": 0.2, "min": 0.1, "max": 0.5},
        "split_seed": {"type": "number", "default": 0, "min": 0},
        "bootstrap_repeats": {"type": "number", "default": 1000, "min": 0},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        incoming_judges = ctx.inputs.get("judge_result")
        labels = ctx.inputs.get("labels")
        decomposition_features = ctx.inputs.get("decomposition_features")
        for name, value in (
            ("samples", samples), ("judge_result", incoming_judges),
            ("labels", labels), ("decomposition_features", decomposition_features),
        ):
            if value is None:
                return NodeRunResult(
                    status="error", error=f"Edit-Aware Calibration requires '{name}'."
                )
        judge_results = _merge_judge_results(incoming_judges)
        overlap = sorted(set(samples) & set(judge_results) & set(labels))
        if len(overlap) < 2:
            return NodeRunResult(
                status="error",
                error="Edit-Aware Calibration needs at least two overlapping labeled videos.",
            )
        training_ids, validation_ids = stable_holdout_split(
            overlap,
            validation_fraction=float(ctx.params.get("validation_fraction") or 0.2),
            split_seed=int(ctx.params.get("split_seed") or 0),
        )
        if ctx.dry_run:
            return NodeRunResult(
                outputs={
                    "judge_result": {},
                    "judge_rule": {},
                    "active_labeling_report": {"items": []},
                },
                meta={
                    "dry_run": True, "n_items": len(overlap),
                    "n_training": len(training_ids), "n_validation": len(validation_ids),
                },
            )

        calibrated: dict[str, dict[str, Any]] = {}
        model_reports: dict[str, Any] = {}
        active_components: dict[str, list[float]] = {item_id: [] for item_id in overlap}
        repeats = int(ctx.params.get("bootstrap_repeats", 1000))
        seed = int(ctx.params.get("split_seed") or 0)
        for dimension in HUMAN_DIMENSIONS:
            feature_names, feature_rows, _categories = _feature_rows(
                samples, judge_results, decomposition_features, dimension
            )
            targets = {
                item_id: target
                for item_id in overlap
                if item_id in feature_rows
                and (target := _label_target(labels[item_id], dimension)) is not None
            }
            train = [item_id for item_id in training_ids if item_id in targets]
            valid = [item_id for item_id in validation_ids if item_id in targets]
            if len(train) < 2 or not valid:
                continue
            train_X = [feature_rows[item_id] for item_id in train]
            train_y = [float(targets[item_id]) for item_id in train]
            predict_ids = [item_id for item_id in overlap if item_id in feature_rows]
            predicted, intervals, stds = _bootstrap_intervals(
                train_X, train_y, [feature_rows[item_id] for item_id in predict_ids],
                repeats=repeats, seed=seed + HUMAN_DIMENSIONS.index(dimension),
            )
            predictions = {
                item_id: min(5.0, max(1.0, predicted[index]))
                for index, item_id in enumerate(predict_ids)
            }
            interval_map = {
                item_id: (
                    min(5.0, max(1.0, intervals[index][0])),
                    min(5.0, max(1.0, intervals[index][1])),
                )
                for index, item_id in enumerate(predict_ids)
            }
            for index, item_id in enumerate(predict_ids):
                active_components[item_id].append(stds[index])
                if item_id not in set(valid):
                    continue
                calibrated.setdefault(item_id, {})[f"calibrated::{dimension}"] = {
                    "judge": "Edit-aware ridge calibration",
                    "metric_id": "EDIT_CAL",
                    "spec_kind": "calibration",
                    "parsed": {
                        "score_1_to_5": predictions[item_id],
                        "prediction_interval_95": list(interval_map[item_id]),
                    },
                    "align": {"dimension": dimension, "score_path": "score_1_to_5"},
                    "valid": True,
                }
            valid_human = [float(targets[item_id]) for item_id in valid]
            valid_base = [
                float(feature_rows[item_id][0]) for item_id in valid
            ]
            valid_pred = [predictions[item_id] for item_id in valid]
            fitted = _fit_ridge(train_X, train_y)
            ridge = fitted.named_steps["ridge"]
            model_reports[dimension] = {
                "feature_names": feature_names,
                "training_ids": train,
                "validation_ids": valid,
                "coefficient": [float(value) for value in ridge.coef_],
                "intercept": float(ridge.intercept_),
                "metrics": {
                    "base_mae": metrics.mae(valid_human, valid_base),
                    "calibrated_mae": metrics.mae(valid_human, valid_pred),
                    "base_rmse": metrics.rmse(valid_human, valid_base),
                    "calibrated_rmse": metrics.rmse(valid_human, valid_pred),
                    "base_spearman": metrics.spearman(valid_human, valid_base),
                    "calibrated_spearman": metrics.spearman(valid_human, valid_pred),
                    "base_qwk": metrics.quadratic_weighted_kappa(valid_human, valid_base),
                    "calibrated_qwk": metrics.quadratic_weighted_kappa(
                        valid_human, valid_pred
                    ),
                },
                "predictions": {
                    item_id: {
                        "human": targets[item_id],
                        "base": feature_rows[item_id][0],
                        "calibrated": predictions[item_id],
                        "interval_95": list(interval_map[item_id]),
                        "calibration_std": stds[predict_ids.index(item_id)],
                        "human_rater_variance": _human_rater_variance(
                            labels[item_id], dimension
                        ),
                        "judge_repeat_variance": (
                            _repeat_disagreement(judge_results[item_id]) ** 2
                        ),
                    }
                    for item_id in valid
                },
            }

        if not model_reports:
            return NodeRunResult(
                status="error",
                error="No human dimension had at least two training items and one validation item.",
            )
        uncertainty = {
            item_id: mean(values) if values else 0.0
            for item_id, values in active_components.items()
        }
        novelty, influence = _novelty_and_influence(
            overlap, training_ids, decomposition_features
        )
        disagreement = {
            item_id: _repeat_disagreement(judge_results.get(item_id) or {})
            for item_id in overlap
        }
        normalized_uncertainty = _normalize(uncertainty)
        normalized_novelty = _normalize(novelty)
        normalized_influence = _normalize(influence)
        normalized_disagreement = _normalize(disagreement)
        active_items = [
            {
                "item_id": item_id,
                "predictive_uncertainty": uncertainty[item_id],
                "judge_repeat_disagreement": disagreement[item_id],
                "feature_novelty": novelty[item_id],
                "expected_model_influence": influence[item_id],
                "priority": mean([
                    normalized_uncertainty[item_id],
                    normalized_disagreement[item_id],
                    normalized_novelty[item_id],
                    normalized_influence[item_id],
                ]),
                "reasons": [
                    reason for reason, present in (
                        ("wide_calibration_interval", normalized_uncertainty[item_id] >= 0.5),
                        ("judge_disagreement", normalized_disagreement[item_id] >= 0.5),
                        ("feature_novelty", normalized_novelty[item_id] >= 0.5),
                        ("high_model_influence", normalized_influence[item_id] >= 0.5),
                    ) if present
                ],
            }
            for item_id in overlap
        ]
        active_items.sort(key=lambda item: (-item["priority"], item["item_id"]))
        report = {
            "version": "edit-aware-ridge-v1",
            "split": {
                "training_ids": training_ids,
                "validation_ids": validation_ids,
                "validation_fraction": float(ctx.params.get("validation_fraction") or 0.2),
                "split_seed": seed,
            },
            "bootstrap_repeats": repeats,
            "models": model_reports,
            "unit_annotation_count": len(ctx.inputs.get("unit_labels") or []),
            "uncertainty": {
                "calibration": "grouped item bootstrap",
                "judge_repeat": "not available unless repeated judge results are supplied",
                "human_rater": "retained in labels.raw_scores; reported by Eval",
            },
        }
        registry = CalibrationRegistry(config.EVIDENCE_ROOT / "calibration_registry")
        version, path = registry.publish(report)
        report["registry_version"] = version
        report["registry_path"] = str(path)
        active_report = {
            "version": "active-labeling-v1",
            "items": active_items,
            "signals": [
                "predictive_interval_width",
                "judge_disagreement_when_available",
                "feature_novelty_when_available",
                "expected_model_influence_when_available",
            ],
            "mutates_dataset": False,
        }
        return NodeRunResult(
            outputs={
                "judge_result": calibrated,
                "judge_rule": report,
                "active_labeling_report": active_report,
            },
            meta={
                "n_training": len(training_ids),
                "n_validation": len(validation_ids),
                "n_dimensions": len(model_reports),
                "registry_version": version,
            },
        )
