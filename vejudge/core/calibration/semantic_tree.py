"""Ontology-weighted semantic decision tree calibrator.

Adapts the Semantic Decision Tree idea (Adv. Eng. Informatics 58, 2023 — ID3 split gain
adjusted by ontology-derived attribute importance) to our regression setting: a compact,
greedy tree over concept-labeled features (``base_score`` plus graded semantic evidence)
mapping to the human score. At each node it picks the split maximizing ontology-weighted
absolute-error reduction — so a concept the ontology
says is relevant to the metric being calibrated is preferred over an equally-predictive but
off-topic one. sklearn can't weight per-feature gain, so the tree is implemented directly;
it can represent several semantic decisions while robust median leaves optimize the primary
item-macro MAE objective directly.

Importance is injected as a ``feature_weights`` map (feature name → weight in (0, 1]); the
node builds it from ``ontology.concept_importance``. Keeping the ontology out of the
calibrator makes the split rule pure and unit-testable. ``metadata()['tree']`` matches
``DecisionTreeCalibrator``'s ``_export_tree_dict`` shape so the existing UI renders it.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .base import Calibrator


def _weighted_median(ys: list[float], weights: list[float]) -> float:
    if not ys:
        return 0.0
    ordered = sorted(zip(ys, weights), key=lambda pair: pair[0])
    midpoint = sum(weights) / 2
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= midpoint:
            return value
    return ordered[-1][0]


def _absolute_error(ys: list[float], weights: list[float]) -> float:
    total = sum(weights)
    if total <= 0:
        return 0.0
    center = _weighted_median(ys, weights)
    return sum(weight * abs(value - center) for value, weight in zip(ys, weights)) / total


class SemanticDecisionTreeCalibrator(Calibrator):
    version = "semantic-tree-v4-lookahead-mae"

    def __init__(
        self,
        *,
        feature_weights: Optional[dict[str, float]] = None,
        allowed_feature_names: Optional[Sequence[str]] = None,
        max_depth: int = 3,
        min_samples_leaf: int = 1,
        split_lookahead: int = 1,
    ) -> None:
        self.feature_weights = dict(feature_weights or {})
        self.allowed_feature_names = (
            set(allowed_feature_names) if allowed_feature_names is not None else None
        )
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.split_lookahead = max(0, min(1, split_lookahead))
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
            "value": round(_weighted_median(node_ys, node_weights), 3) if node_ys else 0.0,
        }
        # A split needs enough rows to leave min_samples_leaf on each side, and depth budget.
        if depth >= self.max_depth or sum(node_weights) < 2 * self.min_samples_leaf:
            return node

        best: Optional[tuple[float, float, float, int, float, list[int], list[int]]] = None
        parent_loss = _absolute_error(node_ys, node_weights)
        total_weight = sum(node_weights)
        for j in range(len(self._feature_names or [])):
            if (
                self.allowed_feature_names is not None
                and self._feature_names[j] not in self.allowed_feature_names
            ):
                continue
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
                child_loss = (
                    left_weight / total_weight
                    * _absolute_error([ys[i] for i in left], [weights[i] for i in left])
                    + right_weight / total_weight
                    * _absolute_error([ys[i] for i in right], [weights[i] for i in right])
                )
                immediate_gain = w * (parent_loss - child_loss)
                lookahead_gain = 0.0
                if self.split_lookahead and depth + 1 < self.max_depth:
                    lookahead_gain = (
                        left_weight / total_weight
                        * self._best_one_split_gain(left, rows, ys, weights)
                        + right_weight / total_weight
                        * self._best_one_split_gain(right, rows, ys, weights)
                    )
                weighted_gain = immediate_gain + lookahead_gain
                # Strictly-better wins; ties keep the earlier (lower-index) feature for
                # determinism. The ontology weight is what breaks a variance tie between two
                # equally-predictive features.
                if weighted_gain > 0 and (best is None or weighted_gain > best[0]):
                    best = (
                        weighted_gain, immediate_gain, lookahead_gain, j, thr, left, right,
                    )

        if best is None:
            return node

        gain, immediate_gain, lookahead_gain, j, thr, left, right = best
        return {
            "leaf": False,
            "samples": len(idxs),
            "weighted_samples": round(sum(node_weights), 3),
            "value": round(_weighted_median(node_ys, node_weights), 3),
            "feature": self._feature_names[j],
            "threshold": round(thr, 3),
            "weighted_gain": round(gain, 6),
            "immediate_gain": round(immediate_gain, 6),
            "lookahead_gain": round(lookahead_gain, 6),
            "left": self._build(left, rows, ys, weights, depth=depth + 1),
            "right": self._build(right, rows, ys, weights, depth=depth + 1),
        }

    def _best_one_split_gain(
        self, idxs: list[int], rows: list[list[float]], ys: list[float],
        weights: list[float],
    ) -> float:
        """Return the best ontology-weighted gain available one level below a split."""
        total_weight = sum(weights[i] for i in idxs)
        if total_weight < 2 * self.min_samples_leaf:
            return 0.0
        parent_loss = _absolute_error(
            [ys[i] for i in idxs], [weights[i] for i in idxs],
        )
        best_gain = 0.0
        for j in range(len(self._feature_names or [])):
            if (
                self.allowed_feature_names is not None
                and self._feature_names[j] not in self.allowed_feature_names
            ):
                continue
            values = sorted({rows[i][j] for i in idxs})
            for a, b in zip(values, values[1:]):
                threshold = (a + b) / 2
                left = [i for i in idxs if rows[i][j] <= threshold]
                right = [i for i in idxs if rows[i][j] > threshold]
                left_weight = sum(weights[i] for i in left)
                right_weight = sum(weights[i] for i in right)
                if (
                    left_weight < self.min_samples_leaf
                    or right_weight < self.min_samples_leaf
                ):
                    continue
                child_loss = (
                    left_weight / total_weight
                    * _absolute_error([ys[i] for i in left], [weights[i] for i in left])
                    + right_weight / total_weight
                    * _absolute_error([ys[i] for i in right], [weights[i] for i in right])
                )
                gain = self._weight(self._feature_names[j]) * (parent_loss - child_loss)
                best_gain = max(best_gain, gain)
        return best_gain

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
            "split_lookahead": self.split_lookahead,
            "allowed_feature_names": (
                sorted(self.allowed_feature_names)
                if self.allowed_feature_names is not None else None
            ),
        }
        if self._tree is not None:
            meta["tree"] = self._tree
            meta["rule_text"] = self._rule_text(self._tree)
            # The ontology importance actually applied to each feature (auditable).
            meta["feature_importances"] = [
                self._weight(n) for n in (self._feature_names or [])
            ]
        return meta
