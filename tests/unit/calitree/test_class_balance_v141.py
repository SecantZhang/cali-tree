import numpy as np
import pytest

from critical.core.calibration.class_balance_v141 import (
    ClassBalancedResidual, training_weights, classification_metrics)


def test_equal_class_mass_survives_original_anchor_multiplier():
    y = np.asarray([0, 0, 0, 1, 1, 2])
    original = np.asarray([True, False, False, True, False, True])
    w = training_weights(y, original=original, original_weight=25.)
    assert np.isclose(w.sum(), 1.)
    assert np.allclose([w[y == k].sum() for k in range(3)], 1/3)
    assert np.isclose(w[0]/w[1], 25.)
    assert np.isclose(w[3]/w[4], 25.)
    # Every example stays present; no majority examples are discarded.
    assert np.all(w > 0)


def test_source_normalization_precedes_class_normalization():
    y = [0, 0, 1, 2]
    groups = ['a', 'a', 'b', 'c']
    assert np.allclose(training_weights(y, groups=groups, balanced=False), [1/6, 1/6, 1/3, 1/3])
    assert np.allclose(training_weights(y, groups=groups), [1/6, 1/6, 1/3, 1/3])
    assert np.allclose(training_weights([0, 0, 1]), [.25, .25, .5])
    with pytest.raises(ValueError):
        training_weights([0, 3])
    with pytest.raises(ValueError):
        training_weights([0, 1], groups=['a'])


def test_unresolved_cases_remain_in_class_balanced_denominator():
    rows = [{'reference': 0, 'prediction': 0}, {'reference': 0, 'prediction': -1},
            {'reference': 1, 'prediction': 1}, {'reference': 2, 'prediction': -1}]
    m = classification_metrics(rows)
    assert m['accuracy'] == .5 and m['balanced_accuracy'] == .5
    assert m['unresolved'] == 2 and m['per_class']['no']['recall'] == .5
    assert m['per_class']['yes']['recall'] == 0.
    assert np.isclose(m['macro_f1'], (2/3+1)/3)


def test_balanced_residual_keeps_actual_original_veto():
    pytest.importorskip('catboost')
    X = np.asarray([[0.], [.2], [.8], [1.]])
    p = np.tile([.51, .48, .01], (4, 1))
    model = ClassBalancedResidual(['goal_progress'], depth=2, iterations=40).fit(X, [1]*4,
        support=p, groups=list('abcd'), protected_X=[[.5]], protected_y=[0],
        protected_support=[[.51, .48, .01]])
    assert model.strength == 0 and model.predict(X, support=p) == [0]*4
    assert model.metadata()['training_weights']['class_weight_mass'] == [0., 1., 0.]
