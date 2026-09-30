"""Reusable leaf execution, separate from durable node construction."""

from dataclasses import dataclass

from .artifacts import snapshot
from .factory import DefaultNodeFactory
from ..context import OptimizationResult
from ..evaluation import balanced_accuracy
from ..geometry import centroid
from ..optimization.composite import OptimizerPlan


@dataclass
class LeafBuildResult:
    node: object
    snapshot: dict
    optimization: OptimizationResult


class LeafController:
    def __init__(self, optimizer=None, factory=None):
        self.optimizer = optimizer if optimizer is not None else OptimizerPlan()
        self.factory = factory if factory is not None else DefaultNodeFactory()

    def optimize(self, initial_prompt, ids, context):
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("A leaf requires a nonempty, unique fit-case group")
        if any(key not in context.samples or key not in context.targets for key in ids):
            raise ValueError("Leaf group contains unknown fit cases")
        return self.optimizer.optimize(initial_prompt, ids, context)

    def build(self, initial_prompt, ids, context, *, node_id, semantic_groups=None):
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("A leaf requires a nonempty, unique fit-case group")
        if context.executor is None:
            raise ValueError("LeafController requires a decomposition executor")
        if any(key not in context.samples or key not in context.targets for key in ids):
            raise ValueError("Leaf group contains unknown fit cases")
        context.executor.preflight({key: context.samples[key] for key in ids})
        result = self.optimize(initial_prompt, ids, context)
        accuracy, correct, predictions = context.services.validate(result.prompt, ids,
                                                                  context.samples, context.targets)
        result.accuracy, result.correct_ids, result.predictions = accuracy, correct, predictions
        components = context.services.extract_components(result.prompt)
        criteria_text = "\n".join(f"{kind}: {value}" for kind in ("criteria", "priorities", "constraints")
                                  for value in components.get(kind, []))
        criteria_embedding = context.services.embed([criteria_text])[0]
        node = self.factory.leaf(id=node_id, prompt=result.prompt, covered_ids=list(ids),
                                 embedding=centroid(context.case_embeddings[key] for key in ids),
                                 components=components, criteria_embedding=criteria_embedding,
                                 member_embeddings=[criteria_embedding], validation_accuracy=accuracy,
                                 semantic_groups=sorted({(semantic_groups or {}).get(key, "unknown") for key in ids}),
                                 routing_eligible=False)
        metadata = snapshot(node, scope_ids=ids, served_ids=ids,
                            predictions={"accuracy": accuracy, "balanced_accuracy": balanced_accuracy(
                                ids, context.targets, predictions), "correct_ids": correct,
                                "predictions": predictions},
                            strategy={"decomposition": context.executor.adapter.name,
                                      "optimizer": result.report.get("plan", type(self.optimizer).__name__)},
                            provenance={"input_prompt": initial_prompt, "optimization": result.report})
        return LeafBuildResult(node, metadata, result)
