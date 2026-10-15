from critical.core.decision.intent_role_facts import compile_record,EXCLUDED
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_physical_witness_program import mid
from tests.unit.calitree.test_bound_witnesses import program


def test_identity_motion_failure_is_separate_from_appearance_changes():
    p=program();p['identity_witnesses']=['original_instance_at_source','counterpart_at_destination','target_markings_or_size_changed']
    x=compile_record(row(original_instance_at_source='true',counterpart_at_destination='false',target_markings_or_size_changed='true'),p,mid())
    assert x['facts']['selected_original_source_persistence_observed']=='true'
    assert x['facts']['selected_destination_counterpart_failure_observed']=='true'
    assert not set(x['facts'])&EXCLUDED


def test_unselected_appearance_difference_cannot_become_an_identity_veto():
    p=program();p['identity_witnesses']=['target_markings_or_size_changed']
    x=compile_record(row(target_markings_or_size_changed='true'),p,mid())
    assert x['facts']['selected_original_source_persistence_observed']=='false'
    assert x['facts']['selected_destination_counterpart_failure_observed']=='false'
