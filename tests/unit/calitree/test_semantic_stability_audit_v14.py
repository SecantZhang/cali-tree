from copy import deepcopy

import pytest

from critical.core.calibration.semantic_hierarchy.portable_features_v8 import validate_record
from run.audit_calitree_semantic_stability_v14 import probe, conflicts


def requirement(progress='requested_endpoint', gap='none'):
    return {'progress': progress, 'endpoint_gap': gap, 'retention_need': 'same_instance_essential',
        'identity_evidence': 'same_instance', 'identity_materiality': 'no_shortfall',
        'collateral_materiality': 'none', 'evidence_consistency': 'coherent'}


def test_mixed_requirements_distinguish_any_and_all_without_reference_labels():
    record = probe([requirement(), requirement('none', 'core_endpoint_missing')])
    validate_record(record)
    f = record['features']
    assert f['meaning_progress_requested_endpoint_any'] and not f['meaning_progress_requested_endpoint_all']
    assert f['meaning_progress_none_any'] and not f['meaning_progress_none_all']
    assert f['meaning_collateral_materiality_none_all']


def test_exact_duplicate_and_requirement_order_do_not_change_quantifiers():
    a, b = requirement(), requirement('toward_requested_goal', 'minor_detail')
    assert probe([a, b]) == probe([b, a]) == probe([a, b, a])


def test_conflict_diagnostic_never_rewrites_evidence_or_assigns_a_new_label():
    record = probe([requirement('incidental_change_only', 'core_endpoint_missing')]); before = deepcopy(record)
    flags = conflicts(2, record)
    assert 'meaning_progress_incidental_change_only_all' in flags
    assert 'meaning_endpoint_gap_core_endpoint_missing_all' in flags
    assert record == before
    assert conflicts(-1, record) == [] and conflicts(2, None) == []
    uncertain = probe([requirement('uncertain', 'uncertain')])
    assert conflicts(2, uncertain) == []  # Uncertainty is not a known negative.


def test_probes_reject_hidden_reference_fields_and_invalid_states():
    with pytest.raises(ValueError, match='valid semantic'):
        probe([{**requirement(), 'reference': 2}])
    with pytest.raises(ValueError, match='valid semantic'):
        probe([requirement('made_up_state')])
