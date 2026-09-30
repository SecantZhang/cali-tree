"""Run proposal, refinement, and acceptance without changing tree topology."""

from .base import MergeAlgorithm, MergeAcceptancePolicy, MergeDecision, MergeResult, MultiMergeAlgorithm
from ..context import BuildContext, OptimizationResult
from ..node import CaliTreeNode


class MergeCoordinator:
    def __init__(self, algorithm: MergeAlgorithm, acceptance: MergeAcceptancePolicy) -> None:
        self.algorithm = algorithm
        self.acceptance = acceptance

    def propose_many(self, children, context):
        from copy import deepcopy
        if len(children) < 2 or len({node.id for node in children}) != len(children):
            raise ValueError("A merge needs at least two distinct children")
        if len(children) > 2 and not isinstance(self.algorithm, MultiMergeAlgorithm):
            raise ValueError("Selected merge algorithm supports only two children")
        copied = deepcopy(children)
        return (self.algorithm.propose_many(copied, context) if isinstance(self.algorithm, MultiMergeAlgorithm)
                else self.algorithm.propose(*copied, context))

    def refine(self, prompt, ids, context):
        return OptimizationResult(*context.optimize_cases(prompt, ids, context.samples, context.targets))

    def assess(self, optimization, scope, context):
        return self.acceptance.evaluate(optimization, scope, context)

    def merge(self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext) -> MergeResult:
        proposal = self.algorithm.propose(left, right, context)
        if proposal.conflict or not proposal.prompt.strip():
            reason = proposal.conflict_reason or "incompatible criteria"
            return MergeResult(MergeDecision(False, "branch", diagnostics={"reason": reason}),
                               conflict_reason=reason)
        normalized = " ".join(proposal.prompt.lower().split())
        if normalized in context.rejected_static_generalization_prompts:
            return MergeResult(MergeDecision(False, "pruned_equivalent", diagnostics={
                "reason": "identical unoptimized prompt already failed the shared guard",
            }))
        covered_ids = sorted(set(left.covered_ids + right.covered_ids))
        optimization = OptimizationResult(*context.optimize_cases(
            proposal.prompt, covered_ids, context.samples, context.targets,
        ))
        decision = self.acceptance.evaluate(optimization, covered_ids, context)
        if decision.kind == "rejected_generalization" and not decision.accepted and optimization.steps == 0:
            context.rejected_static_generalization_prompts.add(normalized)
        return MergeResult(decision, covered_ids, optimization)

    def merge_many(self, children: list[CaliTreeNode], context: BuildContext) -> MergeResult:
        """Synthesize once and evaluate full descendant scope, without changing children."""
        from copy import deepcopy
        if len(children) < 2 or len({node.id for node in children}) != len(children):
            raise ValueError("A merge needs at least two distinct children")
        supplied = {node.id for node in children}

        def descendants(node, path):
            if node.id in path:
                raise ValueError("Cycle in merge inputs")
            for child_id in node.children:
                if child_id in supplied:
                    raise ValueError("Cannot merge a node with its descendant")
                if child_id not in context.nodes:
                    raise ValueError("Unresolved merge descendant")
                descendants(context.nodes[child_id], path | {node.id})

        for node in children:
            descendants(node, set())
        if context.executor is None:
            if len(children) != 2:
                raise ValueError("Multi-child merging requires a modular context")
            return self.merge(children[0], children[1], context)
        scope = sorted({key for node in children for key in
                        context.artifacts[node.id]["scope_ids"]})
        served = sorted({key for node in children for key in
                         context.artifacts[node.id]["served_ids"]})
        if not context.validation_ids:
            return MergeResult(MergeDecision(False, "missing_reserved_validation"), scope)
        if not isinstance(self.algorithm, MultiMergeAlgorithm) and len(children) > 2:
            raise ValueError("Selected merge algorithm supports only two children")
        proposal = self.propose_many(children, context)
        if proposal.conflict or not proposal.prompt.strip():
            return MergeResult(MergeDecision(False, "branch"), scope,
                               conflict_reason=proposal.conflict_reason or "incompatible criteria")
        optimization = OptimizationResult(*context.optimize_cases(
            proposal.prompt, scope, context.samples, context.targets))
        decision = self.acceptance.evaluate(optimization, scope, context)
        served_correct = sorted(set(served) & set(optimization.correct_ids))
        if decision.accepted and not served_correct:
            decision = MergeDecision(False, "empty_served_scope")
        return MergeResult(decision, scope, optimization, served_ids=served_correct)
