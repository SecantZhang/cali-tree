"""Complete-link clustering of extracted prompt criteria."""

from .base import ClusteringAlgorithm
from ..context import BuildContext, PairScore
from ..geometry import complete_link_similarity
from ..node import CaliTreeNode


class SemanticCompleteLinkClustering(ClusteringAlgorithm):
    def score(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> PairScore:
        similarity = complete_link_similarity(left, right)
        return PairScore(similarity, {"semantic_similarity": similarity})
