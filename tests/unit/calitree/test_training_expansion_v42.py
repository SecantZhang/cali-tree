from pathlib import Path

import numpy as np
import pytest

from run import calitree_training_expansion_v42 as expansion
from run.calitree_expert_region_policy_v40 import regions, region_features
from run.calitree_goal_progress_policy_v41 import ProgressPolicy
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record


def test_training_expansion_requires_its_own_authorization_before_any_state_or_model_access(tmp_path):
    with pytest.raises(ValueError, match='authorization'):
        expansion.collect(tmp_path / 'nonexistent', live=True)
    assert list(tmp_path.iterdir()) == []
    assert expansion.MAX_CALLS == 544
    assert expansion.MAX_OUTPUT == 4784128


def test_region_features_are_explicit_semantic_paths_and_ignore_identifiers():
    class Expert:
        artifact = {'tree': {'feature': 'meaning_progress_none_all',
                             'true': {'prediction': 0}, 'false': {'prediction': 2}}}
    definitions = regions({'model-ref': Expert()})
    record = synthetic_record(meaning_available=True, meaning_progress_none_all=True)
    examples = [{'features': record, 'case': 'a', 'reference': 0},
                {'features': record, 'case': 'b', 'reference': 2}, {'features': None}]
    matrix = region_features(examples, definitions)
    assert np.array_equal(matrix[0], matrix[1])
    assert matrix[0].sum() == 1 and matrix[2].sum() == 0
    assert all(len(d['conditions']) == 1 for d in definitions.values())


def test_progress_completion_probabilities_form_a_coherent_three_class_distribution():
    class Head:
        def __init__(self, positive):
            self.positive = positive
        def predict_proba(self, X):
            p = np.asarray(self.positive)
            return np.stack((1 - p, p), axis=1)
    policy = ProgressPolicy(True)
    policy.intent = Head([0, 1, 1, .6])
    policy.completion = Head([1, 0, 1, .5])
    probabilities = policy.predict_proba(np.zeros((4, 1)))
    assert np.allclose(probabilities.sum(axis=1), 1)
    assert np.all(probabilities >= 0)
    assert policy.predict(np.zeros((4, 1)))[:3] == [0, 1, 2]
