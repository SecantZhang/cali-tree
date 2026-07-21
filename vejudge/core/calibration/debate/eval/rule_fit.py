"""Weighted fitting and leakage-aware evaluation for rule calibrators."""

from __future__ import annotations

from statistics import mean
from typing import Callable, Optional

from ...base import Calibrator
from ...linear import LinearCalibrator
from ...tree import DecisionTreeCalibrator


def mae(preds: list[Optional[float]], truth: list[Optional[float]]) -> Optional[float]:
    pairs = [(p, t) for p, t in zip(preds, truth) if p is not None and t is not None]
    return mean(abs(p - t) for p, t in pairs) if pairs else None


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total if total else 0.0


def _predict_bias(
    base_fit: list[float], human_fit: list[float], fit_weights: list[float], base_query: float,
) -> float:
    residuals = [h - b for b, h in zip(base_fit, human_fit)]
    return base_query + _weighted_mean(residuals, fit_weights)


def _macro_item_mae(
    ids: list[str], predictions: list[float], humans: dict[str, float], groups: dict[str, str],
) -> tuple[Optional[float], dict[str, float]]:
    errors: dict[str, list[float]] = {}
    for obs_id, pred in zip(ids, predictions):
        errors.setdefault(groups[obs_id], []).append(abs(pred - humans[obs_id]))
    per_item = {item: mean(values) for item, values in errors.items() if values}
    return (mean(per_item.values()) if per_item else None), per_item


def fit_and_evaluate(
    *,
    item_ids: list[str],
    bases: dict[str, float],
    humans: dict[str, float],
    feats_full: dict[str, list[float]],
    feature_names: list[str],
    loo_groups: Optional[dict[str, str]] = None,
    observation_weights: Optional[dict[str, float]] = None,
    train_groups: Optional[list[str]] = None,
    validation_groups: Optional[list[str]] = None,
    extra_calibrators: Optional[dict[str, Callable[[], Calibrator]]] = None,
) -> dict:
    """Fit weighted comparators and report item-macro error.

    With ``train_groups``/``validation_groups``, one frozen model is trained only on the
    training videos and evaluated on the disjoint validation videos. Without them, the
    legacy grouped-LOO behavior is retained. Raw ratings remain separate observations,
    while their weights sum to one per source video.
    """
    extra = extra_calibrators or {}
    comparators = ["base", "bias", "linear", "tree", *extra.keys()]
    groups = loo_groups or {i: i for i in item_ids}
    weights = observation_weights or {i: 1.0 for i in item_ids}
    group_order = list(dict.fromkeys(groups[i] for i in item_ids))

    def eval_split(fit_ids: list[str], query_ids: list[str]) -> dict[str, list[float]]:
        y_fit = [humans[i] for i in fit_ids]
        w_fit = [weights[i] for i in fit_ids]
        X_fit = [feats_full[i] for i in fit_ids]
        can_fit = len({groups[i] for i in fit_ids}) >= 2
        lin = (
            LinearCalibrator().fit(X_fit, y_fit, sample_weight=w_fit) if can_fit else None
        )
        tree = (
            DecisionTreeCalibrator().fit(
                X_fit, y_fit, feature_names=feature_names, sample_weight=w_fit,
            ) if can_fit else None
        )
        extra_fit = {
            name: factory().fit(
                X_fit, y_fit, feature_names=feature_names, sample_weight=w_fit,
            )
            for name, factory in extra.items()
        } if can_fit else {}
        predictions: dict[str, list[float]] = {key: [] for key in comparators}
        fit_bases = [bases[i] for i in fit_ids]
        for query_id in query_ids:
            predictions["base"].append(bases[query_id])
            predictions["bias"].append(
                _predict_bias(fit_bases, y_fit, w_fit, bases[query_id])
            )
            predictions["linear"].append(
                lin.predict([feats_full[query_id]])[0] if lin else bases[query_id]
            )
            predictions["tree"].append(
                tree.predict([feats_full[query_id]])[0] if tree else bases[query_id]
            )
            for name in extra:
                model = extra_fit.get(name)
                predictions[name].append(
                    model.predict([feats_full[query_id]])[0] if model else bases[query_id]
                )
        return predictions

    def summarize(ids: list[str], predictions: dict[str, list[float]]) -> tuple[dict, dict, dict]:
        metrics: dict[str, Optional[float]] = {}
        weighted_metrics: dict[str, Optional[float]] = {}
        per_item: dict[str, dict[str, float]] = {}
        for key, values in predictions.items():
            score, item_errors = _macro_item_mae(ids, values, humans, groups)
            metrics[key] = score
            total_weight = sum(weights[item] for item in ids)
            weighted_metrics[key] = (
                sum(weights[item] * abs(pred - humans[item]) for item, pred in zip(ids, values))
                / total_weight if total_weight else None
            )
            for item, error in item_errors.items():
                per_item.setdefault(item, {})[key] = error
        return metrics, per_item, weighted_metrics

    evaluation_mode = "grouped_loo_exploratory"
    insample_mae: dict[str, Optional[float]] = {}
    insample_weighted_mae: dict[str, Optional[float]] = {}
    insample_errors: dict[str, dict[str, float]] = {}
    validation_mae: dict[str, Optional[float]] = {}
    validation_weighted_mae: dict[str, Optional[float]] = {}
    validation_errors: dict[str, dict[str, float]] = {}
    validation_predictions: dict[str, list[float]] = {}
    effective_train = group_order
    effective_validation = group_order

    if train_groups is not None and validation_groups is not None:
        evaluation_mode = "frozen_holdout"
        train_set, validation_set = set(train_groups), set(validation_groups)
        train_ids = [i for i in item_ids if groups[i] in train_set]
        validation_ids = [i for i in item_ids if groups[i] in validation_set]
        train_predictions = eval_split(train_ids, train_ids)
        insample_mae, insample_errors, insample_weighted_mae = summarize(
            train_ids, train_predictions,
        )
        validation_predictions = eval_split(train_ids, validation_ids)
        validation_mae, validation_errors, validation_weighted_mae = summarize(
            validation_ids, validation_predictions,
        )
        effective_train = list(train_groups)
        effective_validation = list(validation_groups)
    else:
        all_predictions = eval_split(item_ids, item_ids)
        insample_mae, insample_errors, insample_weighted_mae = summarize(
            item_ids, all_predictions,
        )
        loo_predictions = {key: [] for key in comparators}
        loo_ids: list[str] = []
        for held_group in group_order:
            held = [i for i in item_ids if groups[i] == held_group]
            rest = [i for i in item_ids if groups[i] != held_group]
            fold = eval_split(rest, held)
            loo_ids.extend(held)
            for key in comparators:
                loo_predictions[key].extend(fold[key])
        validation_predictions = loo_predictions
        validation_mae, validation_errors, validation_weighted_mae = summarize(
            loo_ids, loo_predictions,
        )

    fit_group_set = set(effective_train)
    display_fit_ids = [i for i in item_ids if groups[i] in fit_group_set]
    display_weights = [weights[i] for i in display_fit_ids]
    tree_full = (
        DecisionTreeCalibrator().fit(
            [feats_full[i] for i in display_fit_ids],
            [humans[i] for i in display_fit_ids],
            feature_names=feature_names,
            sample_weight=display_weights,
        ) if len(fit_group_set) >= 2 else None
    )
    meta = tree_full.metadata() if tree_full else {}
    return {
        "n_items": len(group_order),
        "n_observations": len(item_ids),
        "evaluation_mode": evaluation_mode,
        "train_item_ids": effective_train,
        "validation_item_ids": effective_validation,
        "n_train_items": len(effective_train),
        "n_validation_items": len(effective_validation),
        "feature_names": feature_names,
        "insample_mae": insample_mae,
        "insample_weighted_mae": insample_weighted_mae,
        # Compatibility: existing panels/readers use loo_mae as the held-out column.
        "loo_mae": validation_mae,
        "validation_mae": validation_mae,
        "validation_weighted_mae": validation_weighted_mae,
        "per_item_errors": validation_errors,
        "tree_rule": meta.get("rule_text", ""),
        "tree": meta.get("tree"),
        "feature_importances": meta.get("feature_importances", []),
    }
