import pytest

from critical.core.decision.facet_policy_v150 import decide, validate


def complete():
    return {'new_requested_content': 'some', 'all_material_facets': 'yes',
        'operation_fidelity': 'faithful', 'source_entity_fidelity': 'preserved',
        'scope_coverage': 'full', 'evidence': 'The requested result is visible.', 'material_gap': 'none'}


def test_new_subgoal_without_faithful_full_operation_is_partial():
    assert decide({**complete(), 'all_material_facets': 'no', 'operation_fidelity': 'unfaithful'}) == 1
    assert decide({**complete(), 'source_entity_fidelity': 'material_unrequested_change'}) == 1
    assert decide({**complete(), 'scope_coverage': 'partial'}) == 1
    assert decide(complete()) == 2


def test_no_progress_uncertainty_and_contradictions_are_distinct():
    assert decide({**complete(), 'new_requested_content': 'none', 'all_material_facets': 'no'}) == 0
    assert decide({**complete(), 'new_requested_content': 'none'}) is None
    assert decide({**complete(), 'new_requested_content': 'uncertain'}) is None
    assert decide({**complete(), 'operation_fidelity': 'uncertain'}) is None
    assert decide({**complete(), 'operation_fidelity': 'uncertain'}, cautious=True) == 1


def test_facet_contract_rejects_reference_fields_and_unbounded_evidence():
    with pytest.raises(ValueError):
        validate({**complete(), 'reference': 'yes'})
    with pytest.raises(ValueError):
        validate({**complete(), 'evidence': 'x'*401})
