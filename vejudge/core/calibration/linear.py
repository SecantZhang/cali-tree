"""Linear-regression calibration baseline (scaffold).

The default first baseline per CLAUDE.md: linear regression over judge sub-scores
(optionally with a per-category bias term). Wired but intentionally minimal — the v1
benchmark reports the *raw* gap; fit this once the raw numbers are reviewed.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .base import Calibrator


class LinearCalibrator(Calibrator):
    version = "linear-v2-weighted"

    def __init__(self) -> None:
        self._model: Optional[Any] = None

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        *,
        sample_weight: Optional[Sequence[float]] = None,
    ) -> "LinearCalibrator":
        from sklearn.linear_model import LinearRegression  # lazy import

        self._model = LinearRegression().fit(
            list(X), list(y), sample_weight=None if sample_weight is None else list(sample_weight)
        )
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        if self._model is None:
            raise RuntimeError("LinearCalibrator.fit must be called before predict")
        return [float(v) for v in self._model.predict(list(X))]

    def metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"version": self.version}
        if self._model is not None:
            meta["coef"] = [float(c) for c in getattr(self._model, "coef_", [])]
            meta["intercept"] = float(getattr(self._model, "intercept_", 0.0))
        return meta
