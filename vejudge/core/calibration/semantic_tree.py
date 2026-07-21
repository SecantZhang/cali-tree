"""Ontology-weighted semantic decision tree calibrator.

Adapts the Semantic Decision Tree idea (Adv. Eng. Informatics 58, 2023 — ID3 split gain
adjusted by ontology-derived attribute importance) to our regression setting: a compact,
greedy, shallow tree over concept-labeled features (``base_score`` + ``fm:<concept>`` counts
+ ``rule:<concept>`` critic booleans) mapping to the human score. At each node it picks the
split maximizing ``importance(feature) * variance_reduction`` — so a concept the ontology
says is relevant to the metric being calibrated is preferred over an equally-predictive but
off-topic one. sklearn can't weight per-feature gain, so the tree is implemented directly;
it stays depth-2 (like the CART baseline) because the labeled batch is tiny.

Importance is injected as a ``feature_weights`` map (feature name → weight in (0, 1]); the
node builds it from ``ontology.concept_importance``. Keeping the ontology out of the
calibrator makes the split rule pure and unit-testable. ``metadata()['tree']`` matches
``DecisionTreeCalibrator``'s ``_export_tree_dict`` shape so the existing UI renders it.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .base import Calibrator


def _weighted_mean(ys: list[float], weights: list[float]) -> float:
    total = sum(weights)
    return sum(y * w for y, w in zip(ys, weights)) / total if total > 0 else 0.0


def _variance(ys: list[float], weights: Optional[list[float]] = None) -> float:
    if not ys:
        return 0.0
    ws = weights or [1.0] * len(ys)
    total = sum(ws)
    if total <= 0:
        return 0.0
    m = _weighted_mean(ys, ws)
    return sum(w * (y - m) ** 2 for y, w in zip(ys, ws)) / total


class SemanticDecisionTreeCalibrator(Calibrator):
    version = "semantic-tree-v2-weighted"

    def __init__(
        self,
        *,
        feature_weights: Optional[dict[str, float]] = None,
        max_depth: int = 2,
        min_samples_leaf: int = 2,
    ) -> None:
        self.feature_weights = dict(feature_weights or {})
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self._feature_names: Optional[list[str]] = None
        self._tree: Optional[dict[str, Any]] = None

    def _weight(self, feature_name: str) -> float:
        # Unlisted features (e.g. base_score) default to full weight — the ontology only
        # de-prioritizes concepts it judges off-metric.
        return float(self.feature_weights.get(feature_name, 1.0))

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        *,
        feature_names: Optional[Sequence[str]] = None,
        sample_weight: Optional[Sequence[float]] = None,
    ) -> "SemanticDecisionTreeCalibrator":
        rows = [list(map(float, r)) for r in X]
        ys = [float(v) for v in y]
        weights = (
            [float(v) for v in sample_weight]
            if sample_weight is not None else [1.0] * len(ys)
        )
        n_feats = len(rows[0]) if rows else 0
        self._feature_names = (
            list(feature_names) if feature_names is not None else [f"x{j}" for j in range(n_feats)]
        )
        self._tree = self._build(list(range(len(rows))), rows, ys, weights, depth=0)
        return self

    def _build(
        self, idxs: list[int], rows: list[list[float]], ys: list[float],
        weights: list[float], *, depth: int,
    ) -> dict[str, Any]:
        node_ys = [ys[i] for i in idxs]
        node_weights = [weights[i] for i in idxs]
        node: dict[str, Any] = {
            "leaf": True,
            "samples": len(idxs),
            "weighted_samples": round(sum(node_weights), 3),
            "value": round(_weighted_mean(node_ys, node_weights), 3) if node_ys else 0.0,
        }
        # A split needs enough rows to leave min_samples_leaf on each side, and depth budget.
        if depth >= self.max_depth or sum(node_weights) < 2 * self.min_samples_leaf:
            return node

        best: Optional[tuple[float, int, float, list[int], list[int]]] = None
        parent_var = _variance(node_ys, node_weights)
        total_weight = sum(node_weights)
        for j in range(len(self._feature_names or [])):
            w = self._weight(self._feature_names[j])
            values = sorted({rows[i][j] for i in idxs})
            for a, b in zip(values, values[1:]):
                thr = (a + b) / 2
                left = [i for i in idxs if rows[i][j] <= thr]
                right = [i for i in idxs if rows[i][j] > thr]
                if (
                    sum(weights[i] for i in left) < self.min_samples_leaf
                    or sum(weights[i] for i in right) < self.min_samples_leaf
                ):
                    continue
                left_weight = sum(weights[i] for i in left)
                right_weight = sum(weights[i] for i in right)
                child_var = (
                    left_weight / total_weight
                    * _variance([ys[i] for i in left], [weights[i] for i in left])
                    + right_weight / total_weight
                    * _variance([ys[i] for i in right], [weights[i] for i in right])
                )
                weighted_gain = w * (parent_var - child_var)
                # Strictly-better wins; ties keep the earlier (lower-index) feature for
                # determinism. The ontology weight is what breaks a variance tie between two
                # equally-predictive features.
                if weighted_gain > 0 and (best is None or weighted_gain > best[0]):
                    best = (weighted_gain, j, thr, left, right)

        if best is None:
            return node

        _gain, j, thr, left, right = best
        return {
            "leaf": False,
            "samples": len(idxs),
            "weighted_samples": round(sum(node_weights), 3),
            "value": round(_weighted_mean(node_ys, node_weights), 3),
            "feature": self._feature_names[j],
            "threshold": round(thr, 3),
            "left": self._build(left, rows, ys, weights, depth=depth + 1),
            "right": self._build(right, rows, ys, weights, depth=depth + 1),
        }

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        if self._tree is None:
            raise RuntimeError("SemanticDecisionTreeCalibrator.fit must be called before predict")
        names = self._feature_names or []
        idx_of = {name: j for j, name in enumerate(names)}
        out: list[float] = []
        for row in X:
            node = self._tree
            while not node["leaf"]:
                j = idx_of[node["feature"]]
                node = node["left"] if float(row[j]) <= node["threshold"] else node["right"]
            out.append(float(node["value"]))
        return out

    def _rule_text(self, node: dict[str, Any], depth: int = 0) -> str:
        pad = "|   " * depth
        if node["leaf"]:
            return f"{pad}|--- value: [{node['value']}]\n"
        f, t = node["feature"], node["threshold"]
        return (
            f"{pad}|--- {f} <= {t}\n{self._rule_text(node['left'], depth + 1)}"
            f"{pad}|--- {f} >  {t}\n{self._rule_text(node['right'], depth + 1)}"
        )

    def metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "version": self.version,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
        }
        if self._tree is not None:
            meta["tree"] = self._tree
            meta["rule_text"] = self._rule_text(self._tree)
            # The ontology importance actually applied to each feature (auditable).
            meta["feature_importances"] = [
                self._weight(n) for n in (self._feature_names or [])
            ]
        return meta
