import numpy as np
import pytest

from critical.core.calibration.numeric_semantics_v66 import NumericSemanticPolicy, NUMERIC
from run.paired_vision_features_v63 import BOUNDS
from run.spatial_vision_features_v65 import SCORES


def test_runtime_numeric_whitelist_matches_projection_contracts():
    assert NUMERIC == {'score_' + name for name in (*BOUNDS, *SCORES)}


def test_only_declared_comparison_scores_accept_continuous_values():
    names = ['meaning_progress_none_all', 'score_property_delta_mean']
    model = NumericSemanticPolicy(names)
    assert model.validate([[0, .0014], [1, -.001]]).shape == (2, 2)
    with pytest.raises(ValueError, match='Boolean'):
        model.validate([[.2, .001]])
    with pytest.raises(ValueError, match='bounds'):
        model.validate([[1, 5.]])
    with pytest.raises(ValueError, match='Declared'):
        NumericSemanticPolicy(['case_id'])


def test_numeric_thresholds_can_retain_small_relative_changes():
    X = np.asarray([[0., -.002], [0., 0.], [0., .0014], [0., .003], [1., -.003], [1., .003]], dtype=np.float32)
    y = np.asarray([0, 0, 1, 2, 0, 2])
    model = NumericSemanticPolicy(['meaning_progress_none_all', 'score_property_delta_mean'])
    model.fit(X, y, original=np.ones(len(X), dtype=bool))
    assert model.predict(X) == y.tolist() and model.original_correct == len(X)
    assert model.original_weight == 1.
