"""Semantic boundary experts for progress, completion and clear success/failure."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from .base import Calibrator

PAIRS = ((0, 1), (1, 2), (0, 2))


class BoundaryExperts(Calibrator):
    version = 'semantic-boundary-experts-v55'

    def __init__(self, *, balanced=False, max_features='sqrt', multiclass=False):
        self.balanced, self.max_features, self.multiclass = balanced, max_features, multiclass
        self.classes_ = np.asarray([0, 1, 2])

    def forest(self):
        return RandomForestClassifier(n_estimators=128, bootstrap=False, min_samples_leaf=1,
                                      max_features=self.max_features, class_weight='balanced' if self.balanced else None,
                                      random_state=20261020, n_jobs=2)

    def fit(self, X, y, *, sample_weight=None):
        X, y = np.asarray(X), np.asarray(y)
        if self.multiclass:
            self.model = self.forest().fit(X, y, sample_weight=sample_weight)
        else:
            self.heads = {}
            for a, b in PAIRS:
                selected = (y == a) | (y == b)
                weight = np.asarray(sample_weight)[selected] if sample_weight is not None else None
                self.heads[(a, b)] = self.forest().fit(X[selected], y[selected] == b, sample_weight=weight)
        return self

    def pair_evidence(self, X):
        if self.multiclass:
            return None
        return {pair: model.predict_proba(X)[:, 1] for pair, model in self.heads.items()}

    def predict_proba(self, X, aggregation='sum'):
        if self.multiclass:
            return self.model.predict_proba(X)
        evidence = self.pair_evidence(X)
        scores = np.ones((len(X), 3)) if aggregation in ('product', 'minimum') else np.zeros((len(X), 3))
        for (a, b), p in evidence.items():
            for label, support in ((a, 1 - p), (b, p)):
                if aggregation == 'product':
                    scores[:, label] *= support
                elif aggregation == 'minimum':
                    scores[:, label] = np.minimum(scores[:, label], support)
                elif aggregation == 'sum':
                    scores[:, label] += support
                else:
                    raise ValueError('Undeclared boundary aggregation')
        totals = scores.sum(axis=1, keepdims=True)
        return np.divide(scores, totals, out=np.full_like(scores, 1 / 3), where=totals > 0)

    def proposals(self, X):
        """A new label needs strict positive support from both relevant experts."""
        if self.multiclass:
            return [[] for _ in X]
        wins = np.ones((len(X), 3), dtype=bool)
        for (a, b), p in self.pair_evidence(X).items():
            wins[:, a] &= p < .5
            wins[:, b] &= p > .5
        return [[int(v) for v in np.flatnonzero(row)] for row in wins]

    def predict(self, X):
        return [int(v) for v in np.argmax(self.predict_proba(X), axis=1)]
