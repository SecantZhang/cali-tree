"""Embedding similarity and deterministic node pairing."""

from __future__ import annotations

import math
from typing import Callable, Iterable, Optional

from .model import CaliTreeNode


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    if len(a) != len(b) or not a:
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 0.0 if denominator == 0 else numerator / denominator


def centroid(vectors: Iterable[Iterable[float]]) -> list[float]:
    rows = [list(row) for row in vectors]
    if not rows:
        return []
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        return []
    return [sum(row[index] for row in rows) / len(rows) for index in range(width)]


def similarity_threshold(
    level: int, *, start: float = 0.90, decay: float = 0.05, floor: float = 0.70
) -> float:
    return max(floor, start - decay * level)

def complete_link_similarity(left: CaliTreeNode, right: CaliTreeNode) -> float:
    left_members = left.member_embeddings or [
        left.criteria_embedding or left.embedding
    ]
    right_members = right.member_embeddings or [
        right.criteria_embedding or right.embedding
    ]
    scores = [
        cosine_similarity(left_embedding, right_embedding)
        for left_embedding in left_members
        for right_embedding in right_members
    ]
    return min(scores) if scores else 0.0


def _pair_candidates(
    nodes: list[CaliTreeNode],
    threshold: float,
    blocked_pairs: Optional[set[frozenset[str]]] = None,
    compatible: Optional[
        Callable[[CaliTreeNode, CaliTreeNode], bool]
    ] = None,
    pair_score: Optional[Callable[[CaliTreeNode, CaliTreeNode], float]] = None,
) -> list[tuple[int, int, float]]:
    candidates: list[tuple[int, int, float]] = []
    for i, left in enumerate(nodes):
        for j in range(i + 1, len(nodes)):
            if (
                blocked_pairs is not None
                and frozenset((left.id, nodes[j].id)) in blocked_pairs
            ):
                continue
            if compatible is not None and not compatible(left, nodes[j]):
                continue
            score = (
                pair_score(left, nodes[j])
                if pair_score is not None
                else complete_link_similarity(left, nodes[j])
            )
            if score >= threshold:
                candidates.append((i, j, score))
    return sorted(candidates, key=lambda row: (-row[2], nodes[row[0]].id, nodes[row[1]].id))


def greedy_pairs(
    nodes: list[CaliTreeNode],
    threshold: float,
    blocked_pairs: Optional[set[frozenset[str]]] = None,
    compatible: Optional[
        Callable[[CaliTreeNode, CaliTreeNode], bool]
    ] = None,
    pair_score: Optional[Callable[[CaliTreeNode, CaliTreeNode], float]] = None,
) -> tuple[list[tuple[CaliTreeNode, CaliTreeNode, float]], list[CaliTreeNode]]:
    used: set[int] = set()
    pairs: list[tuple[CaliTreeNode, CaliTreeNode, float]] = []
    for i, j, score in _pair_candidates(
        nodes, threshold, blocked_pairs, compatible, pair_score
    ):
        if i not in used and j not in used:
            used.update((i, j))
            pairs.append((nodes[i], nodes[j], score))
    return pairs, [node for idx, node in enumerate(nodes) if idx not in used]
