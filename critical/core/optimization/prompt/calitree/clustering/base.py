"""Candidate selection and transfer-probe contract."""

from abc import ABC, abstractmethod

from ..context import BuildContext, PairScore
from ..geometry import greedy_pairs
from ..node import CaliTreeNode


class ClusteringAlgorithm(ABC):
    """Override score/probe or pairing; all mutable probe state belongs to the context."""

    def prepare(self, nodes: list[CaliTreeNode], context: BuildContext) -> None:
        """Initialize optional training-only probe state before clustering."""

    def refresh(self, node: CaliTreeNode, context: BuildContext) -> None:
        """Measure an accepted parent's optional behavior profile."""

    @abstractmethod
    def score(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> PairScore:
        """Cheap ranking score and timeline diagnostics."""
        ...

    def probe(
        self, left: CaliTreeNode, right: CaliTreeNode, context: BuildContext,
    ) -> PairScore:
        """Re-evaluate a selected pair before synthesis; may run transfer probes."""
        return self.score(left, right, context)

    def pairs(
        self, nodes: list[CaliTreeNode], threshold: float, *, level: int,
        blocked_pairs: set[frozenset[str]], context: BuildContext,
    ) -> tuple[list[tuple[CaliTreeNode, CaliTreeNode, float]], list[CaliTreeNode]]:
        compatible = None
        if level < context.settings.semantic_premerge_levels:
            compatible = lambda left, right: bool(
                set(left.semantic_groups) & set(right.semantic_groups)
            )
        return greedy_pairs(
            nodes, threshold, blocked_pairs, compatible,
            lambda left, right: self.score(left, right, context).similarity,
        )

    def groups(self, nodes, threshold, *, level, max_children, blocked_pairs,
               blocked_groups, context):
        """Deterministic complete-link growth, consuming each active node at most once."""
        from itertools import combinations
        available = {node.id: node for node in nodes}
        output = []

        def affinity(left, right):
            if frozenset((left.id, right.id)) in blocked_pairs:
                return -2.0
            if (level < context.settings.semantic_premerge_levels and not
                    set(left.semantic_groups) & set(right.semantic_groups)):
                return -2.0
            return self.score(left, right, context).similarity

        seeds = sorted(((affinity(left, right), left.id, right.id)
                        for left, right in combinations(sorted(nodes, key=lambda n: n.id), 2)),
                       key=lambda row: (-row[0], row[1], row[2]))
        for score, left_id, right_id in seeds:
            if score < threshold or left_id not in available or right_id not in available:
                continue
            group = [available[left_id], available[right_id]]
            while len(group) < max_children:
                candidates = [(min(affinity(node, member) for member in group), node.id, node)
                              for node in available.values() if node.id not in {n.id for n in group}]
                candidates.sort(key=lambda row: (-row[0], row[1]))
                if not candidates or candidates[0][0] < threshold:
                    break
                group.append(candidates[0][2])
            # A rejected joint group must not starve its still-eligible subsets.
            # Drop additions in reverse growth order, retaining the ranked seed.
            while len(group) > 2 and frozenset(node.id for node in group) in blocked_groups:
                group.pop()
            if frozenset(node.id for node in group) in blocked_groups:
                continue
            group.sort(key=lambda node: node.id)
            score = min(affinity(left, right) for left, right in combinations(group, 2))
            output.append((group, score))
            for node in group:
                del available[node.id]
        return output, sorted(available.values(), key=lambda node: node.id)
