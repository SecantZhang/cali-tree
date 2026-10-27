from critical.core.calibration.semantic_warrants_v71 import warranted, WarrantedRubric
from critical.core.calibration.semantic_rubric_v70 import Config


def terms(*names):
    return [{'feature': n, 'value': True} for n in names]


def test_uncertainty_and_task_kind_are_not_failure_evidence():
    assert not warranted(0, terms('meaning_endpoint_gap_uncertain_all',
                                 'meaning_collateral_materiality_uncertain_all', 'requires_attribute'))
    assert warranted(0, terms('meaning_progress_none_all', 'intent_finish'))


def test_partial_requires_progress_or_an_achieved_endpoint_with_a_shortfall():
    assert not warranted(1, terms('meaning_endpoint_gap_none_all', 'requires_absence'))
    assert warranted(1, terms('meaning_progress_toward_requested_goal_any'))
    assert warranted(1, terms('meaning_progress_requested_endpoint_all',
                             'meaning_collateral_materiality_material_unrequested_change_any'))


def test_yes_requires_endpoint_identity_and_collateral_warrants():
    base = terms('meaning_progress_requested_endpoint_all', 'meaning_identity_materiality_no_shortfall_all')
    assert not warranted(2, base)
    assert warranted(2, base + terms('meaning_collateral_materiality_none_all'))


def test_unestablished_opposite_and_similarity_are_not_positive_warrants():
    assert not warranted(2, [{'feature': 'meaning_progress_none_all', 'value': False}])
    assert not warranted(2, terms('vision_target_match_ge_0.9'))


def test_fitting_rejects_an_accurate_uncertainty_shortcut_but_keeps_failure_witnesses():
    names = ['meaning_endpoint_gap_uncertain_all', 'meaning_collateral_materiality_uncertain_all',
             'meaning_progress_none_all', 'intent_finish']
    X = [[1, 1, 0, 1]] * 3 + [[0, 0, 1, 1]] * 3 + [[0, 0, 0, 0]] * 2
    y = [0] * 6 + [2] * 2
    rubric = WarrantedRubric(names, Config(min_sources=2)).fit(X, y, groups=list('abcdefgh'))
    assert rubric.rules and all(warranted(r['prediction'], r['conditions']) for r in rubric.rules)
    assert rubric.predict(X[:1], base_predictions=[2]) == [2]
    assert rubric.predict(X[3:4], base_predictions=[2]) == [0]


def test_essential_identity_requires_affirmative_loss_not_missing_positive_evidence():
    condition = terms('meaning_retention_need_same_instance_essential_all')
    assert not warranted(0, condition + [{'feature': 'identity_all_true_all', 'value': False}])
    assert warranted(0, condition + terms('identity_all_false_all'))
