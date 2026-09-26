"""Serializable CaliTree node state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CaliTreeNode:
    id: str
    prompt: str
    covered_ids: list[str]
    embedding: list[float]
    components: dict[str, list[str]]
    level: int = 0
    status: str = "leaf"
    children: list[str] = field(default_factory=list)
    validation_accuracy: float = 0.0
    routing_threshold: float = 0.70
    conflict_reason: str = ""
    criteria_embedding: list[float] = field(default_factory=list)
    member_embeddings: list[list[float]] = field(default_factory=list)
    generalization_accuracy: Optional[float] = None
    semantic_groups: list[str] = field(default_factory=list)
    # Specialized routing is opt-in when a held-out leaf cohort exists. A leaf that does
    # not match or beat the root on enough validation cases remains useful for clustering
    # but cannot intercept unseen cases.
    routing_eligible: bool = True
    routing_validation_support: int = 0
    routing_validation_accuracy: Optional[float] = None
    routing_baseline_accuracy: Optional[float] = None
    # A normalized no/partial/yes confusion profile measured after leaf optimization.
    # It is deliberately derived from predictions, not prompt wording, so clustering can
    # discover leaves with compatible decision boundaries.
    behavior_profile: list[float] = field(default_factory=list)
