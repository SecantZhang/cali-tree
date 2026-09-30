"""Covered accuracy and balanced generalization guards from the original builder."""

from .base import MergeAcceptancePolicy, MergeDecision
from ..context import BuildContext, OptimizationResult
from ..evaluation import balanced_accuracy, balanced_case_subset


class GuardedMergeAcceptance(MergeAcceptancePolicy):
    def evaluate(
        self, optimization: OptimizationResult, covered_ids: list[str], context: BuildContext,
    ) -> MergeDecision:
        settings = context.settings
        if (settings.merge_objective == "covered_accuracy"
                and optimization.accuracy < settings.merge_acceptance):
            return MergeDecision(False)
        if context.validation_ids:
            guard_ids = balanced_case_subset(
                context.validation_ids, context.validation_targets, settings.merge_validation_cap,
            )
            guard_samples = context.validation_samples
            guard_targets = context.validation_targets
        else:
            guard_ids = balanced_case_subset(
                [item_id for item_id in context.item_ids if item_id not in covered_ids],
                context.targets, settings.merge_validation_cap,
            )
            guard_samples = context.samples
            guard_targets = context.targets
        generalization_accuracy = None
        if guard_ids:
            _raw, _correct, results = context.services.validate(
                optimization.prompt, guard_ids, guard_samples, guard_targets,
            )
            generalization_accuracy = balanced_accuracy(guard_ids, guard_targets, results)
            if context.validation_ids:
                _raw, _correct, baseline_results = context.services.validate(
                    context.warm_prompt, guard_ids, guard_samples, guard_targets,
                )
            else:
                baseline_results = context.warm_results
            if baseline_results:
                baseline_accuracy = balanced_accuracy(guard_ids, guard_targets, baseline_results)
                floor_violated = (
                    settings.merge_objective == "covered_accuracy"
                    and generalization_accuracy < settings.merge_generalization_floor
                )
                if (floor_violated or generalization_accuracy + settings.merge_regression_tolerance
                        < baseline_accuracy):
                    return MergeDecision(False, "rejected_generalization", generalization_accuracy, {
                        "generalization_accuracy": generalization_accuracy,
                        "baseline_generalization_accuracy": baseline_accuracy,
                        "generalization_floor": settings.merge_generalization_floor,
                    })
        return MergeDecision(True, "accepted", generalization_accuracy)
