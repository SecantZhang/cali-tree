"""Calibration models mapping raw judge sub-scores to human evaluator scores.

v1 scaffolds the interface and a linear baseline; calibration is deferred until the
first raw-gap run is reviewed (only ~tens of matched items). See docs/research.md.
"""

from .base import Calibrator
from .linear import LinearCalibrator
from .semantic_tree import PromptRoutedSemanticTreeCalibrator, SemanticDecisionTreeCalibrator
from .tree import DecisionTreeCalibrator

__all__ = [
    "Calibrator",
    "LinearCalibrator",
    "DecisionTreeCalibrator",
    "SemanticDecisionTreeCalibrator",
    "PromptRoutedSemanticTreeCalibrator",
]
