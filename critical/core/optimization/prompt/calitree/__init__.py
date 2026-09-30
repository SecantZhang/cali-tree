"""CaliTree prompt optimization, metrics, and routing."""

from .builder import CaliTreeBuilder
from .geometry import (
    centroid,
    complete_link_similarity,
    cosine_similarity,
    greedy_pairs,
    similarity_threshold,
)
from .metrics import (
    LABELS,
    ORDINAL_VALUE,
    classification_metrics,
    ordinal_absolute_error,
)
from .model import CaliTreeNode
from .routing import route_prompt
from .node import CaliTreeLeafNode, CaliTreeMergeNode, NodeFactory, DefaultNodeFactory
from .context import (
    BuildContext, CaliTreeServices, CaliTreeSettings, OptimizationResult, PairScore,
    RootSelection,
)
from .optimization import (
    PromptOptimizer, FeedbackPromptOptimizer, LeafOptimizer, DefaultLeafOptimizer,
)
from .clustering import (
    ClusteringAlgorithm, SemanticCompleteLinkClustering, BehavioralCompleteLinkClustering,
)
from .merge import (
    MergeAlgorithm, CallbackMergeAlgorithm, MergeAcceptancePolicy, GuardedMergeAcceptance,
    MergeProposal, MergeDecision, MergeResult, MergeCoordinator,
)
from .root import RootSelector, ValidatedRootSelector
from .routing_calibration import RoutingCalibrator, GeometryRoutingCalibrator
from .decomposition import DecompositionAlgorithm, DecompositionTwoWay, DecompositionTwoWayVision, DecompositionTwoWayGrounded, DecompositionTwoWayExecutable, DecompositionTwoWayIntent, DecompositionTwoWayInventory
from .decomposition import DecompositionTwoWayCalibratedVision, VisualReference, VisualReferenceBank
from .decomposition.artifacts import DecompositionAdapter, TwoWayAdapter, TwoWayVisionAdapter, ArtifactExecutor
from .node.leaf_controller import LeafController, LeafBuildResult
from .node.artifacts import validate_tree
from .optimization.composite import OptimizerPlan
from .optimization.textgrad import TextGradLeafOptimizer
from .optimization.gepa import gepa_leaf_optimizer
from .merge.base import MultiMergeAlgorithm
from .merge.callback import CallbackMultiMergeAlgorithm, ConcatenateMergeAlgorithm

__all__ = [
    "CaliTreeBuilder", "CaliTreeNode", "LABELS", "ORDINAL_VALUE",
    "classification_metrics", "ordinal_absolute_error", "route_prompt",
    "centroid", "complete_link_similarity", "cosine_similarity",
    "greedy_pairs", "similarity_threshold",
    "CaliTreeLeafNode", "CaliTreeMergeNode", "NodeFactory", "DefaultNodeFactory",
    "BuildContext", "CaliTreeServices", "CaliTreeSettings", "OptimizationResult",
    "PairScore", "RootSelection",
    "PromptOptimizer", "FeedbackPromptOptimizer", "LeafOptimizer", "DefaultLeafOptimizer",
    "ClusteringAlgorithm", "SemanticCompleteLinkClustering", "BehavioralCompleteLinkClustering",
    "MergeAlgorithm", "CallbackMergeAlgorithm", "MergeAcceptancePolicy", "GuardedMergeAcceptance",
    "MergeProposal", "MergeDecision", "MergeResult", "MergeCoordinator",
    "RootSelector", "ValidatedRootSelector", "RoutingCalibrator", "GeometryRoutingCalibrator",
    "DecompositionAlgorithm", "DecompositionTwoWay", "DecompositionTwoWayVision", "DecompositionTwoWayGrounded",
    "DecompositionTwoWayExecutable",
    "DecompositionTwoWayIntent",
    "DecompositionTwoWayInventory",
    "DecompositionTwoWayCalibratedVision", "VisualReference", "VisualReferenceBank",
    "DecompositionAdapter", "TwoWayAdapter", "TwoWayVisionAdapter", "ArtifactExecutor",
    "LeafController", "LeafBuildResult", "validate_tree", "OptimizerPlan",
    "MultiMergeAlgorithm", "CallbackMultiMergeAlgorithm", "ConcatenateMergeAlgorithm",
    "TextGradLeafOptimizer", "gepa_leaf_optimizer",
]
