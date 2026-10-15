from critical.core.decision.role_bound_witnesses import compile_record
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_physical_witness_program import mid


def program(required_absent):
    return {'postconditions':[{'source_quote':'instruction','physical_test':'Concrete state',
        'required_present':['orientation_landmarks_match'],'required_absent':required_absent}],
        'supporting_witnesses':[],'identity_witnesses':['target_markings_or_size_changed'],'collateral_witnesses':[]}


def test_identification_attribute_is_not_automatically_an_outcome_constraint():
    facts=row(orientation_landmarks_match='true',specified_entity_attribute_conflict='true',target_markings_or_size_changed='true')
    descriptive=compile_record(facts,program([]),mid())
    outcome=compile_record(facts,program(['specified_entity_attribute_conflict']),mid())
    assert descriptive['facts']['requested_entity_attribute_conflict_observed']=='false'
    assert outcome['facts']['requested_entity_attribute_conflict_observed']=='true'
    assert descriptive['facts']['specified_entity_attribute_conflict']=='true'


def test_authorized_addition_count_increase_is_not_a_requested_conflict():
    facts=row(orientation_landmarks_match='true',target_instance_count_increased='true')
    assert compile_record(facts,program([]),mid())['facts']['requested_count_or_multiplicity_conflict_observed']=='false'
    assert compile_record(facts,program(['target_instance_count_increased']),mid())['facts']['requested_count_or_multiplicity_conflict_observed']=='true'
