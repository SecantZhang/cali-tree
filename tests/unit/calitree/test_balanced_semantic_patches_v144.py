import numpy as np

from critical.core.calibration.balanced_semantic_patches_v144 import BalancedSemanticPatches, execute

NAMES = ['rubric_partial_ready', 'view_regular_partial']


def data():
    return (np.asarray([[1, 1], [1, 1], [0, 0], [0, 0], [0, 0]]),
            np.asarray([1, 1, 0, 0, 2]), np.asarray([0, 0, 0, 0, 2]))


def fitted(*, groups=None, protected=(1, 0)):
    X, y, base = data()
    model = BalancedSemanticPatches(NAMES).fit(X, y, base, np.ones(5, dtype=bool),
        groups or ['a', 'b', 'c', 'd', 'e'], protected_X=[protected], protected_y=[0],
        protected_base=[0], protected_eligible=np.ones(1, dtype=bool))
    return model


def test_semantic_anchor_and_guard_recover_partial_without_changing_original():
    model = fitted(); X, y, base = data()
    assert model.predict(X, base, np.ones(5, dtype=bool)).tolist() == y.tolist()
    assert len(model.rules) == 1
    assert {'feature': 'rubric_partial_ready', 'value': True} in model.rules[0]['conditions']
    assert model.predict([[1, 0]], [0], [True]).tolist() == [0]
    artifact = model.artifact()
    for row, grade in zip(X, base):
        values = dict(zip(NAMES, map(bool, row)))
        assert execute(artifact, values, int(grade), True) == model.predict([row], [grade], [True])[0]


def test_one_positive_source_or_indistinguishable_original_blocks_a_rule():
    assert not fitted(groups=['a', 'a', 'c', 'd', 'e']).rules
    assert not fitted(protected=(1, 1)).rules


def test_no_to_partial_only_policy_preserves_other_grades_and_missing_warrants():
    model = fitted()
    result = model.predict([[1, 1], [1, 1], [0, 1], [1, 1]], [1, 2, 0, 0], [True, True, True, False])
    assert result.tolist() == [1, 2, 0, 0]
