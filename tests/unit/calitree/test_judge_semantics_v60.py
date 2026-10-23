from critical.core.calibration import judge_semantics_v60 as semantics
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft


def program(change):
    d = draft('Change the target color')
    d['contract']['authorized_changes'] = [change]
    return bind_program('Change the target color', d)


def test_intents_use_primary_authorization_and_not_retention_clause_or_object_names():
    a = semantics.project(program('Change the sphere color while keeping its matte finish.'), None)
    b = semantics.project(program('Change the hat color while keeping its glossy finish.'), None)
    assert a == b and a['intent_color'] and not a['intent_finish']
    c = semantics.project(program('Make the target surface matte.'), None)
    assert c['intent_finish'] and not c['intent_color']
    assert all(type(value) is bool for value in c.values())


def test_explanation_mentions_keep_polarity_and_clause_boundaries():
    values = semantics.project(None, {'label': 'partial', 'rationale': 'The change is not fully realized, but the scene is preserved.'})
    assert values['rationale_completion_mentioned'] and values['rationale_completion_negated']
    assert not values['rationale_completion_unnegated']
    assert values['rationale_retention_unnegated'] and not values['rationale_retention_negated']
    assert not values['intent_available'] and values['rationale_available']


def test_object_label_and_reference_fields_do_not_change_language_features():
    a = semantics.project(None, {'label': 'no', 'reference': 0, 'case': 'a', 'rationale': 'The hat is largely preserved with a minor deviation.'})
    b = semantics.project(None, {'label': 'yes', 'reference': 2, 'case': 'b', 'rationale': 'The sphere is largely preserved with a minor deviation.'})
    assert a == b and a['rationale_minor_extent_unnegated'] and a['rationale_qualified_extent_mentioned']
    assert semantics.project(None, None) == dict.fromkeys(semantics.SPECS, False)


def test_no_longer_visible_means_missing_not_negated_missing():
    f = semantics.project(None, {'rationale': 'The original entity is no longer visible.'})
    assert f['rationale_missing_unnegated'] and not f['rationale_missing_negated']
