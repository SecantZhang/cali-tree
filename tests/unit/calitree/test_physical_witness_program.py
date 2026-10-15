from critical.core.decision.physical_witness_program import compile_record,CORE,SUPPORT
from critical.core.decision.intermediate_facts import PREDICATES
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_bound_witnesses import program


def mid(**facts):return {'facts':{k:facts.get(k,'not_applicable') for k in PREDICATES}}


def test_positive_witness_and_residual_constraints_are_distinct_physical_assertions():
    x=compile_record(row(requested_attribute_visible='true',contradictory_attribute_remains='true'),program(),mid())
    assert x['facts']['all_positive_physical_assertions_established']=='true'
    assert x['facts']['all_bound_postconditions_established']=='false'
    assert x['facts']['a_forbidden_physical_condition_visible']=='true'


def test_intermediate_requires_concrete_operation_related_configuration():
    x=compile_record(row(),program(),mid(actor_limb_position_changed='true'))
    assert x['facts']['instruction_related_intermediate_witness']=='false'
    x=compile_record(row(),program(),mid(arm_directed_toward_target='true'))
    assert x['facts']['instruction_related_intermediate_witness']=='true'
    assert 'instruction_related_intermediate_witness' in SUPPORT
    assert 'instruction_related_intermediate_witness' not in CORE


def test_no_visible_deformation_witness_does_not_impute_absent_deformation():
    x=compile_record(row(unrequested_entity_deformed='unknown'),program(),mid())
    assert x['facts']['unrequested_entity_deformed']=='unknown'
    assert x['facts']['unrequested_deformation_observed']=='false'
