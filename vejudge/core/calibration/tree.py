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
            meta["feature_importances"] = [
                float(v) for v in getattr(self._model, "feature_importances_", [])
            ]
        return meta
