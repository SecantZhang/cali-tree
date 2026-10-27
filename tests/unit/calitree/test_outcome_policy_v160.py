from critical.core.decision import outcome_policy_v160 as outcome, facet_policy_v150 as previous


def record(**changes):
    return {'new_requested_content': 'some', 'all_material_facets': 'yes', 'operation_fidelity': 'faithful',
            'source_entity_fidelity': 'preserved', 'scope_coverage': 'full', 'evidence': 'Visible requested result',
            'material_gap': 'none', **changes}


def test_completed_requested_outcome_is_separate_from_source_quality_caps():
    v = record(operation_fidelity='unfaithful', source_entity_fidelity='material_unrequested_change', material_gap='Unrequested accessory changed')
    assert previous.decide(v) == 1 and outcome.decide(v) == 2
    assert outcome.decide(record(all_material_facets='no', material_gap='Requested placement incomplete')) == 1


def test_absence_unknown_and_inconsistent_scope_never_become_full_fulfillment():
    assert outcome.decide(record(new_requested_content='none', all_material_facets='no')) == 0
    assert outcome.decide(record(new_requested_content='none', all_material_facets='yes')) is None
    assert outcome.decide(record(new_requested_content='uncertain')) is None
    assert outcome.decide(record(all_material_facets='uncertain')) is None
    assert outcome.decide(record(scope_coverage='partial')) is None
