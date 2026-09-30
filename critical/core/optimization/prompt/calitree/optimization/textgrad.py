"""Convenience leaf adapter for the existing official TextGrad implementation."""

from dataclasses import replace

from .composite import OptimizerPlan
from ...textgrad import textgrad_update
from ..decomposition.artifacts import component_identity


class TextGradLeafOptimizer(OptimizerPlan):
    def __init__(self, engine, *, usage_cb=None, log_dir=None):
        super().__init__("textgrad")
        self.engine, self.usage_cb, self.log_dir = engine, usage_cb, log_dir

    def optimize(self, prompt, ids, context):
        services = replace(context.services, optimizer_identity={**context.services.optimizer_identity,
            "textgrad": component_identity(self)}, optimize=lambda text, feedback: textgrad_update(
            text, feedback, engine=self.engine, usage_cb=self.usage_cb, log_dir=self.log_dir))
        return super().optimize(prompt, ids, replace(context, services=services))
