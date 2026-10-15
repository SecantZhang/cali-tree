"""Three-label reusable rules with decision-dependent uncertainty.

No protected label assignments: correspondence, fulfillment and source facts are
learned inputs. Unknown facts are intervals, never failed checks or guessed labels.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import product
import math

import numpy as np

from .base import Calibrator
from ..decision.artifacts import digest
from ..decision.rich_evidence import validate_rich

VERSION = 'three-label-evidence-rules-v3'
LABELS = ('no', 'partial', 'yes')
LIMITS = {'max_depth': 2, 'max_split_nodes': 3, 'min_leaf_sources': 2}
FEATURES = ('target_match', 'source_integrity', 'core_minimum', 'core_maximum',
            'constraint_minimum', 'collateral_continuity', 'verification_visibility')
PREDICATES = {
    'target_matches': {'feature': 'target_match', 'minimum': 1},
    'source_meaning_retained': {'feature': 'source_integrity', 'minimum': 1},
    'source_preserved': {'feature': 'source_integrity', 'minimum': 2},
    'some_core_progress': {'feature': 'core_maximum', 'minimum': 1},
    'some_core_complete': {'feature': 'core_maximum', 'minimum': 2},
    'every_core_has_progress': {'feature': 'core_minimum', 'minimum': 1},
    'every_core_complete': {'feature': 'core_minimum', 'minimum': 2},
    'every_constraint_has_progress': {'feature': 'constraint_minimum', 'minimum': 1},
    'every_constraint_complete': {'feature': 'constraint_minimum', 'minimum': 2},
    'no_collateral_entity_or_relation_change': {'feature': 'collateral_continuity', 'minimum': 2},
    'verification_content_visible': {'feature': 'verification_visibility', 'minimum': 2},
}
STRENGTH = {'absent': 0, 'incomplete': 1, 'complete': 2}
DOMAIN = [dict(zip(FEATURES, x)) for x in product((0, 1), *([range(3)]*6)) if x[2] <= x[3]]
DOMAIN_ARRAY = np.asarray([[x[k] for k in FEATURES] for x in DOMAIN], dtype=np.int8)
DOMAIN_INDEX = {tuple(row): i for i, row in enumerate(DOMAIN_ARRAY)}
EDGES = []
for i, x in enumerate(DOMAIN_ARRAY):
    for j, name in enumerate(FEATURES):
        if x[j] < (1 if name == 'target_match' else 2):
            better = x.copy(); better[j] += 1
            index = DOMAIN_INDEX.get(tuple(better))
            if index is not None: EDGES.append((i, index))
EDGE_FROM = np.asarray([a for a, _ in EDGES]); EDGE_TO = np.asarray([b for _, b in EDGES])


def evidence_bounds(record):
    if not isinstance(record, dict) or set(record) != {'instruction', 'observations'}:
        raise ValueError('Only instruction and observations are accepted')
    o = validate_rich(record['observations'], record['instruction'])
    lower, upper = {}, {}
    def interval(name, state, mapping, unknown):
        lo, hi = unknown if state == 'unknown' else (mapping[state], mapping[state])
        lower[name], upper[name] = lo, hi
    interval('target_match', o['target']['state'], {'matched': 1, 'wrong_target': 0}, (0, 1))
    interval('source_integrity', o['source_integrity']['state'],
             {'meaning_destroyed': 0, 'material_deviation': 1, 'preserved': 2}, (0, 2))
    for role in ('core', 'constraint'):
        reqs = [r for r in o['requirements'] if r['role'] == role]
        low = [0 if r['state'] == 'unknown' else STRENGTH[r['state']] for r in reqs]
        high = [2 if r['state'] == 'unknown' else STRENGTH[r['state']] for r in reqs]
        lower[role+'_minimum'], upper[role+'_minimum'] = min(low, default=2), min(high, default=2)
        if role == 'core': lower['core_maximum'], upper['core_maximum'] = max(low), max(high)
    facts = o['collateral']
    def continuity(unknown_present):
        present = lambda name: facts[name]['state'] == 'present' or (unknown_present and facts[name]['state'] == 'unknown')
        if present('scene_replacement'): return 0
        if any(present(k) for k in ('entity_loss', 'entity_addition_or_duplication', 'relation_change')): return 1
        return 2
    lower['collateral_continuity'], upper['collateral_continuity'] = continuity(True), continuity(False)
    interval('verification_visibility', o['verification_visibility']['state'],
             {'full': 2, 'not_applicable': 2, 'partial': 1, 'unobservable': 0}, (0, 2))
    return {'lower': {k: lower[k] for k in FEATURES}, 'upper': {k: upper[k] for k in FEATURES}}


def decide(tree, features):
    while 'label' not in tree:
        p = PREDICATES[tree['predicate']]
        tree = tree['when_true'] if features[p['feature']] >= p['minimum'] else tree['when_false']
    return tree['label']


def node_count(tree):
    return 0 if 'label' in tree else 1 + node_count(tree['when_true']) + node_count(tree['when_false'])


def validate_tree(tree, depth=0, used=()):
    if not isinstance(tree, dict): raise ValueError('Rule nodes must be objects')
    if set(tree) == {'label'}:
        if tree['label'] not in LABELS: raise ValueError('Invalid learned label')
        return
    if (set(tree) != {'predicate', 'when_true', 'when_false'} or depth >= LIMITS['max_depth']
            or tree['predicate'] not in PREDICATES or tree['predicate'] in used):
        raise ValueError('Unsupported reusable predicate or tree complexity')
    for key in ('when_true', 'when_false'): validate_tree(tree[key], depth+1, (*used, tree['predicate']))


def vector(tree):
    if 'label' in tree: return np.full(len(DOMAIN), LABELS.index(tree['label']), dtype=np.int8)
    p = PREDICATES[tree['predicate']]
    mask = DOMAIN_ARRAY[:, FEATURES.index(p['feature'])] >= p['minimum']
    return np.where(mask, vector(tree['when_true']), vector(tree['when_false']))


def monotone_values(values):
    return values[-1] == 2 and bool(np.all(values[EDGE_FROM] <= values[EDGE_TO]))


def monotone(tree): return monotone_values(vector(tree))


def trees(depth=0, used=()):
    for label in LABELS: yield {'label': label}
    if depth == LIMITS['max_depth']: return
    for predicate in PREDICATES:
        if predicate in used: continue
        children = list(trees(depth+1, (*used, predicate)))
        for a in children:
            for b in children:
                if a != b: yield {'predicate': predicate, 'when_true': a, 'when_false': b}


def shape(tree):
    return 'leaf' if 'label' in tree else (tree['predicate'], shape(tree['when_true']), shape(tree['when_false']))


def definite_support(tree, bounds, groups, path='root'):
    """Only cases guaranteed to reach a leaf count toward its source support."""
    if 'label' in tree: return {path: len(set(groups))}
    p = PREDICATES[tree['predicate']]; output = {}
    for truth, key in ((True, 'when_true'), (False, 'when_false')):
        keep = [i for i, b in enumerate(bounds) if (b['lower'][p['feature']] >= p['minimum'] if truth
                                                    else b['upper'][p['feature']] < p['minimum'])]
        output.update(definite_support(tree[key], [bounds[i] for i in keep], [groups[i] for i in keep], path+'/'+key))
    return output


def prediction(tree, bounds):
    low, high = decide(tree, bounds['lower']), decide(tree, bounds['upper'])
    label = low if low == high else None
    return {'label': label, 'resolved': label is not None, 'label_bounds': [low, high],
            'evidence_bounds': bounds,
            'uncertain_features': [k for k in FEATURES if bounds['lower'][k] != bounds['upper'][k]],
            'resolution': 'All possible evidence completions agree' if label else 'Unknown evidence changes the learned label',
            'version': VERSION}


class EvidenceRuleCalibrator(Calibrator):
    version = VERSION
    def __init__(self): self._artifact = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None):
        X, y = list(X), list(y)
        if (sample_weight is not None or not X or len(X) != len(y) or source_groups is None
                or len(source_groups) != len(X) or len(set(source_groups)) != len(X)
                or any(type(v) is not int or v not in range(3) for v in y)):
            raise ValueError('Matched ordinal labels and unique explicit source groups required')
        bounds = [evidence_bounds(x) for x in X]
        low_indices = np.asarray([DOMAIN_INDEX[tuple(b['lower'][k] for k in FEATURES)] for b in bounds])
        high_indices = np.asarray([DOMAIN_INDEX[tuple(b['upper'][k] for k in FEATURES)] for b in bounds])
        targets = np.asarray(y); cache = {}; counts = Counter(); best = rank = None
        reference = np.where((DOMAIN_ARRAY[:, 0] == 0) | (DOMAIN_ARRAY[:, 1] == 0) | (DOMAIN_ARRAY[:, 3] == 0), 0,
                             np.where(np.all(DOMAIN_ARRAY[:, 1:] == 2, axis=1), 2, 1))
        for tree in trees():
            counts['enumerated'] += 1
            key = shape(tree)
            if key not in cache: cache[key] = definite_support(tree, bounds, source_groups)
            support = cache[key]
            if min(support.values()) < LIMITS['min_leaf_sources']: continue
            counts['supported'] += 1
            values = vector(tree)
            if not monotone_values(values): continue
            counts['supported_monotone'] += 1
            lo, hi = values[low_indices], values[high_indices]
            correct = int(np.count_nonzero((lo == hi) & (lo == targets)))
            candidate_rank = (correct, -node_count(tree), -int(np.count_nonzero(values != reference)))
            if rank is None or candidate_rank > rank: best, rank = deepcopy(tree), candidate_rank
        if best is None: raise ValueError('No supported monotone policy')
        self._artifact = {'version': VERSION, 'tree': best, 'predicates': deepcopy(PREDICATES),
                          'feature_names': list(FEATURES), 'limits': deepcopy(LIMITS),
                          'leaf_support': definite_support(best, bounds, source_groups), 'search_counts': dict(counts),
                          'training_rows': len(X), 'training_correct': rank[0],
                          'training_feature_ref': digest(bounds), 'training_target_ref': digest(y),
                          'uncertainty': 'Resolve only if monotone lower/upper completions yield the same label.',
                          'guards': 'No immutable label guards; all three labels are learned.',
                          'scope': 'Same-case local fitting; not unseen accuracy or repeat robustness.'}
        return self

    def predict_records(self, X):
        if self._artifact is None: raise RuntimeError('Fit or restore first')
        return [prediction(self._artifact['tree'], evidence_bounds(x)) for x in X]

    def predict(self, X):
        return [float(LABELS.index(r['label'])) if r['label'] is not None else math.nan for r in self.predict_records(X)]

    def metadata(self): return deepcopy(self._artifact) if self._artifact else {'version': VERSION}

    @classmethod
    def restore(cls, artifact):
        if (artifact.get('version') != VERSION or artifact.get('predicates') != PREDICATES
                or artifact.get('limits') != LIMITS or artifact.get('feature_names') != list(FEATURES)):
            raise ValueError('Changed v3 calibration contract')
        validate_tree(artifact['tree'])
        if (node_count(artifact['tree']) > LIMITS['max_split_nodes'] or not monotone(artifact['tree'])
                or not artifact.get('leaf_support') or any(type(n) is not int or n < 2 for n in artifact['leaf_support'].values())):
            raise ValueError('Nonmonotone or unsupported v3 policy')
        result = cls(); result._artifact = deepcopy(artifact); return result


def feature_conflicts(records, targets):
    buckets = defaultdict(list)
    for i, (x, y) in enumerate(zip(records, targets)): buckets[digest(evidence_bounds(x))].append((i, y))
    collisions = []; ceiling = 0
    for rows in buckets.values():
        c = Counter(y for _, y in rows); ceiling += max(c.values())
        if len(c) > 1: collisions.append({'indices': [i for i, _ in rows], 'target_counts': {LABELS[k]: v for k, v in c.items()}})
    return {'identical_evidence_bound_conflicts': collisions, 'optimistic_feature_only_ceiling': ceiling,
            'note': 'Optimistic before monotonicity, support, bounded depth and unresolved-completion constraints.'}
