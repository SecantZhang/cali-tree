"""Two-parameter calibration selected for final balanced accuracy.

The ordinal index is a statistical human-grade score, not physical edit
progress. The warranted arm needs affirmative same-requirement evidence for
every changed grade. Previously selected semantic/expert decisions keep priority.
"""
import itertools

import numpy as np

from .rubric_score_v82 import log_support
from .rubric_evidence_v73 import CONTRACT_REF
from ..decision.artifacts import digest

BIAS_GRID = tuple(float(x)/4 for x in range(-8, 17))
ORDINAL_GRID = tuple(float(x)/20 for x in range(41))


def predict(support, base, locked, warrants, *, family, parameters, warranted):
    p = np.asarray(support, dtype=float); log_support(p)
    base, locked, w = np.asarray(base), np.asarray(locked), np.asarray(warrants)
    if (base.shape != (len(p),) or locked.shape != base.shape or locked.dtype != bool or
            w.shape != p.shape or w.dtype != bool or not np.all(np.isin(base, (-1, 0, 1, 2)))):
        raise ValueError('Aligned grades, protected routes and Boolean warrants required')
    if family == 'identity':
        return base.copy()
    values = np.asarray(parameters, dtype=float)
    if values.shape != (2,) or not np.all(np.isfinite(values)) or type(warranted) is not bool:
        raise ValueError('Two finite calibration parameters required')
    if family == 'bias':
        proposed = np.argmax(log_support(p)+[0., *values], axis=1)
    elif family == 'ordinal' and 0 <= values[0] < values[1] <= 2:
        index = p[:, 1]+2*p[:, 2]
        proposed = (index >= values[0]).astype(int)+(index >= values[1]).astype(int)
    else:
        raise ValueError('Known compact calibration family required')
    allowed = ~locked
    if warranted:
        allowed &= (proposed == base) | w[np.arange(len(p)), proposed]
    return np.where(allowed, proposed, base)


def recalls(y, prediction):
    y, prediction = np.asarray(y), np.asarray(prediction)
    return [float(np.mean(prediction[y == k] == k)) for k in range(3)]


class CompactBalance:
    def __init__(self, *, family='bias', warranted=True, pareto=False):
        if family not in ('bias', 'ordinal') or type(warranted) is not bool or type(pareto) is not bool:
            raise ValueError('Known family and Boolean guard/objective required')
        self.family, self.warranted, self.pareto = family, warranted, pareto

    def fit(self, support, y, base, locked, warrants, *, protected_support,
            protected_y, protected_base, protected_locked, protected_warrants):
        y, py = np.asarray(y), np.asarray(protected_y)
        if (len(y) != len(support) or set(np.unique(y)) != {0, 1, 2} or
                len(py) != len(protected_support) or not np.all(np.isin(py, (0, 1, 2)))):
            raise ValueError('All three fitting grades and aligned original protection required')
        baseline = recalls(y, base)
        params = itertools.product(BIAS_GRID, repeat=2) if self.family == 'bias' else (
            (low, high) for low in ORDINAL_GRID for high in ORDINAL_GRID if low < high)
        self.trials = []
        for family, pair in [('identity', ())]+[(self.family, pair) for pair in params]:
            p = predict(support, base, locked, warrants, family=family, parameters=pair, warranted=self.warranted)
            protected = predict(protected_support, protected_base, protected_locked, protected_warrants,
                                family=family, parameters=pair, warranted=self.warranted)
            r = recalls(y, p)
            norm = 0. if family == 'identity' else float(np.sum((np.asarray(pair)-(
                np.asarray([.5, 1.5]) if family == 'ordinal' else 0.))**2))
            self.trials.append({'family': family, 'parameters': list(pair),
                'retained': bool(np.all(protected == py)), 'class_recalls': r,
                'balanced_accuracy': float(np.mean(r)), 'worst_class_recall': min(r),
                'accuracy': float(np.mean(p == y)), 'norm': norm,
                'per_class_nonregression': all(a+1e-12 >= b for a, b in zip(r, baseline))})
        passing = [t for t in self.trials if t['retained'] and (not self.pareto or t['per_class_nonregression'])]
        if not passing:
            raise ValueError('Even unchanged original decisions fail protection')
        self.selected = min(passing, key=lambda t: (-t['balanced_accuracy'], -t['worst_class_recall'],
            -t['accuracy'], t['norm'], t['family'] != 'identity', t['parameters']))
        return self

    def predict(self, support, base, locked, warrants):
        return predict(support, base, locked, warrants, family=self.selected['family'],
                       parameters=self.selected['parameters'], warranted=self.warranted)

    def artifact(self):
        value = {'version': 'compact-balanced-boundary-v143', 'family': self.family,
            'warranted': self.warranted, 'pareto_fitting_recalls': self.pareto,
            'selected': self.selected, 'trials': self.trials,
            'warrant_contract_ref': CONTRACT_REF,
            'priority': 'Existing semantic and independent-expert overrides keep their original decisions. Missing coverage keeps regular fallback.',
            'equation': 'bias: argmax(log(teacher support)+[0,partial_bias,yes_bias]); ordinal: two cutoffs on support_partial+2*support_yes. Identity keeps current grade. No/Partial/Yes order breaks ties.',
            'limit': 'Human-grade calibration; the ordinal index is not a physical progress certificate.'}
        value['artifact_ref'] = digest(value)
        return value
