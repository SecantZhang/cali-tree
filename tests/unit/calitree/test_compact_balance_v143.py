import numpy as np

from critical.core.calibration.compact_balance_v143 import CompactBalance, predict, recalls


def fitting_case():
    p = np.asarray([[.9, .05, .05]]*6+[[.6, .35, .05]]*3+[[.1, .1, .8]])
    y = np.asarray([0]*8+[1, 2])
    return p, y, np.argmax(p, axis=1), np.zeros(10, dtype=bool), np.ones((10, 3), dtype=bool)


def protection(*, ambiguous=False):
    return {'protected_support': [[.6, .35, .05]] if ambiguous else np.empty((0, 3)),
        'protected_y': [0] if ambiguous else [], 'protected_base': [0] if ambiguous else [],
        'protected_locked': np.zeros(1 if ambiguous else 0, dtype=bool),
        'protected_warrants': np.ones((1 if ambiguous else 0, 3), dtype=bool)}


def test_direct_balanced_objective_can_prefer_minority_recall_over_raw_accuracy():
    p, y, base, locked, w = fitting_case()
    model = CompactBalance().fit(p, y, base, locked, w, **protection())
    predicted = model.predict(p, base, locked, w)
    assert np.mean(recalls(y, predicted)) > np.mean(recalls(y, base))
    assert np.mean(predicted == y) < np.mean(base == y)
    assert predicted[8] == 1


def test_original_protection_and_fitting_per_class_floor_veto_harmful_settings():
    p, y, base, locked, w = fitting_case()
    protected = CompactBalance().fit(p, y, base, locked, w, **protection(ambiguous=True))
    pareto = CompactBalance(pareto=True).fit(p, y, base, locked, w, **protection())
    assert np.array_equal(protected.predict(p, base, locked, w), base)
    assert np.array_equal(pareto.predict(p, base, locked, w), base)


def test_uncertainty_does_not_supply_a_grade_warrant_and_locked_rules_keep_priority():
    p = [[.6, .35, .05]]*3
    w = np.asarray([[False, False, False], [False, True, False], [False, True, False]])
    result = predict(p, [0]*3, [False, False, True], w, family='bias', parameters=[1., 0.], warranted=True)
    assert result.tolist() == [0, 1, 0]


def test_ordered_threshold_equality_uses_the_upper_region():
    result = predict([[0., 1., 0.], [.25, 0., .75]], [0, 0], [False, False],
        np.ones((2, 3), dtype=bool), family='ordinal', parameters=[1., 1.5], warranted=True)
    assert result.tolist() == [1, 2]
