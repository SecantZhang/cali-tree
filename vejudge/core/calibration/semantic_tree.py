"""Ontology-weighted semantic model trees.

The referenced Semantic Decision Tree paper adjusts empirical split gain with attribute
importance derived from a knowledge base. This regression adaptation does the same for
graded semantic evidence. Score controls may calibrate a regularized model inside each
leaf, but are never eligible as learned decisions; this keeps numeric shortcuts from
displacing the semantic questions that make the tree interpretable.
"""

from __future__ import annotations

from statistics import mean
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
    """A semantic-only regression tree with optional score-aware leaf models."""

    version = "semantic-tree-v5-semantic-model-leaves"

    def __init__(
        self,
        *,
        feature_weights: Optional[dict[str, float]] = None,
        allowed_feature_names: Optional[Sequence[str]] = None,
        leaf_feature_names: Optional[Sequence[str]] = None,
        leaf_ridge_alpha: float = 1.0,
        max_depth: int = 3,
        min_samples_leaf: int = 1,
        split_lookahead: int = 1,
    ) -> None:
        self.feature_weights = dict(feature_weights or {})
        self.allowed_feature_names = (
            set(allowed_feature_names) if allowed_feature_names is not None else None
        )
        self.leaf_feature_names = list(leaf_feature_names or [])
        self.leaf_ridge_alpha = max(0.0, float(leaf_ridge_alpha))
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.split_lookahead = max(0, min(1, split_lookahead))
        self._feature_names: Optional[list[str]] = None
        self._leaf_feature_indices: list[int] = []
        self._tree: Optional[dict[str, Any]] = None

    def _weight(self, feature_name: str) -> float:
        return float(self.feature_weights.get(feature_name, 1.0))

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        *,
        feature_names: Optional[Sequence[str]] = None,
        sample_weight: Optional[Sequence[float]] = None,
    ) -> "SemanticDecisionTreeCalibrator":
        rows = [list(map(float, row)) for row in X]
        ys = [float(value) for value in y]
        weights = (
            [float(value) for value in sample_weight]
            if sample_weight is not None else [1.0] * len(ys)
        )
        n_features = len(rows[0]) if rows else 0
        self._feature_names = (
            list(feature_names) if feature_names is not None
            else [f"x{index}" for index in range(n_features)]
        )
        self._leaf_feature_indices = [
            self._feature_names.index(name)
            for name in self.leaf_feature_names if name in self._feature_names
        ]
        self._tree = self._build(list(range(len(rows))), rows, ys, weights, depth=0)
        return self

    def _leaf(
        self,
        idxs: list[int],
        rows: list[list[float]],
        ys: list[float],
        weights: list[float],
    ) -> tuple[dict[str, Any], float]:
        node_ys = [ys[index] for index in idxs]
        node_weights = [weights[index] for index in idxs]
        fallback = _weighted_median(node_ys, node_weights) if node_ys else 0.0
        node: dict[str, Any] = {
            "leaf": True,
            "samples": len(idxs),
            "weighted_samples": round(sum(node_weights), 3),
            "value": round(fallback, 3),
        }
        if not self._leaf_feature_indices or len(idxs) < 2:
            return node, _absolute_error(node_ys, node_weights)

        from sklearn.linear_model import Ridge  # lazy import

        X_leaf = [[rows[index][j] for j in self._leaf_feature_indices] for index in idxs]
        model = Ridge(alpha=self.leaf_ridge_alpha).fit(
            X_leaf, node_ys, sample_weight=node_weights,
        )
        predictions = [float(value) for value in model.predict(X_leaf)]
        total = sum(node_weights)
        loss = (
            sum(
                weight * abs(target - prediction)
                for target, prediction, weight in zip(node_ys, predictions, node_weights)
            ) / total if total else 0.0
        )
        node["value"] = round(mean(predictions), 3)
        node["leaf_model"] = {
            "kind": "ridge",
            "alpha": self.leaf_ridge_alpha,
            "feature_names": [self._feature_names[j] for j in self._leaf_feature_indices],
            "coef": [float(value) for value in model.coef_],
            "intercept": float(model.intercept_),
        }
        return node, loss

    def _build(
        self,
        idxs: list[int],
        rows: list[list[float]],
        ys: list[float],
        weights: list[float],
        *,
        depth: int,
    ) -> dict[str, Any]:
        node, parent_loss = self._leaf(idxs, rows, ys, weights)
        node_weights = [weights[index] for index in idxs]
        if depth >= self.max_depth or sum(node_weights) < 2 * self.min_samples_leaf:
            return node

        best: Optional[tuple[float, float, float, int, float, list[int], list[int]]] = None
        total_weight = sum(node_weights)
        for j in range(len(self._feature_names or [])):
            feature_name = self._feature_names[j]
            if (
                self.allowed_feature_names is not None
                and feature_name not in self.allowed_feature_names
            ):
                continue
            importance = self._weight(feature_name)
            values = sorted({rows[index][j] for index in idxs})
            for low, high in zip(values, values[1:]):
                threshold = (low + high) / 2
                left = [index for index in idxs if rows[index][j] <= threshold]
                right = [index for index in idxs if rows[index][j] > threshold]
                left_weight = sum(weights[index] for index in left)
                right_weight = sum(weights[index] for index in right)
                if (
                    left_weight < self.min_samples_leaf
                    or right_weight < self.min_samples_leaf
                ):
                    continue
                _, left_loss = self._leaf(left, rows, ys, weights)
                _, right_loss = self._leaf(right, rows, ys, weights)
                child_loss = (
                    left_weight / total_weight * left_loss
                    + right_weight / total_weight * right_loss
                )
                immediate_gain = importance * (parent_loss - child_loss)
                lookahead_gain = 0.0
                if self.split_lookahead and depth + 1 < self.max_depth:
                    lookahead_gain = (
                        left_weight / total_weight
                        * self._best_one_split_gain(left, rows, ys, weights)
                        + right_weight / total_weight
                        * self._best_one_split_gain(right, rows, ys, weights)
                    )
                adjusted_gain = immediate_gain + lookahead_gain
                if adjusted_gain > 0 and (best is None or adjusted_gain > best[0]):
                    best = (
                        adjusted_gain, immediate_gain, lookahead_gain,
                        j, threshold, left, right,
                    )

        if best is None:
            return node
        gain, immediate_gain, lookahead_gain, j, threshold, left, right = best
        return {
            "leaf": False,
            "samples": len(idxs),
            "weighted_samples": round(sum(node_weights), 3),
            "value": node["value"],
            "feature": self._feature_names[j],
            "threshold": round(threshold, 3),
            "weighted_gain": round(gain, 6),
            "immediate_gain": round(immediate_gain, 6),
            "lookahead_gain": round(lookahead_gain, 6),
            "semantic_decision": True,
            "left": self._build(left, rows, ys, weights, depth=depth + 1),
            "right": self._build(right, rows, ys, weights, depth=depth + 1),
        }

    def _best_one_split_gain(
        self,
        idxs: list[int],
        rows: list[list[float]],
        ys: list[float],
        weights: list[float],
    ) -> float:
        total_weight = sum(weights[index] for index in idxs)
        if total_weight < 2 * self.min_samples_leaf:
            return 0.0
        _, parent_loss = self._leaf(idxs, rows, ys, weights)
        best_gain = 0.0
        for j in range(len(self._feature_names or [])):
            feature_name = self._feature_names[j]
            if (
                self.allowed_feature_names is not None
                and feature_name not in self.allowed_feature_names
            ):
                continue
            values = sorted({rows[index][j] for index in idxs})
            for low, high in zip(values, values[1:]):
                threshold = (low + high) / 2
                left = [index for index in idxs if rows[index][j] <= threshold]
                right = [index for index in idxs if rows[index][j] > threshold]
                left_weight = sum(weights[index] for index in left)
                right_weight = sum(weights[index] for index in right)
                if (
                    left_weight < self.min_samples_leaf
                    or right_weight < self.min_samples_leaf
                ):
                    continue
                _, left_loss = self._leaf(left, rows, ys, weights)
                _, right_loss = self._leaf(right, rows, ys, weights)
                child_loss = (
                    left_weight / total_weight * left_loss
                    + right_weight / total_weight * right_loss
                )
                gain = self._weight(feature_name) * (parent_loss - child_loss)
                best_gain = max(best_gain, gain)
        return best_gain

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        if self._tree is None:
            raise RuntimeError("SemanticDecisionTreeCalibrator.fit must be called before predict")
        index_of = {name: j for j, name in enumerate(self._feature_names or [])}
        output: list[float] = []
        for row in X:
            node = self._tree
            while not node["leaf"]:
                j = index_of[node["feature"]]
                node = node["left"] if float(row[j]) <= node["threshold"] else node["right"]
            leaf_model = node.get("leaf_model")
            if leaf_model:
                value = float(leaf_model["intercept"])
                for name, coefficient in zip(
                    leaf_model["feature_names"], leaf_model["coef"],
                ):
                    value += float(coefficient) * float(row[index_of[name]])
                output.append(value)
            else:
                output.append(float(node["value"]))
        return output

    def _rule_text(self, node: dict[str, Any], depth: int = 0) -> str:
        pad = "|   " * depth
        if node["leaf"]:
            kind = "model" if node.get("leaf_model") else "value"
            return f"{pad}|--- leaf {kind}: [{node['value']}]\n"
        feature, threshold = node["feature"], node["threshold"]
        return (
            f"{pad}|--- semantic {feature} <= {threshold}\n"
            f"{self._rule_text(node['left'], depth + 1)}"
            f"{pad}|--- semantic {feature} >  {threshold}\n"
            f"{self._rule_text(node['right'], depth + 1)}"
        )

    def metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "version": self.version,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "split_lookahead": self.split_lookahead,
            "leaf_feature_names": list(self.leaf_feature_names),
            "leaf_ridge_alpha": self.leaf_ridge_alpha,
            "allowed_feature_names": (
                sorted(self.allowed_feature_names)
                if self.allowed_feature_names is not None else None
            ),
        }
        if self._tree is not None:
            meta["tree"] = self._tree
            meta["rule_text"] = self._rule_text(self._tree)
            meta["feature_importances"] = [
                self._weight(name) for name in (self._feature_names or [])
            ]
        return meta


class PromptRoutedSemanticTreeCalibrator(Calibrator):
    """Use a fixed prompt router and semantic-only learned subtrees."""

    version = "prompt-routed-semantic-tree-v1"

    def __init__(
        self,
        *,
        feature_weights: Optional[dict[str, float]] = None,
        semantic_feature_names: Optional[Sequence[str]] = None,
        prompt_feature_names: Optional[Sequence[str]] = None,
        leaf_feature_names: Optional[Sequence[str]] = None,
        max_depth: int = 3,
        min_samples_leaf: int = 1,
        leaf_ridge_alpha: float = 1.0,
    ) -> None:
        self.feature_weights = dict(feature_weights or {})
        self.semantic_feature_names = list(semantic_feature_names or [])
        self.prompt_feature_names = list(prompt_feature_names or [])
        self.leaf_feature_names = list(leaf_feature_names or [])
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.leaf_ridge_alpha = leaf_ridge_alpha
        self._feature_names: list[str] = []
        self._models: dict[str, SemanticDecisionTreeCalibrator] = {}
        self._fallback: Optional[SemanticDecisionTreeCalibrator] = None

    def _prompt_for_row(self, row: Sequence[float]) -> str:
        for name in self.prompt_feature_names:
            if name in self._feature_names and float(row[self._feature_names.index(name)]) > 0.5:
                return name
        return "__fallback__"

    def _semantic_for_prompt(self, prompt_name: str) -> list[str]:
        metric = prompt_name.split(":", 1)[1] if ":" in prompt_name else prompt_name
        return [
            name for name in self.semantic_feature_names
            if f":{metric}:" in name or ":shared:" in name
        ]

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        *,
        feature_names: Optional[Sequence[str]] = None,
        sample_weight: Optional[Sequence[float]] = None,
    ) -> "PromptRoutedSemanticTreeCalibrator":
        rows = [list(map(float, row)) for row in X]
        ys = [float(value) for value in y]
        weights = (
            list(map(float, sample_weight)) if sample_weight is not None
            else [1.0] * len(ys)
        )
        self._feature_names = list(
            feature_names or [f"x{index}" for index in range(len(rows[0]) if rows else 0)]
        )
        self._models = {}
        for prompt_name in self.prompt_feature_names:
            idxs = [
                index for index, row in enumerate(rows)
                if self._prompt_for_row(row) == prompt_name
            ]
            if not idxs:
                continue
            self._models[prompt_name] = SemanticDecisionTreeCalibrator(
                feature_weights=self.feature_weights,
                allowed_feature_names=self._semantic_for_prompt(prompt_name),
                leaf_feature_names=self.leaf_feature_names,
                leaf_ridge_alpha=self.leaf_ridge_alpha,
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
            ).fit(
                [rows[index] for index in idxs],
                [ys[index] for index in idxs],
                feature_names=self._feature_names,
                sample_weight=[weights[index] for index in idxs],
            )
        self._fallback = SemanticDecisionTreeCalibrator(
            allowed_feature_names=[],
            leaf_feature_names=self.leaf_feature_names,
            leaf_ridge_alpha=self.leaf_ridge_alpha,
            max_depth=0,
        ).fit(rows, ys, feature_names=self._feature_names, sample_weight=weights)
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        if self._fallback is None:
            raise RuntimeError("PromptRoutedSemanticTreeCalibrator.fit must be called before predict")
        output: list[float] = []
        for row in X:
            model = self._models.get(self._prompt_for_row(row), self._fallback)
            output.append(model.predict([row])[0])
        return output

    def _router_tree(self) -> Optional[dict[str, Any]]:
        tree = self._fallback.metadata().get("tree") if self._fallback else None
        for prompt_name in reversed(self.prompt_feature_names):
            model = self._models.get(prompt_name)
            if not model:
                continue
            subtree = model.metadata().get("tree")
            tree = {
                "leaf": False,
                "samples": (subtree or {}).get("samples", 0),
                "weighted_samples": (subtree or {}).get("weighted_samples", 0),
                "value": (subtree or {}).get("value", 0),
                "feature": prompt_name,
                "threshold": 0.5,
                "context_router": True,
                "left": tree or subtree,
                "right": subtree,
            }
        return tree

    def metadata(self) -> dict[str, Any]:
        prompt_trees = {
            prompt: model.metadata().get("tree") for prompt, model in self._models.items()
        }
        semantic_splits: list[str] = []

        def collect(node: Optional[dict[str, Any]]) -> None:
            if not node or node.get("leaf"):
                return
            semantic_splits.append(str(node.get("feature")))
            collect(node.get("left"))
            collect(node.get("right"))

        for prompt_tree in prompt_trees.values():
            collect(prompt_tree)
        tree = self._router_tree()
        return {
            "version": self.version,
            "tree": tree,
            "prompt_trees": prompt_trees,
            "semantic_split_features": semantic_splits,
            "semantic_split_count": len(semantic_splits),
            "raw_score_split_count": sum(
                name in {"base_score", "score_std", "score_range"}
                for name in semantic_splits
            ),
            "leaf_feature_names": list(self.leaf_feature_names),
            "rule_text": self._rule_text(tree),
        }

    def _rule_text(self, node: Optional[dict[str, Any]], depth: int = 0) -> str:
        if not node:
            return ""
        pad = "|   " * depth
        if node.get("leaf"):
            return f"{pad}|--- leaf calibration: [{node.get('value', 0)}]\n"
        label = "context" if node.get("context_router") else "semantic"
        return (
            f"{pad}|--- {label} {node['feature']} <= {node['threshold']}\n"
            f"{self._rule_text(node.get('left'), depth + 1)}"
            f"{pad}|--- {label} {node['feature']} >  {node['threshold']}\n"
            f"{self._rule_text(node.get('right'), depth + 1)}"
        )
