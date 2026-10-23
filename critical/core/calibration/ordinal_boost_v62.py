"""Compact symmetric-tree objectives for grades and within-task relative quality."""
import numpy as np

from .base import Calibrator

VERSION = 'semantic-ordinal-relative-boost-v62'


def ordered_probabilities(progress, completion):
    p, q = np.asarray(progress, dtype=float).copy(), np.asarray(completion, dtype=float).copy()
    inverted = q > p
    middle = (p[inverted] + q[inverted]) / 2
    p[inverted] = q[inverted] = middle
    return np.stack([1 - p, p - q, q], axis=1)


def mean_support(values):
    values = np.clip(np.asarray(values, dtype=float), 0, 2)
    # Equal-distance half-point ties follow the unchanged upper-bin convention.
    scores = -(values[:, None] - np.asarray([0., 1., 2.])) ** 2 / .5 + np.asarray([0., 1e-12, 2e-12])
    scores -= scores.max(axis=1, keepdims=True)
    support = np.exp(scores)
    return support / support.sum(axis=1, keepdims=True)


def centered_targets(means, tasks):
    means, tasks = np.asarray(means, dtype=float), np.asarray(tasks)
    relative = means.copy()
    for task in set(tasks):
        selected = tasks == task
        relative[selected] -= means[selected].mean()
    return np.stack([means, relative], axis=1)


class OrdinalBoost(Calibrator):
    version = VERSION

    def __init__(self, *, family='multiclass', depth=6, iterations=1200):
        if family not in ('multiclass', 'ordinal', 'relative_mean'):
            raise ValueError('Unknown semantic boosting objective')
        self.family, self.depth, self.iterations = family, depth, iterations
        self.classes_ = np.asarray([0, 1, 2])

    def fit(self, X, y, *, original, means=None, tasks=None, sample_weight=None):
        from catboost import CatBoostClassifier, CatBoostRegressor
        if sample_weight is not None:
            raise ValueError('Protected weights selected by local retention only')
        X, y, original = np.asarray(X), np.asarray(y), np.asarray(original, dtype=bool)
        if not np.all((X == 0) | (X == 1)):
            raise ValueError('Closed Boolean semantic inputs required')
        params = dict(iterations=self.iterations, depth=self.depth, learning_rate=.05, l2_leaf_reg=3.,
                      random_seed=20261021, thread_count=2, verbose=False, allow_writing_files=False,
                      bootstrap_type='No', random_strength=0.)
        self.weight_trials = []
        for weight in (1., 5., 25.):
            weights = np.where(original, weight, 1.)
            if self.family == 'multiclass':
                self.model = CatBoostClassifier(loss_function='MultiClass', **params)
                self.model.fit(X, y, sample_weight=weights)
            elif self.family == 'ordinal':
                self.models = []
                for boundary in (0, 1):
                    model = CatBoostClassifier(loss_function='Logloss', **params)
                    model.fit(X, y > boundary, sample_weight=weights)
                    self.models.append(model)
            else:
                if means is None or tasks is None:
                    raise ValueError('Released means and fitting task groups required')
                self.model = CatBoostRegressor(loss_function='MultiRMSE', **params)
                self.model.fit(X, centered_targets(means, tasks), sample_weight=weights)
            correct = int(np.sum(np.argmax(self.predict_proba(X[original]), axis=1) == y[original]))
            self.weight_trials.append({'weight': weight, 'original_correct': correct})
            self.original_weight, self.original_correct = weight, correct
            if correct == int(original.sum()):
                break
        return self

    def predict_proba(self, X):
        X = np.asarray(X)
        if self.family == 'multiclass':
            return self.model.predict_proba(X)
        if self.family == 'ordinal':
            p, q = [model.predict_proba(X)[:, 1] for model in self.models]
            return ordered_probabilities(p, q)
        return mean_support(self.model.predict(X)[:, 0])

    def predict(self, X):
        return [int(value) for value in np.argmax(self.predict_proba(X), axis=1)]
