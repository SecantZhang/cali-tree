import numpy as np

from critical.core.calibration.tempered_weights_v147 import weights
from critical.core.calibration.class_balance_v141 import training_weights
from run.verify_calitree_balanced_search_v145 import scalar_calibration
from run.verify_calitree_tempered_balance_v148 import native_scores


def test_tempering_endpoints_match_original_and_full_balance_even_with_anchors():
    y = np.asarray([0, 0, 1, 2]); original = np.asarray([True, False, False, True])
    assert np.allclose(weights(y, 0., original, 5.), np.asarray([5, 1, 1, 5])/12)
    assert np.allclose(weights(y, 1., original, 5.), training_weights(y, original=original, original_weight=5.))
    counts = np.asarray([0]*8+[1, 2]); w = weights(counts, .5, np.zeros(10, dtype=bool))
    assert 1/3 < w[counts == 0].sum() < .8
    assert .1 < w[counts == 1].sum() < 1/3


def test_scalar_boundary_audit_obeys_threshold_equality_warrants_and_priority():
    artifact = {'selected': {'family': 'ordinal', 'parameters': [1., 1.5]}, 'warranted': True}
    assert scalar_calibration(artifact, [0., 1., 0.], 0, False, [True]*3) == 1
    assert scalar_calibration(artifact, [0., 1., 0.], 0, False, [True, False, True]) == 0
    assert scalar_calibration(artifact, [0., 1., 0.], 0, True, [True]*3) == 0


def test_native_head_audit_uses_float32_thresholds_scale_and_bias():
    border = float(np.float32(.7))
    native = {'features_info': {'float_features': [{'feature_index': 0, 'flat_feature_index': 0}]},
        'scale_and_bias': [2., [.1, .2, .3]], 'oblivious_trees': [{
        'splits': [{'split_type': 'FloatFeature', 'float_feature_index': 0, 'border': border}],
        'leaf_values': [0., 1., 2., 3., 4., 5.]}]}
    assert np.allclose(native_scores(native, [[border+1e-10], [border+1e-6]]), [[.1, 2.2, 4.3], [6.1, 8.2, 10.3]])
