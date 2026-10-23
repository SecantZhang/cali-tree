import numpy as np
import pytest

from critical.core.calibration.ordinal_boost_v62 import ordered_probabilities, mean_support, centered_targets, OrdinalBoost


def test_ordered_boundaries_project_inversions_and_keep_three_class_mass():
    actual = ordered_probabilities([.8, .2], [.3, .8])
    assert np.allclose(actual, [[.2, .5, .3], [.5, 0, .5]])
    assert np.all(actual >= 0) and np.allclose(actual.sum(axis=1), 1)


def test_mean_bins_keep_declared_half_point_ties_without_tuned_thresholds():
    support = mean_support([0., .499, .5, 1., 1.499, 1.5, 2.])
    assert np.argmax(support, axis=1).tolist() == [0, 0, 1, 1, 1, 2, 2]


def test_relative_targets_use_only_supplied_same_task_fitting_rows():
    targets = centered_targets([0., 1., 2., 2.], ['a', 'a', 'b', 'b'])
    assert np.allclose(targets, [[0, -.5], [1, .5], [2, 0], [2, 0]])


@pytest.mark.parametrize('family', ['multiclass', 'ordinal', 'relative_mean'])
def test_small_fit_has_no_identity_argument_at_prediction(family):
    pytest.importorskip('catboost')
    X = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]] * 3, dtype=np.float32)
    y = np.asarray([0, 1, 2, 2] * 3)
    original = np.arange(len(X)) < 4
    model = OrdinalBoost(family=family, depth=2, iterations=80)
    model.fit(X, y, original=original, means=y, tasks=np.repeat(np.arange(3), 4))
    assert model.predict(X[original]) == [0, 1, 2, 2]
