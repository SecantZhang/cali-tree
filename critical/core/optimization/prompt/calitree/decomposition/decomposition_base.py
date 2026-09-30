"""Extension contracts for decomposition_example.py and other strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, Generic, TypeVar

from .models import Condition, ConditionResult, DecompositionResult, InstructionPlan
from .policy import CompiledPolicy


class RubricCompiler(ABC):
    @abstractmethod
    def compile(self, rubric: str) -> CompiledPolicy:
        """Compile only rubric semantics; never consume sample targets."""
        ...


class InstructionCompiler(ABC):
    @abstractmethod
    def decompose(self, instruction: str) -> InstructionPlan:
        """Extract intent without seeing evidence or final labels."""
        ...


class ConditionEvaluator(ABC):
    def cache_key(self, condition: Condition, evidence: dict[str, Any]) -> str:
        """Custom evaluators retain the complete evidence context by default."""
        return json.dumps({"condition": condition.to_dict(), "evidence": evidence},
                          sort_keys=True, allow_nan=False)

    @abstractmethod
    def evaluate(self, condition: Condition, evidence: dict[str, Any]) -> ConditionResult:
        """Evaluate one condition without deciding the overall label."""
        ...


PolicyT = TypeVar("PolicyT")
PlanT = TypeVar("PlanT")


class DecompositionAlgorithm(ABC, Generic[PolicyT, PlanT]):
    @abstractmethod
    def compile(self, rubric: str) -> PolicyT:
        ...

    @abstractmethod
    def decompose(self, instruction: str) -> PlanT:
        ...

    @abstractmethod
    def evaluate(
        self, policy: PolicyT, instruction: str, evidence: dict[str, Any],
    ) -> DecompositionResult:
        ...

    @abstractmethod
    def judge(self, prompt: str, sample: dict[str, Any]) -> dict[str, str]:
        """A callback suitable for CaliTreeBuilder(judge=...)."""
        ...

    def judge_many(
        self, prompt: str, samples: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        return {key: self.judge(prompt, sample) for key, sample in samples.items()}
