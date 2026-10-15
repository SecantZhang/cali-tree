from critical.core.decision.bound_witnesses import compile_record
from critical.core.decision.postcondition_binding import validate
from tests.unit.calitree.test_factual_rules import row
import pytest


def program():
    return {'postconditions':[{'source_quote':'make it green','physical_test':'The intended target is green without contrary original-color portions',
        'required_present':['requested_attribute_visible'],'required_absent':['contradictory_attribute_remains']}],
        'supporting_witnesses':['requested_attribute_visible'],'identity_witnesses':[],'collateral_witnesses':[]}


def test_concrete_attribute_conjunction_distinguishes_residual_from_complete():
    p=program();validate(p,'make it green')
    r=compile_record(row(requested_attribute_visible='true',contradictory_attribute_remains='true'),p)
    assert r['facts']['a_required_positive_witness_visible']=='true'
    assert r['facts']['all_bound_postconditions_established']=='false'
    assert r['facts']['requested_attribute_with_visible_residual']=='true'
    r=compile_record(row(requested_attribute_visible='true',contradictory_attribute_remains='false'),p)
    assert r['facts']['all_bound_postconditions_established']=='true'


def test_undecidable_test_means_no_visible_proof_not_a_false_physical_claim():
    r=compile_record(row(requested_attribute_visible='unknown',contradictory_attribute_remains='false'),program())
    assert r['facts']['all_bound_postconditions_established']=='false'
    assert r['facts']['a_required_physical_test_undecidable']=='true'
    assert r['facts']['all_bound_postconditions_contradicted']=='false'
    assert compile_record(None,program()) is None


def test_bound_instruction_program_rejects_grade_predicates_or_invented_anchors():
    p=program();p['postconditions'][0]['required_present']=['progress']
    with pytest.raises(ValueError):validate(p,'make it green')
    p=program();p['postconditions'][0]['source_quote']='a different instruction'
    with pytest.raises(ValueError):validate(p,'make it green')
