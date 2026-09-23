"""Abstract ensemble interface (stub).

Future: aggregate multiple judges or prompt variants (e.g. A/B-order-swapped pairwise)
into a single score. Not implemented in v1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class Ensemble(ABC):
    @abstractmethod
    def combine(self, judge_outputs: Sequence[dict[str, Any]]) -> dict[str, Any]:
        ...
