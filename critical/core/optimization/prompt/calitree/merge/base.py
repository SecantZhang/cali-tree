"""Independent prompt synthesis and acceptance contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..context import BuildContext, OptimizationResult
from ..node import CaliTreeNode


@dataclass
class MergeProposal:
    prompt: str
    conflict: bool = False
    conflict_reason: str = ""


@dataclass
class MergeDecision:
    accepted: bool
    kind: str = "rejected"
    generalization_accuracy: Optional[float] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class MergeResult:
    """A coordinator result; the builder owns topology and timeline mutations."""

    decision: MergeDecision
    covered_ids: list[str] = field(default_factory=list)
    optimization: Optional[OptimizationResult] = None
    conflict_reason: str = ""
    served_ids: list[str] = field(default_factory=list)


class MergeAlgorithm(ABC):
    @abstractmethod
    def propose(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> MergeProposal:
        ...


class MultiMergeAlgorithm(MergeAlgorithm):
    """Native joint synthesis; binary callers delegate to the same implementation."""

    def propose(self, left, right, context):
        return self.propose_many([left, right], context)

    @abstractmethod
    def propose_many(self, children: list[CaliTreeNode], context: BuildContext) -> MergeProposal:
        ...


class MergeAcceptancePolicy(ABC):
    @abstractmethod
    def evaluate(
        self, optimization: OptimizationResult, covered_ids: list[str], context: BuildContext,
    ) -> MergeDecision:
        """Accept or reject a refined proposal using the available validation cases."""
        ...
