"""Complete-link ranking with measured behavior and lazy bidirectional transfer."""

from typing import Optional

from .base import ClusteringAlgorithm
from ..context import BuildContext, CaliTreeSettings, PairScore
from ..evaluation import balanced_accuracy, balanced_case_subset, behavior_profile
from ..geometry import complete_link_similarity, cosine_similarity
from ..node import CaliTreeNode


class BehavioralCompleteLinkClustering(ClusteringAlgorithm):
    def prepare(self, nodes: list[CaliTreeNode], context: BuildContext) -> None:
        context.behavioral_probe_ids = balanced_case_subset(
            context.item_ids, context.targets, context.settings.behavioral_probe_cap,
        )
        if context.item_ids:
            for node in nodes:
                self.refresh(node, context)
            context.timeline.append({
                "kind": "behavioral_clustering_probe",
                "node_id": "behavioral_clustering",
                "leaves": len(nodes),
                "probe_cases": len(context.behavioral_probe_ids),
            })

    def refresh(self, node: CaliTreeNode, context: BuildContext) -> None:
        _accuracy, _correct, results = context.services.validate(
            node.prompt, context.behavioral_probe_ids, context.samples, context.targets,
        )
        node.behavior_profile = behavior_profile(
            context.behavioral_probe_ids, context.targets, results,
        )

    @staticmethod
    def weighted_score(
        left: CaliTreeNode, right: CaliTreeNode, settings: CaliTreeSettings,
        cross_generalization: Optional[float] = None,
    ) -> PairScore:
        semantic = complete_link_similarity(left, right)
        behavior = cosine_similarity(left.behavior_profile, right.behavior_profile)
        active_weights = settings.semantic_similarity_weight + settings.behavior_similarity_weight
        if cross_generalization is not None:
            active_weights += settings.cross_generalization_weight
        active_weights = active_weights or 1.0
        score = (
            settings.semantic_similarity_weight * semantic
            + settings.behavior_similarity_weight * behavior
            + (settings.cross_generalization_weight * cross_generalization
               if cross_generalization is not None else 0.0)
        ) / active_weights
        diagnostics = {"semantic_similarity": semantic, "behavior_similarity": behavior}
        if cross_generalization is not None:
            diagnostics["cross_generalization"] = cross_generalization
        return PairScore(score, diagnostics)

    def score(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> PairScore:
        return self.weighted_score(left, right, context.settings)

    def probe(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> PairScore:
        left_ids = balanced_case_subset(
            right.covered_ids, context.targets, context.settings.cross_generalization_cap,
        )
        right_ids = balanced_case_subset(
            left.covered_ids, context.targets, context.settings.cross_generalization_cap,
        )
        _raw, _correct, left_results = context.services.validate(
            left.prompt, left_ids, context.samples, context.targets,
        )
        _raw, _correct, right_results = context.services.validate(
            right.prompt, right_ids, context.samples, context.targets,
        )
        left_on_right = balanced_accuracy(left_ids, context.targets, left_results)
        right_on_left = balanced_accuracy(right_ids, context.targets, right_results)
        result = self.weighted_score(
            left, right, context.settings, (left_on_right + right_on_left) / 2,
        )
        result.diagnostics.update(left_on_right=left_on_right, right_on_left=right_on_left)
        return result
