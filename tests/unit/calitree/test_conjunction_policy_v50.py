import numpy as np
import pytest

from critical.core.calibration.semantic_conjunction_policy_v50 import SemanticConjunctionPolicy
from run import calitree_observer_diagnostic_v51r1 as diagnostic


def test_binary_semantic_conjunctions_represent_conditional_middle_class():
    X = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    y = np.asarray([0, 1, 1, 2])
    model = SemanticConjunctionPolicy(degree=2, C=1000).fit(X, y)
    assert model.converged and model.predict(X) == list(y)
    assert model.transform.n_output_features_ == 3
    probabilities = model.predict_proba(X)
    assert np.all(np.isfinite(probabilities)) and np.allclose(probabilities.sum(axis=1), 1)
    with pytest.raises(ValueError, match='Boolean'):
        SemanticConjunctionPolicy().fit([[0, .25], [1, 1]], [0, 1])


def test_fresh_observer_diagnostic_needs_new_authorization_before_credentials_or_files(tmp_path):
    out = tmp_path / 'not-created'
    with pytest.raises(ValueError, match='authorization'):
        diagnostic.collect(out, live=True)
    assert not out.exists()
    assert diagnostic.MAX_CALLS == 48
    assert diagnostic.MAX_OUTPUT == 589824
