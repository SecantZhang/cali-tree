"""Reconstruct a rubric as progress and conditional-completion gates.

The gates predict human ordinal judgments, not certified physical states.
Exact conjunctions shared by both gates have one predicate and two weights.
"""
import itertools

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

from .semantic_residual_runtime_v104 import f32
from ..decision.artifacts import digest

THRESHOLDS = (.2, .35, .5, .65, .8)
MASS_FLOORS = (0., .35, .5, .65, .8, .9)


def probabilities(progress, completion):
    p, c = np.asarray(progress, dtype=float), np.asarray(completion, dtype=float)
    if p.shape != c.shape or not np.isfinite(p).all() or not np.isfinite(c).all() or np.any((p < 0)|(p > 1)|(c < 0)|(c > 1)):
        raise ValueError('Aligned bounded progress and conditional completion scores required')
    return np.stack([1-p, p*(1-c), p*c], axis=-1)


def readout(p, c, base, locked, setting):
    base, locked = np.asarray(base), np.asarray(locked)
    if setting is None:
        return base.copy()
    low, high, minimum = setting
    grade = np.where(p < low, 0, np.where(c >= high, 2, 1))
    q = probabilities(p, c)
    use = ~locked & (q[np.arange(len(q)), grade] >= minimum)
    return np.where(use, grade, base)


class ConditionalRubric:
    def __init__(self, *, C=1., max_terms=32):
        if C not in (.1, 1., 10.) or max_terms not in (32, 96):
            raise ValueError('Frozen small sparse-gate configuration required')
        self.C, self.max_terms = C, max_terms

    def fit(self, X, y, original):
        a, y, original = np.asarray(X, dtype=float), np.asarray(y), np.asarray(original)
        if (a.ndim != 2 or len(a) != len(y) or original.shape != y.shape or original.dtype != bool or
                set(np.unique(y)) != {0, 1, 2} or not np.all((a == 0)|(a == 1))):
            raise ValueError('Boolean named terms, three grades and original anchor mask required')
        weights = np.where(original, 5., 1.)
        for grade in range(3):
            weights[y == grade] /= weights[y == grade].sum()
        self.models = []; self.columns = []
        for complete in (False, True):
            chosen = y > 0 if complete else np.ones(len(y), dtype=bool)
            target = (y[chosen] == 2) if complete else (y[chosen] > 0)
            w = weights[chosen].copy(); w /= w.sum()
            z = a[chosen]
            # Rank direct concepts and exact shared conjunctions using fit data.
            residual = target.astype(float)-float(w @ target)
            ranking = np.abs(z.T @ (w*residual))
            cols = sorted((i for i in range(a.shape[1]) if np.std(z[:, i]) > 0),
                          key=lambda i: (-float(ranking[i]), i))[:self.max_terms]
            if not cols:
                raise ValueError('At least one varying semantic term is needed')
            model = LogisticRegression(C=self.C, penalty='l1', solver='liblinear',
                max_iter=2000, random_state=20261025, tol=1e-8)
            model.fit(z[:, cols], target, sample_weight=w*len(w))
            self.models.append(model); self.columns.append(cols)
        return self

    def scores(self, X):
        a = np.asarray(X, dtype=float)
        return [m.predict_proba(a[:, cols])[:, 1] for m, cols in zip(self.models, self.columns)]

    def select(self, fitting_X, y, base, locked, protected_X, protected_y, protected_base, protected_locked):
        p, c = self.scores(fitting_X); pp, pc = self.scores(protected_X)
        y, py = np.asarray(y), np.asarray(protected_y)
        self.trials = []
        for setting in [None, *itertools.product(THRESHOLDS, THRESHOLDS, MASS_FLOORS)]:
            predicted = readout(p, c, base, locked, setting)
            protected = readout(pp, pc, protected_base, protected_locked, setting)
            r = [float(np.mean(predicted[y == k] == k)) for k in range(3)]
            self.trials.append({'setting': list(setting) if setting is not None else None,
                'retained': bool(np.all(protected == py)), 'balanced_accuracy': float(np.mean(r)),
                'worst_class_recall': min(r), 'accuracy': float(np.mean(predicted == y)),
                'changed': int(np.sum(predicted != base))})
        passing = [r for r in self.trials if r['retained']]
        if not passing:
            raise ValueError('The original predictions fail the hard retention requirement')
        selected = min(passing, key=lambda r: (-r['balanced_accuracy'], -r['worst_class_recall'],
            -r['accuracy'], r['changed'], r['setting'] is not None, r['setting'] or []))
        self.setting = selected['setting']; self.selected = selected
        return self

    def predict(self, X, base, locked):
        p, c = self.scores(X)
        return readout(p, c, base, locked, self.setting)

    def artifact(self, terms, descriptions, parent_ref):
        coefficients = {}
        for gate, (model, columns) in enumerate(zip(self.models, self.columns)):
            for col, weight in zip(columns, model.coef_[0]):
                if weight:
                    coefficients.setdefault(col, [0., 0.])[gate] += float(weight)
        shared = [{'conditions': terms[i], 'progress_completion_weights': w} for i, w in sorted(coefficients.items())]
        names = sorted({c['feature'] for t in shared for c in t['conditions']})
        result = {'version': 'conditional-shared-semantic-rubric-v149', 'parent_ref': parent_ref,
            'C': self.C, 'max_terms_per_gate': self.max_terms, 'setting': self.setting,
            'bias': [float(m.intercept_[0]) for m in self.models], 'terms': shared,
            'features': names, 'feature_descriptions': {n: descriptions[n] for n in names},
            'gate_targets': ['human recognizes at least partial fulfillment', 'human full fulfillment conditional on at least partial fulfillment'],
            'equation': 'P=sigmoid(progress score); C=sigmoid(conditional completion score); class masses=[1-P,P*(1-C),P*C]. Use learned progress/completion thresholds and minimum selected-class mass; otherwise retain v112.',
            'limit': 'Learned human-grade gates over model evidence, not physical-state certificates.'}
        result['artifact_ref'] = digest(result)
        return result


def evaluate(artifact, values, base, locked):
    if locked or artifact['setting'] is None:
        return base
    scores = list(artifact['bias'])
    for term in artifact['terms']:
        matched = all((f32(float(values[c['feature']])) > f32(c['border'])) == c['greater'] for c in term['conditions'])
        if matched:
            for k, weight in enumerate(term['progress_completion_weights']):
                scores[k] += weight
    p, c = map(float, expit(scores)); low, high, minimum = artifact['setting']
    grade = 0 if p < low else (2 if c >= high else 1)
    mass = [1-p, p*(1-c), p*c][grade]
    return grade if mass >= minimum else base
