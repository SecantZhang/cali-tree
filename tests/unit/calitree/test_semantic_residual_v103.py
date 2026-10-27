import numpy as np
import pytest

from critical.core.calibration.semantic_residual_v103 import SemanticResidual, corrected_support


def test_zero_strength_exactly_preserves_normalized_teacher_and_invalid_shapes_fail():
    p = np.asarray([[.7, .2, .1], [.1, .5, .4]])
    assert np.allclose(corrected_support(p, np.ones_like(p), 0), p)
    with pytest.raises(ValueError, match='residual'):
        corrected_support(p, np.ones((1, 3)), 1)
    result = corrected_support(p, [[-.9, .6, .3], [0, -.9, .9]], 1)
    assert np.all(result >= 0) and np.allclose(result.sum(axis=1), 1)


def test_actual_original_veto_blocks_a_desirable_training_shift():
    pytest.importorskip('catboost')
    X = np.asarray([[0.], [.2], [.8], [1.]])
    p = np.tile([.51, .48, .01], (4, 1))
    model = SemanticResidual(['goal_progress'], depth=2, iterations=40).fit(X, [1]*4, support=p, groups=list('abcd'),
            protected_X=[[.5]], protected_y=[0], protected_support=[[.51, .48, .01]])
    assert model.strength == 0 and model.predict(X, support=p) == [0]*4
