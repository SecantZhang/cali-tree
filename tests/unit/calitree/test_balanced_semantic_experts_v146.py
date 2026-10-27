import numpy as np
import pytest

from critical.core.calibration.balanced_semantic_experts_v146 import (
    BalancedSemanticExperts, expert_flags, execute)

NAMES = ['expert_partial_review_ready', 'rubric_uncertainty_any', 'view_regular_partial']


def test_expert_region_requires_disagreement_an_available_judge_and_review_reason():
    assert expert_flags({'rubric_uncertainty_any': True}, 0, 1)['expert_partial_review_ready']
    assert not any(expert_flags({'rubric_uncertainty_any': True}, 1, 1).values())
    assert not any(expert_flags({'rubric_uncertainty_any': True}, 0, -1).values())
    assert not any(expert_flags({}, 0, 1).values())


def test_review_rule_selects_existing_partial_without_asserting_a_physical_warrant():
    X = [[1, 1, 1], [1, 1, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0]]
    model = BalancedSemanticExperts(NAMES, style='partial_review').fit(X, [1, 1, 0, 0, 2],
        [0, 0, 0, 0, 2], np.ones(5, dtype=bool), list('abcde'),
        protected_X=[[0, 1, 0]], protected_y=[0], protected_base=[0], protected_eligible=[True])
    assert len(model.rules) == 1 and model.rules[0]['role'] == 'regular'
    artifact = model.artifact(); values = dict(zip(NAMES, [True, True, True]))
    assert execute(artifact, values, 0, True, 1) == 1
    assert execute(artifact, values, 2, True, 1) == 2
    with pytest.raises(ValueError, match='differs'):
        execute(artifact, values, 0, True, 0)
