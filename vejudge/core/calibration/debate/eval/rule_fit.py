"""Shared fit + in-sample/LOO evaluation of the rule calibrators.

Given per-item base judge scores, human anchors, and feature vectors
``[base_score, b1..bK]``, fit four comparators and report MAE both in-sample and
leave-one-out: (a) base only, (b) base + global bias, (c) linear over base+booleans,
(d) shallow decision tree over base+booleans. LOO is the honest read at small n; if the
booleans add nothing, (c)/(d) collapse toward (b).
"""

from __future__ import annotations

from statistics import mean
from typing import Optional

from ...linear import LinearCalibrator
from ...tree import DecisionTreeCalibrator


def mae(preds: list[Optional[float]], truth: list[Optional[float]]) -> Optional[float]:
    pairs = [(p, t) for p, t in zip(preds, truth) if p is not None and t is not None]
    return mean(abs(p - t) for p, t in pairs) if pairs else None


def _predict_bias(base_fit: list[float], human_fit: list[float], base_query: float) -> float:
    """(b) base + mean residual on the fit set — the pure global bias correction."""
    resid = [h - b for b, h in zip(base_fit, human_fit)]
    return base_query + (mean(resid) if resid else 0.0)


def fit_and_evaluate(
    *,
    item_ids: list[str],
    bases: dict[str, float],
    humans: dict[str, float],
    feats_full: dict[str, list[float]],
    feature_names: list[str],
) -> dict:
    """Return the report dict: in-sample + LOO MAE per comparator, the fitted tree rule
    text, and feature importances. ``feats_full[i] == [base_i, b1_i..bK_i]``."""

    def eval_split(fit_ids: list[str], query_ids: list[str]) -> dict[str, list[float]]:
        yb = [humans[i] for i in fit_ids]
        lin = LinearCalibrator().fit([feats_full[i] for i in fit_ids], yb) if len(fit_ids) >= 2 else None
        tree = (
            DecisionTreeCalibrator().fit([feats_full[i] for i in fit_ids], yb, feature_names=feature_names)
            if len(fit_ids) >= 2 else None
        )
        preds: dict[str, list[float]] = {"base": [], "bias": [], "linear": [], "tree": []}
        for q in query_ids:
            preds["base"].append(bases[q])
            preds["bias"].append(_predict_bias([bases[i] for i in fit_ids], yb, bases[q]))
            preds["linear"].append(lin.predict([feats_full[q]])[0] if lin else bases[q])
            preds["tree"].append(tree.predict([feats_full[q]])[0] if tree else bases[q])
        return preds

    truth = [humans[i] for i in item_ids]
    insample = eval_split(item_ids, item_ids)
    insample_mae = {k: mae(v, truth) for k, v in insample.items()}

    loo = {k: [] for k in ("base", "bias", "linear", "tree")}
    for held in item_ids:
        rest = [i for i in item_ids if i != held]
        one = eval_split(rest, [held])
        for k in loo:
            loo[k].append(one[k][0])
    loo_mae = {k: mae(v, truth) for k, v in loo.items()}

    tree_full = (
        DecisionTreeCalibrator().fit([feats_full[i] for i in item_ids],
                                     [humans[i] for i in item_ids], feature_names=feature_names)
        if len(item_ids) >= 2 else None
    )
    meta = tree_full.metadata() if tree_full else {}
    return {
        "n_items": len(item_ids),
        "feature_names": feature_names,
        "insample_mae": insample_mae,
        "loo_mae": loo_mae,
        "tree_rule": meta.get("rule_text", ""),
        "feature_importances": meta.get("feature_importances", []),
    }
