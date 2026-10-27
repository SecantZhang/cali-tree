"""Calibration controls that distinguish held-source views from fitting views.

The score adjustment is an explicit class-boundary control, not a new visual
judge or calibrated correctness probability. Optional grading warrants can
veto a changed grade, but cannot create a grade from uncertainty.
"""
import itertools

import numpy as np
from scipy.special import logsumexp

from .rubric_score_v82 import log_support

GRID = (-1., -.5, 0., .5, 1., 1.5, 2.)


def source_excluded_views(support, train, held, groups, inner_views):
    """Return mixed views and a mask marking only genuinely excluded sources."""
    result = np.asarray(support, dtype=float).copy()
    log_support(result)
    groups = np.asarray(groups)
    train, held = list(train), list(held)
    if len(result) != len(groups) or len(set(train)) != len(train):
        raise ValueError('Aligned distinct fitting rows required')
    if set(groups[train]) & set(groups[held]):
        raise ValueError('Outer source leakage')
    excluded_mask = np.zeros(len(result), dtype=bool)
    for membership, probabilities in inner_views:
        excluded = set(membership['held_sources'])
        expected = [i for i in train if groups[i] not in excluded]
        if membership['train'] != expected or set(membership['training_sources']) != set(groups[expected]):
            raise ValueError('Inner membership differs from teacher fitting rows')
        if set(groups[expected]) & (excluded | set(groups[held])):
            raise ValueError('Inner source leakage')
        indices = [i for i in train if groups[i] in excluded]
        if not indices or excluded_mask[indices].any():
            raise ValueError('Empty or repeated inner held-source partition')
        p = np.asarray(probabilities, dtype=float)
        log_support(p)
        if p.shape != result.shape:
            raise ValueError('Aligned inner teacher support required')
        result[indices] = p[indices]
        excluded_mask[indices] = True
    return result, excluded_mask


class BoundaryCalibration:
    version = 'source-excluded-class-boundary-control-v89'

    @staticmethod
    def _predict(scores, bias, warrants):
        predicted = np.argmax(scores + bias, axis=1)
        original = np.argmax(scores, axis=1)
        if warrants is not None:
            w = np.asarray(warrants)
            if w.shape != scores.shape or w.dtype != bool:
                raise ValueError('Aligned Boolean grading warrants required')
            veto = ~w[np.arange(len(w)), predicted]
            predicted[veto] = original[veto]
        return predicted

    def fit(self, support, y, groups, *, protected_support, protected_y,
            warrants=None, protected_warrants=None):
        scores, protected = log_support(support), log_support(protected_support)
        y, py = np.asarray(y, dtype=int), np.asarray(protected_y, dtype=int)
        if len(scores) != len(y) or len(groups) != len(y) or not len(y) or len(protected) != len(py):
            raise ValueError('Aligned calibration and protected rows required')
        if not np.all(np.isin(y, (0, 1, 2))) or not np.all(np.isin(py, (0, 1, 2))):
            raise ValueError('Three-class grades required')
        unique, counts = np.unique(groups, return_counts=True)
        sizes = dict(zip(unique, counts))
        weights = np.asarray([1. / sizes[g] for g in groups]); weights /= weights.sum()
        self.trials = []
        for partial, yes in itertools.product(GRID, repeat=2):
            bias = np.asarray([0., partial, yes])
            pred = self._predict(scores, bias, warrants)
            protected_pred = self._predict(protected, bias, protected_warrants)
            logits = scores + bias
            self.trials.append({
                'bias': bias.tolist(), 'retained': bool(np.all(protected_pred == py)),
                'source_weighted_accuracy': float(weights @ (pred == y)),
                'negative_log_likelihood': float(weights @ (logsumexp(logits, axis=1) - logits[np.arange(len(y)), y])),
                'bias_norm': float(bias @ bias),
            })
        eligible = [r for r in self.trials if r['retained']]
        if not eligible:
            raise ValueError('No boundary adjustment retains every original')
        chosen = min(eligible, key=lambda r: (-r['source_weighted_accuracy'], r['bias_norm'], r['negative_log_likelihood'], r['bias']))
        self.bias = np.asarray(chosen['bias'])
        self.selected = chosen
        return self

    def predict(self, support, *, warrants=None):
        return self._predict(log_support(support), self.bias, warrants)

    def artifact(self):
        return {'version': self.version, 'grid': list(GRID), 'bias_no_partial_yes': self.bias.tolist(),
                'selection': self.selected, 'trials': self.trials,
                'equation': 'argmax(log(teacher support) + class bias); optional affirmative grade warrant vetoes any changed grade.',
                'limits': 'Class-boundary calibration control, not a standalone semantic policy or probability of correctness.'}
