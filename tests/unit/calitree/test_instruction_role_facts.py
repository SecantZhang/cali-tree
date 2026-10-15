from critical.core.decision.instruction_role_facts import compile_record,semantic_priority
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_physical_witness_program import mid
from tests.unit.calitree.test_bound_witnesses import program


def test_same_count_increase_is_a_relocation_conflict_only_in_relocation_role():
    f=row(target_instance_count_increased='true');p=program()
    assert compile_record(f,p,mid())['facts']['relocation_duplicate_observed']=='false'
    p['identity_witnesses']=['original_instance_displaced']
    assert compile_record(f,p,mid())['facts']['relocation_duplicate_observed']=='true'


def test_requested_constraints_precede_incidental_support_in_equal_coverage_ties():
    assert semantic_priority('relocation_duplicate_observed')<semantic_priority('instruction_related_intermediate_witness')
