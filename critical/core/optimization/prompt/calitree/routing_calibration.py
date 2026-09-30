"""Templates for calibrating routing edges; inference remains in routing.py."""

from abc import ABC, abstractmethod

from .geometry import cosine_similarity
from .node import CaliTreeNode


class RoutingCalibrator(ABC):
    @abstractmethod
    def calibrate(
        self, nodes: dict[str, CaliTreeNode], case_embeddings: dict[str, list[float]],
        *, margin: float,
    ) -> None:
        """Update child thresholds in place."""
        ...


class GeometryRoutingCalibrator(RoutingCalibrator):
    def calibrate(
        self, nodes: dict[str, CaliTreeNode], case_embeddings: dict[str, list[float]],
        *, margin: float,
    ) -> None:
        """Calibrate every parent→child edge from training instruction geometry."""
        for parent in nodes.values():
            children = [nodes[node_id] for node_id in parent.children if node_id in nodes]
            for child in children:
                positives = [
                    cosine_similarity(case_embeddings[item_id], child.embedding)
                    for item_id in child.covered_ids
                    if item_id in case_embeddings
                ]
                negative_ids = {
                    item_id
                    for sibling in children
                    if sibling.id != child.id
                    for item_id in sibling.covered_ids
                }
                negatives = [
                    cosine_similarity(case_embeddings[item_id], child.embedding)
                    for item_id in sorted(negative_ids)
                    if item_id in case_embeddings
                ]
                if not positives:
                    child.routing_threshold = 1.0
                    continue
                positive_floor = min(positives)
                if negatives:
                    negative_ceiling = max(negatives)
                    if positive_floor > negative_ceiling:
                        threshold = (positive_floor + negative_ceiling) / 2
                    else:
                        threshold = (
                            sum(positives) / len(positives)
                            + sum(negatives) / len(negatives)
                        ) / 2
                    threshold += margin
                else:
                    threshold = positive_floor - margin
                child.routing_threshold = max(-1.0, min(1.0, threshold))
