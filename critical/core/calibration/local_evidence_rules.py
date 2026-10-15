"""Exact local fitting of a small, anonymous, monotone evidence-rule tree.

This deliberately does not use text features or exact condition counts. It is a
local fitting diagnostic, not a held-out calibration estimator.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import product
import math

from .base import Calibrator
from ..decision.artifacts import digest
from ..decision.single_call import apply_label_policy, validate_observation


VERSION = 'local-reusable-evidence-rules-v1'
LABELS = ('no', 'partial', 'yes')
STRENGTH = {'absent': 0, 'incomplete': 1, 'complete': 2}
PREDICATES = {
    'source_preserved': {'feature': 'source_integrity', 'minimum': 2},
    'every_core_has_progress': {'feature': 'core_minimum', 'minimum': 1},
    'every_core_complete': {'feature': 'core_minimum', 'minimum': 2},
    'every_constraint_has_progress': {'feature': 'constraint_minimum', 'minimum': 1},
    'every_constraint_complete': {'feature': 'constraint_minimum', 'minimum': 2},
}
FEATURES = ('source_integrity', 'core_minimum', 'constraint_minimum')
LIMITS = {'max_depth': 2, 'max_split_nodes': 3, 'min_leaf_sources': 2}
DOMAIN = [dict(zip(FEATURES, values)) for values in product((1, 2), (0, 1, 2), (0, 1, 2))]


def summarize(record):
    """Raw instruction is used only for provenance validation, never a predicate."""
    if not isinstance(record, dict) or set(record) != {'instruction', 'observations'}:
        raise ValueError('Only instruction and observations are accepted')
    obs = validate_observation(record['observations'], record['instruction'])
    original = apply_label_policy(obs, record['instruction'])
    guard = 'fixed_no' if original['label'] == 'no' else 'unresolved' if original['label'] is None else None
    if guard:
        return {'guard': guard, 'features': None}
    def minimum(role):
        return min((STRENGTH[r['state']] for r in obs['requirements'] if r['role'] == role), default=2)
    # The original policy can resolve some unknown requirement states. Retain
    # uncertainty rather than inventing a minimum for this different policy.
    if any(r['state'] == 'unknown' for r in obs['requirements']):
        return {'guard': 'unresolved', 'features': None}
    return {'guard': None, 'features': {
        'source_integrity': 2 if obs['source_integrity']['state'] == 'preserved' else 1,
        'core_minimum': minimum('core'), 'constraint_minimum': minimum('constraint'),
    }}


def decide(tree, features):
    while 'label' not in tree:
        predicate = PREDICATES[tree['predicate']]
        value = features[predicate['feature']] >= predicate['minimum']
        tree = tree['when_true'] if value else tree['when_false']
    return tree['label']


def split_nodes(tree):
    return 0 if 'label' in tree else 1 + split_nodes(tree['when_true']) + split_nodes(tree['when_false'])


def validate_tree(tree, *, depth=0, used=()):
    if not isinstance(tree, dict): raise ValueError('Rule nodes must be objects')
    if set(tree) == {'label'}:
        if tree['label'] not in ('partial', 'yes'): raise ValueError('Learned leaves are Partial or Yes only')
        return tree
    if (set(tree) != {'predicate', 'when_true', 'when_false'} or depth >= LIMITS['max_depth']
            or tree['predicate'] not in PREDICATES or tree['predicate'] in used):
        raise ValueError('Unsupported predicate, repeated predicate, or rule complexity')
    for key in ('when_true', 'when_false'):
        validate_tree(tree[key], depth=depth+1, used=(*used, tree['predicate']))
    return tree


def monotone(tree):
    """Exhaustively check every point in the finite anonymous evidence domain."""
    values = [(x, LABELS.index(decide(tree, x))) for x in DOMAIN]
    return (decide(tree, dict(zip(FEATURES, (2, 2, 2)))) == 'yes'
            and all(a <= b for x, a in values for y, b in values
                    if all(x[k] <= y[k] for k in FEATURES)))


def leaf_support(tree, rows, groups, path='root'):
    if 'label' in tree: return {path: len(set(groups))}
    predicate = PREDICATES[tree['predicate']]
    output = {}
    for value, key in ((True, 'when_true'), (False, 'when_false')):
        indices = [i for i, r in enumerate(rows) if (r[predicate['feature']] >= predicate['minimum']) == value]
        output.update(leaf_support(tree[key], [rows[i] for i in indices], [groups[i] for i in indices], path+'/'+key))
    return output


def trees(depth=0, used=()):
    yield {'label': 'partial'}
    yield {'label': 'yes'}
    if depth == LIMITS['max_depth']: return
    for predicate in PREDICATES:
        if predicate in used: continue
        children = list(trees(depth+1, (*used, predicate)))
        for left in children:
            for right in children:
                if left == right: continue
                yield {'predicate': predicate, 'when_true': left, 'when_false': right}


def _base_label(features):
    return 'yes' if all(features[k] == 2 for k in FEATURES) else 'partial'


class LocalEvidenceRuleCalibrator(Calibrator):
    """Fit the same cases subject to fixed reusable syntax and support limits."""
    version = VERSION

    def __init__(self):
        self._artifact = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None):
        if sample_weight is not None: raise ValueError('This local experiment uses equal case weights')
        records, targets = list(X), list(y)
        if (not records or len(records) != len(targets) or any(type(y) is not int or y not in range(3) for y in targets)
                or source_groups is None or len(source_groups) != len(records)
                or len(set(source_groups)) != len(records)):
            raise ValueError('Need matched ordinal targets and distinct explicit source groups')
        summaries = [summarize(r) for r in records]
        indices = [i for i, s in enumerate(summaries) if s['guard'] is None]
        features = [summaries[i]['features'] for i in indices]
        groups = [source_groups[i] for i in indices]
        if len(features) < LIMITS['min_leaf_sources']:
            raise ValueError('Insufficient unguarded source cases for reusable rules')
        best, best_rank, counts = None, None, Counter()
        for tree in trees():
            counts['enumerated'] += 1
            if not monotone(tree): continue
            counts['monotone'] += 1
            support = leaf_support(tree, features, groups)
            if min(support.values()) < LIMITS['min_leaf_sources']: continue
            counts['supported'] += 1
            predictions = [None if s['guard'] == 'unresolved' else 'no' if s['guard'] == 'fixed_no'
                           else decide(tree, s['features']) for s in summaries]
            correct = sum(p == LABELS[y] for p, y in zip(predictions, targets))
            relaxations = sum(decide(tree, point) != _base_label(point) for point in DOMAIN)
            rank = (correct, -split_nodes(tree), -relaxations)
            if best_rank is None or rank > best_rank:
                best, best_rank = deepcopy(tree), rank
        if best is None: raise ValueError('No supported monotone policy in the frozen rule grammar')
        self._artifact = {
            'version': VERSION, 'tree': best, 'predicates': deepcopy(PREDICATES), 'limits': deepcopy(LIMITS),
            'feature_names': list(FEATURES), 'leaf_support': leaf_support(best, features, groups),
            'training_rows': len(records), 'training_feature_ref': digest(summaries),
            'training_target_ref': digest(targets), 'training_correct': best_rank[0],
            'search_counts': dict(counts),
            'selection': 'Maximize local correct; tie: fewer splits, fewer departures from fixed policy, enumeration order.',
            'scope': 'Local fitting accuracy on the same cached records; not robustness or generalization.',
        }
        return self

    def predict_records(self, X):
        if self._artifact is None: raise RuntimeError('Fit or restore the rule policy before prediction')
        result = []
        for record in X:
            summary = summarize(record)
            label = None if summary['guard'] == 'unresolved' else 'no' if summary['guard'] == 'fixed_no' else decide(self._artifact['tree'], summary['features'])
            result.append({'label': label, **summary, 'version': VERSION})
        return result

    def predict(self, X):
        return [float(LABELS.index(r['label'])) if r['label'] is not None else math.nan for r in self.predict_records(X)]

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact is not None else {'version': VERSION}

    @classmethod
    def restore(cls, artifact):
        if (artifact.get('version') != VERSION or artifact.get('predicates') != PREDICATES
                or artifact.get('limits') != LIMITS or artifact.get('feature_names') != list(FEATURES)):
            raise ValueError('Changed reusable rule grammar')
        validate_tree(artifact['tree'])
        if (split_nodes(artifact['tree']) > LIMITS['max_split_nodes'] or not monotone(artifact['tree'])
                or not artifact.get('leaf_support')
                or any(type(n) is not int or n < LIMITS['min_leaf_sources'] for n in artifact['leaf_support'].values())):
            raise ValueError('Nonmonotone or unsupported rule artifact')
        model = cls(); model._artifact = deepcopy(artifact); return model


def feature_conflicts(records, targets):
    """Show irreducible conflicts without assigning identity-specific exceptions."""
    buckets = defaultdict(list)
    for i, (record, target) in enumerate(zip(records, targets)):
        buckets[digest(summarize(record))].append((i, target))
    conflicts, ceiling = [], 0
    for bucket in buckets.values():
        counts = Counter(y for _, y in bucket); ceiling += max(counts.values())
        if len(counts) > 1:
            conflicts.append({'indices': [i for i, _ in bucket], 'target_counts': {LABELS[k]: v for k, v in counts.items()}})
    return {'identical_feature_conflicts': conflicts, 'feature_only_fitting_ceiling': ceiling,
            'note': 'Optimistic ceiling before monotonicity, minimum support and guard constraints.'}
