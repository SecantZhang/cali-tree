"""Calibration knowledge base — a small ontology of judge failure-mode *concepts*.

Assembled from what already exists, not invented: the 10 keys of
``FAILURE_MODE_TAXONOMY`` (prompt content) + their ``_TENDENCY`` verb-phrase labels, an
``is-a`` grouping into concept families, and a hand-authored ``affects_dimensions`` link to
the human dimensions each bias distorts (grounded in the ``ALIGNMENT`` crosswalk). This is
the "knowledge base" a Semantic Decision Tree uses: ``concept_importance(key, metric)``
turns the ontology into the paper's per-attribute importance weight (overlap of a concept's
affected dimensions with the metric being calibrated), so split selection can be biased
toward semantically relevant concepts.

Versioned (``ONTOLOGY_VERSION``) and hand-authored at v1 (the family/affects mappings are a
judgement call and expected to be revised); a drift test pins the concept set to the
taxonomy so the two never diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from ...postprocessing.align import ALIGNMENT
from .debate.calibrated_result import _TENDENCY

ONTOLOGY_VERSION = "ontology-v1"

# metric_id -> the human dimensions it maps to (reverse of ALIGNMENT; same construction as
# cl_adversarial_node._DIMENSIONS_FOR_METRIC, rebuilt here to keep core decoupled from the
# interface layer).
_DIMENSIONS_FOR_METRIC: dict[str, list[str]] = {}
for _dim, (_mid, _extractor) in ALIGNMENT.items():
    _DIMENSIONS_FOR_METRIC.setdefault(_mid, []).append(_dim)


@dataclass(frozen=True)
class Concept:
    key: str                          # taxonomy key — the stable id
    label: str                        # short verb phrase (from _TENDENCY)
    description: str                  # full sentence (from FAILURE_MODE_TAXONOMY)
    family: str                       # is-a parent (a family id below)
    affects_dimensions: tuple[str, ...]  # subset of HUMAN_DIMENSIONS this bias distorts


# is-a families grouping the 10 concepts (hand-authored v1).
FAMILY_LABELS: dict[str, str] = {
    "instruction_fidelity": "Instruction fidelity",
    "perceptual_completeness": "Perceptual completeness",
    "rationale_quality": "Rationale quality",
    "scale_consistency": "Scale consistency",
    "comparison_bias": "Comparison bias",
}

# Which human dimensions each failure mode tends to distort (hand-authored v1, grounded in
# the ALIGNMENT crosswalk). Global/meta biases (rationale/scale/category) touch every
# dimension; the pairwise-only biases touch none of the absolute-scoring dimensions.
_ALL_DIMS = tuple(d for d in ALIGNMENT)  # the 9 scored human dimensions

_AFFECTS: dict[str, tuple[str, ...]] = {
    "surface_realism_bias": (
        "video_addresses_prompt", "story_flow_voiceover", "story_flow_visuals",
    ),
    "source_drift_blindness": (
        "story_flow_visuals", "section_placement_opening", "section_placement_middle",
        "section_placement_closing",
    ),
    "frame_only_blindness": ("abrupt_cutoffs_video", "story_flow_visuals"),
    "audio_neglect": (
        "voiceover_matches_visuals", "abrupt_cutoffs_voiceover", "story_flow_voiceover",
    ),
    "long_video_compression": (
        "story_flow_voiceover", "story_flow_visuals", "section_placement_middle",
    ),
    "overconfident_rationale": _ALL_DIMS,   # meta: can distort any dimension's score
    "scale_drift": _ALL_DIMS,               # calibration: affects every dimension
    "category_imbalance": _ALL_DIMS,        # calibration: affects every dimension
    "position_bias": (),                    # pairwise-only; irrelevant to absolute scoring
    "self_bias": (),                        # pairwise-only; irrelevant to absolute scoring
}

_FAMILY_OF: dict[str, str] = {
    "surface_realism_bias": "instruction_fidelity",
    "source_drift_blindness": "instruction_fidelity",
    "frame_only_blindness": "perceptual_completeness",
    "audio_neglect": "perceptual_completeness",
    "long_video_compression": "perceptual_completeness",
    "overconfident_rationale": "rationale_quality",
    "scale_drift": "scale_consistency",
    "category_imbalance": "scale_consistency",
    "position_bias": "comparison_bias",
    "self_bias": "comparison_bias",
}

CONCEPTS: dict[str, Concept] = {
    key: Concept(
        key=key,
        label=_TENDENCY[key],
        description=FAILURE_MODE_TAXONOMY[key],
        family=_FAMILY_OF[key],
        affects_dimensions=_AFFECTS[key],
    )
    for key in FAILURE_MODE_TAXONOMY
}

# Never let a mapped concept weigh exactly zero on a metric it doesn't directly touch — a
# small floor keeps it eligible but strongly de-prioritized vs. an on-metric concept.
_IMPORTANCE_FLOOR = 0.1


def concept_importance(key: Optional[str], metric_id: str, *, floor: float = _IMPORTANCE_FLOOR) -> float:
    """Ontology-derived attribute importance in [floor, 1]: the fraction of the metric's
    human dimensions that this concept distorts. ``None``/``base_score`` (not a concept)
    → 1.0 (the judge's own score is always relevant). Unknown key or a metric with no human
    dimensions → the floor.
    """
    if key is None:
        return 1.0
    dims = _DIMENSIONS_FOR_METRIC.get(metric_id, [])
    concept = CONCEPTS.get(key)
    if not dims or concept is None:
        return floor
    overlap = len(set(concept.affects_dimensions) & set(dims))
    return max(floor, overlap / len(dims))


def concept_for_feature(name: str) -> Optional[str]:
    """Recover the concept key from a feature name (``fm:<key>`` / ``rule:<key>``).
    ``base_score`` and any un-prefixed name → None (no concept; importance 1.0)."""
    if name.startswith("fm:"):
        key = name[3:]
    elif name.startswith("rule:"):
        key = name[5:]
    else:
        return None
    return key if key in CONCEPTS else None


def feature_labels() -> dict[str, str]:
    """concept key → human-readable label, for the UI tooltip on a semantic split."""
    return {key: c.label for key, c in CONCEPTS.items()}
