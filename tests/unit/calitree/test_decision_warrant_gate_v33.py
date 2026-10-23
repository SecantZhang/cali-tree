from copy import deepcopy

from critical.core.calibration.decision_warrant_gate_v33 import certificate
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record


def yes_record():
    return synthetic_record(meaning_available=True,meaning_progress_requested_endpoint_all=True,
        meaning_endpoint_gap_none_all=True,meaning_evidence_consistency_coherent_all=True,outcome_all_true_all=True,
        meaning_identity_materiality_no_shortfall_any=True,meaning_collateral_materiality_none_any=True)


def no_record():
    return synthetic_record(meaning_available=True,meaning_progress_none_all=True,meaning_progress_none_any=True,
        meaning_endpoint_gap_core_endpoint_missing_all=True,meaning_endpoint_gap_core_endpoint_missing_any=True,
        meaning_evidence_consistency_coherent_all=True,outcome_all_false_all=True)


def test_affirmative_success_and_failure_warrants():
    assert certificate(yes_record())==2
    assert certificate(no_record())==0
    assert certificate(None)is None


def test_no_cannot_be_inferred_merely_from_absence_of_positive_flags():
    empty=synthetic_record(meaning_available=True,meaning_evidence_consistency_coherent_all=True,outcome_all_false_all=True)
    assert certificate(empty)is None


def test_uncertainty_partial_progress_and_material_damage_prevent_unwarranted_answers():
    for flag in ('meaning_progress_uncertain_any','meaning_progress_toward_requested_goal_any','meaning_endpoint_gap_uncertain_any'):
        changed=no_record();changed['features'][flag]=True
        assert certificate(changed)is None
    for flag in ('meaning_identity_materiality_uncertain_any','meaning_identity_materiality_material_shortfall_any',
                 'meaning_collateral_materiality_material_unrequested_change_any'):
        changed=yes_record();changed['features'][flag]=True
        assert certificate(changed)is None


def test_authorized_transformation_does_not_require_identical_instance():
    record=yes_record();record['features']['meaning_identity_evidence_recognizable_transformed_counterpart_all']=True
    record['features']['meaning_retention_need_recognizable_counterpart_sufficient_all']=True
    assert not record['features']['meaning_identity_evidence_same_instance_all']
    assert certificate(record)==2
