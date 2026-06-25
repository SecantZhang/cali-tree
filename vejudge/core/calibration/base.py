"""Abstract calibrator. Implementations map judge sub-scores -> human scores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class Calibrator(ABC):
    """Fit on (judge features, human score) pairs disjoint from the test set."""

    version: str = "base"

    @abstractmethod
    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "Calibrator":
        ...

    @abstractmethod
    def predict(self, X: Sequence[Sequence[float]]) -> list[float]:
        ...

    def metadata(self) -> dict[str, Any]:
        return {"version": self.version}
