"""Deterministic, immutable summaries of unreduced human-rating disagreement."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any, Sequence


PROFILE_VERSION = "human-disagreement-v1"


def build_disagreement_profile(scores: Sequence[float]) -> dict[str, Any]:
    values = sorted(float(score) for score in scores)
    if not values:
        return {}
    counts = Counter(values)
    max_count = max(counts.values())
    modes = sorted(score for score, count in counts.items() if count == max_count)
    spread = values[-1] - values[0]
    polarized = spread >= 2.0 and len(values) >= 2
    return {
        "version": PROFILE_VERSION,
        "rating_count": len(values),
        "histogram": {f"{score:g}": counts[score] for score in sorted(counts)},
        "minimum": values[0],
        "maximum": values[-1],
        "range": spread,
        "median": float(median(values)),
        "modes": modes,
        "polarized": polarized,
        "required_perspectives": [
            "Identify observable evidence supporting the lower-rating interpretation.",
            "Identify observable evidence supporting the higher-rating interpretation.",
            "State a stable semantic tradeoff without selecting an annotator as the target.",
        ] if polarized else [
            "Identify observable evidence that explains the rating pattern.",
            "State a stable semantic evaluation principle rather than a target score.",
        ],
    }
