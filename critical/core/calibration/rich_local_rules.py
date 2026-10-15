"""Bounded local rules over label-blind v2 facts; no text/identity predicates."""
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import product
import math

from .base import Calibrator
from .local_evidence_rules import LIMITS, LABELS, PREDICATES as OLD_PREDICATES, summarize as summarize_base
from ..decision.artifacts import digest
from ..decision.rich_evidence import base_observation, validate_rich

VERSION = 'local-rich-reusable-rules-v2'
FEATURES = ('source_integrity', 'core_minimum', 'constraint_minimum', 'collateral_continuity', 'verification_visibility')
PREDICATES = {**deepcopy(OLD_PREDICATES),
              'no_collateral_entity_or_relation_change': {'feature': 'collateral_continuity', 'minimum': 2},
              'verification_content_visible': {'feature': 'verification_visibility', 'minimum': 2}}
DOMAIN = [dict(zip(FEATURES, values)) for values in product((1, 2), (0, 1, 2), (0, 1, 2), (0, 1, 2), (0, 1, 2))]
DOMAIN_INDEX = {tuple(x[k] for k in FEATURES): i for i, x in enumerate(DOMAIN)}
EDGES = []
for i, point in enumerate(DOMAIN):
    for name in FEATURES:
        if point[name] < 2:
            better = {**point, name: point[name]+1}
            EDGES.append((i, DOMAIN_INDEX[tuple(better[k] for k in FEATURES)]))


def summarize(record):
    if not isinstance(record, dict) or set(record) != {'instruction', 'observations'}:
        raise ValueError('Only instruction and observations accepted')
    obs = validate_rich(record['observations'], record['instruction'])
    base = summarize_base({'instruction': record['instruction'], 'observations': base_observation(obs)})
    if base['guard']: return base
    facts = obs['collateral']; visibility = obs['verification_visibility']['state']
    names = ('entity_loss', 'entity_addition_or_duplication', 'relation_change', 'scene_replacement')
    if any(facts[k]['state'] == 'unknown' for k in names) or visibility in ('unknown', 'unobservable'):
        return {'guard': 'unresolved', 'features': None}
    continuity = 0 if facts['scene_replacement']['state'] == 'present' else (
        1 if any(facts[k]['state'] == 'present' for k in names[:-1]) else 2)
    return {'guard': None, 'features': {**base['features'], 'collateral_continuity': continuity,
            'verification_visibility': 1 if visibility == 'partial' else 2}}


def decide(tree, features):
    while 'label' not in tree:
        p = PREDICATES[tree['predicate']]
        tree = tree['when_true'] if features[p['feature']] >= p['minimum'] else tree['when_false']
    return tree['label']


def nodes(tree):
    return 0 if 'label' in tree else 1 + nodes(tree['when_true']) + nodes(tree['when_false'])


def monotone(tree):
    values = [LABELS.index(decide(tree, x)) for x in DOMAIN]
    return values[-1] == 2 and all(values[a] <= values[b] for a, b in EDGES)


def validate_tree(tree, depth=0, used=()):
    if not isinstance(tree, dict): raise ValueError('Rule nodes must be objects')
    if set(tree) == {'label'}:
        if tree['label'] not in ('partial', 'yes'): raise ValueError('Only Partial/Yes learned leaves')
        return
    if (set(tree) != {'predicate', 'when_true', 'when_false'} or depth >= LIMITS['max_depth']
            or tree['predicate'] not in PREDICATES or tree['predicate'] in used):
        raise ValueError('Unsupported rich rule predicate or complexity')
    for key in ('when_true', 'when_false'): validate_tree(tree[key], depth+1, (*used, tree['predicate']))


def trees(depth=0, used=()):
    yield {'label': 'partial'}; yield {'label': 'yes'}
    if depth == LIMITS['max_depth']: return
    for name in PREDICATES:
        if name in used: continue
        children = list(trees(depth+1, (*used, name)))
        for a in children:
            for b in children:
                if a != b: yield {'predicate': name, 'when_true': a, 'when_false': b}


def supports(tree, features, groups, path='root'):
    if 'label' in tree: return {path: len(set(groups))}
    p = PREDICATES[tree['predicate']]; output = {}
    for truth, key in ((True, 'when_true'), (False, 'when_false')):
        keep = [i for i, x in enumerate(features) if (x[p['feature']] >= p['minimum']) == truth]
        output.update(supports(tree[key], [features[i] for i in keep], [groups[i] for i in keep], path+'/'+key))
    return output


class RichLocalRuleCalibrator(Calibrator):
    version = VERSION

    def __init__(self): self._artifact = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None):
        X, y = list(X), list(y)
        if (sample_weight is not None or not X or len(X) != len(y) or source_groups is None
                or len(source_groups) != len(X) or len(set(source_groups)) != len(X)
                or any(type(v) is not int or v not in range(3) for v in y)):
            raise ValueError('Matched ordinal labels and unique explicit source groups required')
        summaries = [summarize(x) for x in X]
        keep = [i for i, s in enumerate(summaries) if s['guard'] is None]
        features = [summaries[i]['features'] for i in keep]; groups = [source_groups[i] for i in keep]
        if len(features) < LIMITS['min_leaf_sources']: raise ValueError('Insufficient supported evidence')
        best, rank, counts = None, None, Counter()
        for tree in trees():
            counts['enumerated'] += 1
            if not monotone(tree): continue
            counts['monotone'] += 1
            support = supports(tree, features, groups)
            if min(support.values()) < LIMITS['min_leaf_sources']: continue
            counts['supported'] += 1
            predictions = [None if s['guard'] == 'unresolved' else 'no' if s['guard'] == 'fixed_no'
                           else decide(tree, s['features']) for s in summaries]
            correct = sum(p == LABELS[target] for p, target in zip(predictions, y))
            deviations = sum(decide(tree, x) != ('yes' if all(x[k] == 2 for k in FEATURES) else 'partial') for x in DOMAIN)
            candidate_rank = (correct, -nodes(tree), -deviations)
            if rank is None or candidate_rank > rank: best, rank = deepcopy(tree), candidate_rank
        if best is None: raise ValueError('No supported monotone rich policy')
        self._artifact = {'version': VERSION, 'tree': best, 'predicates': deepcopy(PREDICATES),
                          'feature_names': list(FEATURES), 'limits': deepcopy(LIMITS),
                          'leaf_support': supports(best, features, groups), 'search_counts': dict(counts),
                          'training_rows': len(X), 'training_feature_ref': digest(summaries),
                          'training_target_ref': digest(y), 'training_correct': rank[0],
                          'scope': 'Same-case fitting; schema informed by previous inspected errors; no transfer/robustness claim.'}
        return self

    def predict_records(self, X):
        if self._artifact is None: raise RuntimeError('Fit or restore first')
        output = []
        for record in X:
            s = summarize(record)
            label = None if s['guard'] == 'unresolved' else 'no' if s['guard'] == 'fixed_no' else decide(self._artifact['tree'], s['features'])
            output.append({'label': label, **s, 'version': VERSION})
        return output

    def predict(self, X):
        return [float(LABELS.index(r['label'])) if r['label'] is not None else math.nan for r in self.predict_records(X)]

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact else {'version': VERSION}

    @classmethod
    def restore(cls, artifact):
        if (artifact.get('version') != VERSION or artifact.get('predicates') != PREDICATES
                or artifact.get('limits') != LIMITS or artifact.get('feature_names') != list(FEATURES)):
            raise ValueError('Changed rich rule grammar')
        validate_tree(artifact['tree'])
        if (nodes(artifact['tree']) > LIMITS['max_split_nodes'] or not monotone(artifact['tree'])
                or not artifact.get('leaf_support') or any(type(n) is not int or n < 2 for n in artifact['leaf_support'].values())):
            raise ValueError('Nonmonotone or unsupported rich rules')
        result = cls(); result._artifact = deepcopy(artifact); return result


def conflicts(records, targets):
    groups = defaultdict(list)
    for i, (x, y) in enumerate(zip(records, targets)): groups[digest(summarize(x))].append((i, y))
    collisions = []; ceiling = 0
    for rows in groups.values():
        c = Counter(y for _, y in rows); ceiling += max(c.values())
        if len(c) > 1: collisions.append({'indices': [i for i, _ in rows], 'target_counts': {LABELS[k]: v for k, v in c.items()}})
    return {'identical_feature_conflicts': collisions, 'feature_only_fitting_ceiling': ceiling}
