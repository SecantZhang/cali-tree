import json

import numpy as np
import pytest

from critical.core.calibration.single_tree_v173 import SingleTree, execute, ANCHOR_WEIGHTS


def fitted(leaves=4, balanced=True):
    X = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=bool)
    y = np.asarray([0, 1, 2, 2])
    model = SingleTree(['progress', 'complete'], leaves=leaves, balanced=balanced).fit(
        X, y, groups=['a', 'b', 'c', 'd'], original=np.ones(4, dtype=bool), protected_X=X, protected_y=y)
    return X, y, model


def test_portable_tree_is_self_contained_and_round_trips_json():
    X, y, model = fitted()
    artifact = json.loads(json.dumps(model.artifact({'progress': 'Progress observed', 'complete': 'Completion observed'})))
    assert model.retained
    assert [execute(artifact, dict(zip(model.names, map(bool, row)))) for row in X] == y.tolist()
    assert set(artifact['feature_names']) <= {'progress', 'complete'}
    assert 'teacher' not in json.dumps(artifact)


def test_insufficient_capacity_is_not_repaired_with_protected_lookup():
    X, y, model = fitted(leaves=2)
    assert not model.retained
    assert len(model.attempts) == len(ANCHOR_WEIGHTS)
    assert np.sum(np.asarray(model.predict(X)) == y) < len(y)
    assert model.metadata()['leaves'] <= 2


def test_equal_class_mass_survives_anchor_weighting():
    X, y, model = fitted(leaves=2)
    for attempt in model.attempts:
        assert np.allclose(attempt['class_weight_mass'], [1/3]*3)


def test_missing_evidence_and_modified_rules_are_rejected():
    _, _, model = fitted()
    artifact = model.artifact({'progress': 'Progress', 'complete': 'Complete'})
    with pytest.raises(ValueError, match='Boolean'):
        execute(artifact, {})
    artifact['tree']['feature'] = 'case_lookup'
    with pytest.raises(ValueError, match='Changed'):
        execute(artifact, {'case_lookup': True})


def test_conflicting_identical_inputs_cannot_claim_perfect_local_retention():
    X = np.asarray([[0], [0], [1]])
    y = np.asarray([0, 1, 2])
    model = SingleTree(['progress'], leaves=128).fit(X, y, groups=['a', 'b', 'c'], protected_X=X, protected_y=y)
    assert not model.retained
    assert model.metadata()['leaves'] == 2
