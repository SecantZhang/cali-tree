"""Contracts for learned, data-only decision programs."""
from abc import ABC, abstractmethod


class DecisionProgram(ABC):
    @abstractmethod
    def fit(self, rows):
        """Fit feature records; targets and case groups are training metadata."""

    @abstractmethod
    def predict(self, features):
        """Predict using only the declared feature vector."""

    @abstractmethod
    def to_dict(self):
        """Export a portable program without Python objects or case lookups."""
