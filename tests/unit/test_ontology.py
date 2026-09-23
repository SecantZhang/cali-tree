"""The calibration ontology is assembled from the existing taxonomy + crosswalk; these
guard the assembly (no drift from the taxonomy) and the importance semantics the semantic
tree relies on."""

from vejudge.core.calibration import ontology as o
from vejudge.core.calibration.debate.calibrated_result import _TENDENCY
from vejudge.core.prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from vejudge.database.dl_human_annotations import HUMAN_DIMENSIONS


def test_concepts_cover_the_taxonomy_exactly():
    # Drift guard: the ontology's concept set is the taxonomy's key set, no more no less.
    assert set(o.CONCEPTS) == set(FAILURE_MODE_TAXONOMY) == set(_TENDENCY)


def test_each_concept_is_well_formed():
    dims = set(HUMAN_DIMENSIONS)
    for key, c in o.CONCEPTS.items():
        assert c.label == _TENDENCY[key]
        assert c.description == FAILURE_MODE_TAXONOMY[key]
        assert c.family in o.FAMILY_LABELS
        assert set(c.affects_dimensions) <= dims  # only real human dimensions


def test_importance_rises_with_dimension_overlap():
    # audio_neglect overlaps M5 (a voiceover-flow dimension) but not M3 (prompt only).
    assert o.concept_importance("audio_neglect", "M5") > o.concept_importance("audio_neglect", "M3")
    # A concept touching every dimension maxes out for any metric.
    assert o.concept_importance("scale_drift", "M5") == 1.0


def test_off_metric_and_unmapped_concepts_get_the_floor():
    # Pairwise-only biases don't touch absolute-scoring dimensions -> floor.
    assert o.concept_importance("position_bias", "M5") == o._IMPORTANCE_FLOOR
    # Unknown key -> floor; base_score (None) is always fully relevant.
    assert o.concept_importance("not_a_concept", "M5") == o._IMPORTANCE_FLOOR
    assert o.concept_importance(None, "M5") == 1.0


def test_concept_for_feature_parses_the_naming_convention():
    assert o.concept_for_feature("fm:audio_neglect") == "audio_neglect"
    assert o.concept_for_feature("rule:frame_only_blindness") == "frame_only_blindness"
    assert o.concept_for_feature("base_score") is None
    assert o.concept_for_feature("fm:not_a_concept") is None
