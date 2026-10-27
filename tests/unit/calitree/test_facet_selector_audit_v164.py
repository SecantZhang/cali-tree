import pytest

from run.verify_calitree_facet_selector_v164 import check_boolean_union


def rule(**conditions):
    return {'from_grade': 0, 'grade': 2,
        'conditions': [{'feature': n, 'value': v} for n, v in conditions.items()]}


def test_boolean_audit_checks_states_absent_from_the_observed_examples():
    native = [rule(facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=True)]
    # This incorrect generalization agrees whenever faithful=True, but must
    # fail on the unobserved faithful=False states.
    with pytest.raises(AssertionError):
        check_boolean_union(native, [rule(facet_yes_outcome_ready=True)])


def test_boolean_audit_accepts_exact_shared_region_union():
    native = [rule(facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=True),
              rule(facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=False)]
    assert check_boolean_union(native, [rule(facet_yes_outcome_ready=True)]) == 32
