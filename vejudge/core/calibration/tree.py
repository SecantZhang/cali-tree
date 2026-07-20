"""Shallow decision-tree calibrator.

Maps a judge feature vector — the judge's own 1-5 score plus a handful of semantic
boolean answers (see the prompt-calibration experiment under
``core.calibration.debate.eval``) — to a human-aligned score. Kept deliberately shallow
(``max_depth=2``, ``min_samples_leaf=2``) because the labeled batch is tiny (n≈7): a
deeper tree memorizes the batch and fails leave-one-out. ``metadata()`` exposes the
fitted rule as text so the "judge rule" is auditable, matching the interpretable-tree
intent.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .base import Calibrator


def _export_tree_dict(model: Any, feature_names: Optional[Sequence[str]]) -> dict[str, Any]:
    """A JSON-serializable structural view of a fitted sklearn regression tree, for a UI
    to render as an actual node/edge diagram (the ``export_text`` string is kept alongside
    for auditing, but a string can't be drawn). Each node is either a split
    ``{leaf: False, feature, threshold, samples, value, left, right}`` — left = condition
    TRUE (``feature <= threshold``), matching sklearn's convention — or a leaf
    ``{leaf: True, samples, value}`` where ``value`` is the predicted (calibrated) score.
    """
    t = model.tree_

    def node(i: int) -> dict[str, Any]:
        # sklearn marks a leaf by having no children (both child ids == -1 / TREE_LEAF).
        is_leaf = t.children_left[i] == t.children_right[i]
        out: dict[str, Any] = {
            "leaf": bool(is_leaf),
            "samples": int(t.n_node_samples[i]),
            # Regression tree: value has shape (1, n_outputs); single-output here.
            "value": round(float(t.value[i][0][0]), 3),
        }
        if not is_leaf:
            fi = int(t.feature[i])
            out["feature"] = (
                feature_names[fi] if feature_names is not None and 0 <= fi < len(feature_names)
                else f"x{fi}"
            )
            out["threshold"] = round(float(t.threshold[i]), 3)
            out["left"] = node(int(t.children_left[i]))
            out["right"] = node(int(t.children_right[i]))
        return out

    return node(0)


class DecisionTreeCalibrator(Calibrator):
    version = "decision-tree-v1"

    def __init__(self, *, max_depth: int = 2, min_samples_leaf: int = 2) -> None:
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self._model: Optional[Any] = None
        self._feature_names: Optional[list[str]] = None

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        *,
        feature_names: Optional[Sequence[str]] = None,
    ) -> "DecisionTreeCalibrator":
        from sklearn.tree import DecisionTreeRegressor  # lazy import

        self._model = DecisionTreeRegressor(
            max_depth=self.max_depth, min_samples_leaf=self.min_samples_leaf,
        ).fit(list(X), list(y))
        self._feature_names = list(feature_names) if feature_names is not None else None
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        if self._model is None:
            raise RuntimeError("DecisionTreeCalibrator.fit must be called before predict")
        return [float(v) for v in self._model.predict(list(X))]

    def metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "version": self.version,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
        }
        if self._model is not None:
            from sklearn.tree import export_text

            kwargs: dict[str, Any] = {}
            if self._feature_names is not None:
                kwargs["feature_names"] = self._feature_names
            # The human-readable "judge rule" — the whole point of using a tree.
            meta["rule_text"] = export_text(self._model, **kwargs)
            # Structured form of the same tree, for a UI to draw as a diagram.
            meta["tree"] = _export_tree_dict(self._model, self._feature_names)
            meta["feature_importances"] = [
                float(v) for v in getattr(self._model, "feature_importances_", [])
            ]
        return meta
