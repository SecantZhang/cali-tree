from types import SimpleNamespace

import numpy as np

from critical.core.calibration import conditional_rubric_v149 as core


def test_conditional_completion_preserves_probability_mass_and_does_not_override_no_progress():
    q = core.probabilities([.2, .8], [.9, .25])
    assert np.allclose(q.sum(axis=1), 1.)
    assert np.allclose(q[0], [.8, .02, .18])
    assert np.allclose(q[1], [.2, .6, .2])


def test_no_cases_do_not_enter_conditional_completion_training(monkeypatch):
    calls = []
    class Model:
        def __init__(self, **kwargs):
            pass
        def fit(self, X, y, **kwargs):
            calls.append(np.asarray(y).tolist())
            return self
    monkeypatch.setattr(core, 'LogisticRegression', Model)
    X = [[0, 0], [0, 1], [1, 0], [1, 1], [0, 0], [1, 0]]
    core.ConditionalRubric().fit(X, [0, 0, 1, 1, 2, 2], np.zeros(6, dtype=bool))
    assert calls == [[False, False, True, True, True, True], [False, False, True, True]]


def test_shared_terms_carry_both_gate_weights_and_execute_exactly():
    model = core.ConditionalRubric(); model.setting = [.5, .5, 0.]
    model.models = [SimpleNamespace(coef_=np.asarray([[1., 2.]]), intercept_=np.asarray([.1])),
                    SimpleNamespace(coef_=np.asarray([[3.]]), intercept_=np.asarray([.2]))]
    model.columns = [[0, 1], [0]]
    terms = [[{'feature': 'goal_fragment', 'border': .5, 'greater': True}],
             [{'feature': 'full_extent', 'border': .5, 'greater': True}]]
    a = model.artifact(terms, {'goal_fragment': 'Some requested content is realized.', 'full_extent': 'The intended extent is covered.'}, 'parent')
    assert len(a['terms']) == 2
    assert a['terms'][0]['progress_completion_weights'] == [1., 3.]
    assert core.evaluate(a, {'goal_fragment': True, 'full_extent': False}, 0, False) == 2
    assert core.evaluate(a, {}, 0, True) == 0
