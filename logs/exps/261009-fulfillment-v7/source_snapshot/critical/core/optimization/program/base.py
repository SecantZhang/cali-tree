"""Contracts for replaceable local repair components."""
from abc import ABC, abstractmethod
class LeafOptimizer(ABC):
    @abstractmethod
    def optimize(self, case, reference_label, *, seed=None): ...
class EditProposer(ABC):
    @abstractmethod
    def propose(self, program, case, reference_label, feedback, *, slot, limit): ...
class LeafEvaluator(ABC):
    @abstractmethod
    def evaluate(self, program, case, reference_label, *, repeats, namespace, final=False): ...
class AcceptancePolicy(ABC):
    @abstractmethod
    def rank(self, report, program): ...
