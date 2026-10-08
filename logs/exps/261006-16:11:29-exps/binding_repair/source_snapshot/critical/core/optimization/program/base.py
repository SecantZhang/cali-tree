"""Replaceable search components; feedback and inference have different inputs."""
from abc import ABC, abstractmethod


class DecisionProgramOptimizer(ABC):
    @abstractmethod
    def optimize(self, seed, context):
        pass


class EditProposer(ABC):
    @abstractmethod
    def propose(self, program, feedback, *, slot, limit):
        pass

    def audit(self, before, after, edit, *, slot):
        return {"accepted": True, "reason": "Structural validation only"}


class ProgramEvaluator(ABC):
    @abstractmethod
    def evaluate(self, program, cases, *, repeats, namespace, final=False):
        pass


class AcceptancePolicy(ABC):
    @abstractmethod
    def assess(self, baseline, candidate):
        pass
