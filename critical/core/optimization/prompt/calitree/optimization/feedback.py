"""Callback-backed feedback optimization shared by all default stages."""

from typing import Any

from .base import LeafOptimizer, PromptOptimizer
from ..context import BuildContext, CaliTreeServices, OptimizationResult


class FeedbackPromptOptimizer(PromptOptimizer):
    def optimize(
        self, prompt: str, ids: list[str], samples: dict[str, Any], targets: dict[str, str],
        *, services: CaliTreeServices, max_steps: int,
    ) -> OptimizationResult:
        accuracy, correct, results = services.validate(prompt, ids, samples, targets)
        steps = 0
        while accuracy < 1.0 and steps < max_steps:
            mistakes = [item_id for item_id in ids if item_id not in correct]
            if services.format_feedback is not None:
                feedback = services.format_feedback(mistakes, samples, targets, results)
            else:
                feedback = "\n\n".join(
                    f"Instruction: {(samples[item_id].get('input') or {}).get('instruction', '')}\n"
                    f"Predicted: {results[item_id].get('label')}\n"
                    f"Target: {targets[item_id]}\n"
                    f"Rationale: {results[item_id].get('rationale', '')}"
                    for item_id in mistakes
                )
            prompt = services.optimize(prompt, feedback)
            steps += 1
            accuracy, correct, results = services.validate(prompt, ids, samples, targets)
        return OptimizationResult(prompt, accuracy, correct, results, steps)


class DefaultLeafOptimizer(LeafOptimizer):
    def optimize(
        self, prompt: str, ids: list[str], context: BuildContext,
    ) -> OptimizationResult:
        return OptimizationResult(*context.optimize_cases(
            prompt, ids, context.samples, context.targets,
        ))
