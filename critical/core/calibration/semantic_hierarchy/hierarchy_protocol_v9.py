"""Sealed M3--M7 search and replacement gates, separate from inference."""
from fractions import Fraction

from ...decision.artifacts import digest
from .portable_tree_v8 import LIMITS as M2_LIMITS, metrics

VERSION = 'portable-semantic-hierarchy-v9.2'
PROFILES = {
    'local_shallow': {**M2_LIMITS, 'max_depth': 3},
    'local_deeper': {**M2_LIMITS, 'max_depth': 4},
    'pooled': {**M2_LIMITS, 'max_depth': 5},
}
ROUTING = {'max_routes': 8, 'min_fit_sources': 2, 'min_validation_sources': 8,
           'min_validation_per_class': 2, 'min_validation_batches': 2,
           'max_scope_tests': 2, 'unresolved': 'pooled_fallback',
           'whole_system_guard': 'Select among at most 256 ordered route subsets on fitting data; no loss of pooled accuracy, macro-F1, any class recall, or coverage. Evaluate the complete selector out of source.'}
SEARCH = {'max_hierarchy_depth': 3, 'active_candidates_per_initial_batch': 2,
          'max_parent_proposals': 24, 'pair_shortlist_per_round': 6}
MERGE_GATES = {'min_validation_sources_per_label': 8, 'min_validation_sources_per_scope': 8,
    'macro_f1_min_delta': 0, 'max_additional_errors_total': 1, 'partial_recall_min_delta': 0,
    'max_additional_errors_other_class_or_scope': 1, 'coverage_min_delta': 0,
    'require_gain_or_lossless_complexity_reduction': True}


def macro_fraction(metric):
    return sum((Fraction(2 * c['correct'], c['support'] + c['predicted'])
                if c['support'] + c['predicted'] else Fraction(0))
               for c in metric['per_class'].values()) / 3


def score(rows, decisions):
    predictions = [d['prediction'] if isinstance(d, dict) else d for d in decisions]
    m = metrics(predictions, [r['reference'] for r in rows])
    m['coverage'] = (m['total'] - m['unresolved']) / m['total']
    m['confusion'] = {str(y): {str(p): sum(a == y and b == p for a, b in zip(
        [r['reference'] for r in rows], predictions)) for p in (-1, 0, 1, 2)} for y in range(3)}
    m['error_cases'] = [r['case'] for r, p in zip(rows, predictions) if r['reference'] != p]
    return m


def content_ref(value, key):
    return digest({k: v for k, v in value.items() if k != key})


def sealed(value, key):
    return {**value, key: digest(value)}

