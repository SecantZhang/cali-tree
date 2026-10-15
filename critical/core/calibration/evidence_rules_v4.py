"""Class-balanced objective for the unchanged reusable evidence-rule grammar."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction

import numpy as np

from .evidence_rules_v3 import (
    EvidenceRuleCalibrator, DOMAIN_ARRAY, DOMAIN_INDEX, FEATURES, LABELS, LIMITS,
    PREDICATES, evidence_bounds, trees, shape, definite_support, vector,
    monotone_values, monotone, node_count, validate_tree,
)
from ..decision.artifacts import digest

VERSION = 'three-label-evidence-rules-v4-macro-f1'
OBJECTIVE = {
    'primary': 'macro_f1',
    'min_correct_source_cases_per_class': 2,
    'tie_breaks': ['worst_class_recall', 'correct_cases', 'fewer_splits',
                   'fewer_reference_policy_departures', 'fixed_enumeration_order'],
    'unresolved': 'Count as false negatives for the reference class; never drop from denominator.',
}


def classification_metrics(predictions, targets):
    """Exact fractions prevent floating-point noise in objective tie-breaks."""
    p, y = list(predictions), list(targets)
    if (len(p) != len(y) or not y or any(type(v) is not int or v not in range(3) for v in y)
            or any(v not in (-1, 0, 1, 2) for v in p)):
        raise ValueError('Matched ordinal labels/predictions required; -1 means unresolved')
    supports = [y.count(label) for label in range(3)]
    if any(n == 0 for n in supports): raise ValueError('All three reference classes required')
    tp = [sum(a == b == label for a, b in zip(p, y)) for label in range(3)]
    predicted = [p.count(label) for label in range(3)]
    recalls = [Fraction(t, n) for t, n in zip(tp, supports)]
    f1 = [Fraction(2*t, n+k) for t, n, k in zip(tp, supports, predicted)]
    exact_macro = sum(f1, Fraction())/3
    exact_worst = min(recalls)
    result = {'correct': sum(tp), 'total': len(y), 'accuracy': sum(tp)/len(y),
              'macro_f1': float(exact_macro), 'worst_class_recall': float(exact_worst),
              'per_class': {label: {'support': n, 'predicted': k, 'correct': t,
                                     'recall': float(r), 'f1': float(f)}
                            for label, n, k, t, r, f in zip(LABELS, supports, predicted, tp, recalls, f1)},
              'unresolved': p.count(-1)}
    return result, exact_macro, exact_worst


def objective_rank(predictions, targets, *, splits=0, departures=0):
    metrics, macro, worst = classification_metrics(predictions, targets)
    if any(v['correct'] < OBJECTIVE['min_correct_source_cases_per_class'] for v in metrics['per_class'].values()):
        return None, metrics
    return (macro, worst, metrics['correct'], -splits, -departures), metrics


class ClassBalancedEvidenceRuleCalibrator(EvidenceRuleCalibrator):
    """V3 semantics and capacity; explicit protection against class collapse."""
    version = VERSION

    def fit(self, X, y, *, sample_weight=None, source_groups=None):
        X, y = list(X), list(y)
        if (sample_weight is not None or not X or len(X) != len(y) or source_groups is None
                or len(source_groups) != len(X) or len(set(source_groups)) != len(X)
                or any(type(v) is not int or v not in range(3) for v in y)
                or any(y.count(label) < OBJECTIVE['min_correct_source_cases_per_class'] for label in range(3))):
            raise ValueError('Distinct source groups and at least two training cases per class required')
        bounds = [evidence_bounds(x) for x in X]
        lo_idx = np.asarray([DOMAIN_INDEX[tuple(b['lower'][k] for k in FEATURES)] for b in bounds])
        hi_idx = np.asarray([DOMAIN_INDEX[tuple(b['upper'][k] for k in FEATURES)] for b in bounds])
        reference = np.where((DOMAIN_ARRAY[:, 0] == 0) | (DOMAIN_ARRAY[:, 1] == 0) | (DOMAIN_ARRAY[:, 3] == 0), 0,
                             np.where(np.all(DOMAIN_ARRAY[:, 1:] == 2, axis=1), 2, 1))
        counts = Counter(); cache = {}; best = best_rank = best_metrics = None
        best_unconstrained_f1 = None
        for tree in trees():
            counts['enumerated'] += 1
            key = shape(tree)
            if key not in cache: cache[key] = definite_support(tree, bounds, source_groups)
            if min(cache[key].values()) < LIMITS['min_leaf_sources']: continue
            counts['supported'] += 1
            values = vector(tree)
            if not monotone_values(values): continue
            counts['supported_monotone'] += 1
            low, high = values[lo_idx], values[hi_idx]
            p = np.where(low == high, low, -1).tolist()
            rank, metrics = objective_rank(p, y, splits=node_count(tree),
                                          departures=int(np.count_nonzero(values != reference)))
            if best_unconstrained_f1 is None or metrics['macro_f1'] > best_unconstrained_f1:
                best_unconstrained_f1 = metrics['macro_f1']
            if rank is None: continue
            counts['class_supported'] += 1
            if best_rank is None or rank > best_rank:
                best, best_rank, best_metrics = deepcopy(tree), rank, metrics
        if best is None:
            raise ValueError('No supported monotone policy recognizes at least two sources per class; refusing a collapsed fallback')
        self._artifact = {'version': VERSION, 'tree': best, 'predicates': deepcopy(PREDICATES),
                          'feature_names': list(FEATURES), 'limits': deepcopy(LIMITS), 'objective': deepcopy(OBJECTIVE),
                          'leaf_support': definite_support(best, bounds, source_groups), 'search_counts': dict(counts),
                          'training_rows': len(X), 'training_correct': best_metrics['correct'],
                          'training_metrics': best_metrics,
                          'best_supported_macro_f1_without_floor': best_unconstrained_f1,
                          'training_feature_ref': digest(bounds), 'training_target_ref': digest(y),
                          'uncertainty': 'Resolve only when monotone lower/upper evidence completions agree.',
                          'scope': 'Macro-F1 local fitting on the same cases; no generalization or repeat-robustness claim.'}
        return self

    def predict_records(self, X):
        return [{**r, 'version': VERSION} for r in super().predict_records(X)]

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact else {'version': VERSION, 'objective': deepcopy(OBJECTIVE)}

    @classmethod
    def restore(cls, artifact):
        if (artifact.get('version') != VERSION or artifact.get('predicates') != PREDICATES
                or artifact.get('feature_names') != list(FEATURES) or artifact.get('limits') != LIMITS
                or artifact.get('objective') != OBJECTIVE):
            raise ValueError('Changed v4 objective or reusable rule contract')
        validate_tree(artifact['tree'])
        if (node_count(artifact['tree']) > LIMITS['max_split_nodes'] or not monotone(artifact['tree'])
                or not artifact.get('leaf_support') or any(type(n) is not int or n < 2 for n in artifact['leaf_support'].values())
                or any(artifact['training_metrics']['per_class'][label]['correct'] < 2 for label in LABELS)):
            raise ValueError('Unsupported, nonmonotone or class-collapsed policy')
        result = cls(); result._artifact = deepcopy(artifact); return result
