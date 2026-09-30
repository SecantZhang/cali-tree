"""Prompt refinement and leaf specialization contracts."""

from abc import ABC, abstractmethod
from typing import Any

from ..context import BuildContext, CaliTreeServices, OptimizationResult


class PromptOptimizer(ABC):
    @abstractmethod
    def optimize(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str],
        *, services: CaliTreeServices, max_steps: int,
    ) -> OptimizationResult:
        """Refine a prompt using only the supplied cases."""
        ...


class LeafOptimizer(ABC):
    @abstractmethod
    def optimize(
        self, prompt: str, ids: list[str], context: BuildContext,
    ) -> OptimizationResult:
        """Specialize one leaf group independently of warm-start/merge refinement."""
        ...
