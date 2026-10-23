import numpy as np

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts


class Head:
    def __init__(self, p):
        self.p = p
    def predict_proba(self, X):
        return np.asarray([[1 - self.p, self.p]] * len(X))


def test_two_relevant_boundary_warrants_outweigh_unrelated_expert():
    model = BoundaryExperts()
    model.heads = {(0, 1): Head(.9), (1, 2): Head(.1), (0, 2): Head(.99)}
    X = np.zeros((2, 1))
    assert model.proposals(X) == [[1], [1]]
    for aggregation in ('sum', 'product', 'minimum'):
        probabilities = model.predict_proba(X, aggregation)
        assert np.allclose(probabilities.sum(axis=1), 1)
    assert list(np.argmax(model.predict_proba(X, 'minimum'), axis=1)) == [1, 1]


def test_ties_and_cycles_never_propose_a_new_label():
    model = BoundaryExperts()
    X = np.zeros((1, 1))
    model.heads = {(0, 1): Head(.5), (1, 2): Head(.5), (0, 2): Head(.5)}
    assert model.proposals(X) == [[]]
    model.heads = {(0, 1): Head(0), (1, 2): Head(0), (0, 2): Head(1)}
    assert model.proposals(X) == [[]]
    assert np.allclose(model.predict_proba(X, 'product'), [[1 / 3] * 3])
