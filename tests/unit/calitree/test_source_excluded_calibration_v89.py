import numpy as np
import pytest

from critical.core.calibration.source_excluded_calibration_v89 import BoundaryCalibration, source_excluded_views


def test_in_sample_originals_do_not_enter_excluded_source_mask():
    p = np.tile([.8, .1, .1], (4, 1)); q = np.tile([.2, .7, .1], (4, 1))
    m = {'train': [0, 1], 'training_sources': ['original'], 'held_sources': ['inner']}
    mixed, mask = source_excluded_views(p, [0, 1, 2], [3], ['original', 'original', 'inner', 'outer'], [(m, q)])
    assert mask.tolist() == [False, False, True, False]
    assert np.array_equal(mixed[[0, 1, 3]], p[[0, 1, 3]])
    assert np.array_equal(mixed[2], q[2])
    with pytest.raises(ValueError, match='repeated'):
        source_excluded_views(p, [0, 1, 2], [3], ['original', 'original', 'inner', 'outer'], [(m, q), (m, q)])


def test_teacher_membership_and_outer_exclusion_are_required():
    p = np.tile([.8, .1, .1], (3, 1))
    with pytest.raises(ValueError, match='Outer source leakage'):
        source_excluded_views(p, [0, 1], [2], ['x', 'y', 'y'], [])
    m = {'train': [0, 1], 'training_sources': ['a', 'b'], 'held_sources': ['b']}
    with pytest.raises(ValueError, match='membership'):
        source_excluded_views(p, [0, 1], [2], ['a', 'b', 'c'], [(m, p)])


def test_actual_original_veto_overrides_desirable_training_shift():
    p = np.tile([.51, .48, .01], (4, 1))
    model = BoundaryCalibration().fit(p, [1]*4, list('abcd'), protected_support=p[:1], protected_y=[0])
    assert model.predict(p).tolist() == [0]*4
    assert model.bias.tolist() == [0., 0., 0.]


def test_affirmative_warrant_vetoes_a_new_grade_without_asserting_failure():
    p = np.tile([.51, .48, .01], (4, 1)); w = np.tile([False, True, False], (4, 1))
    model = BoundaryCalibration().fit(p, [1]*4, list('abcd'), protected_support=[[.99, .005, .005]],
                                      protected_y=[0], warrants=w, protected_warrants=np.zeros((1, 3), dtype=bool))
    assert model.predict(p, warrants=w).tolist() == [1]*4
    assert model.predict(p, warrants=np.zeros((4, 3), dtype=bool)).tolist() == [0]*4
    assert model.selected['retained']
