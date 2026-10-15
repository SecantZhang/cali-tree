"""Supported semantic partitions with local rules; no mandatory label vetoes.

Training labels select reusable evidence splits. Prediction and routing consume
only the closed M1-derived feature record. Search stops at the first perfect
subtree in a bounded shortlist; no global tree-optimality claim is made.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import math

from ..base import Calibrator
from ...decision.artifacts import digest
from .features_v4 import FEATURES, SPECS, CONTRACT_REF, validate_record

VERSION = 'conflict-aware-semantic-partitions-v4'
LIMITS = {'max_depth': 6, 'split_candidates': 24, 'min_leaf_sources': 2,
          'max_search_states': 1000000, 'group_depth': 2, 'min_group_sources': 6}


def metrics(predictions, targets):
    p, y = list(predictions), list(targets)
    if not y or len(p) != len(y) or any(type(v) is not int or v not in (0,1,2) for v in y) or any(v not in (-1,0,1,2) for v in p):
        raise ValueError('Invalid metric inputs')
    classes = {}
    for k, name in enumerate(('no','partial','yes')):
        support, predicted = y.count(k), p.count(k)
        correct = sum(a == b == k for a,b in zip(p,y))
        classes[name] = {'support': support, 'predicted': predicted, 'correct': correct,
                         'recall': correct / support if support else None,
                         'f1': 2 * correct / (support + predicted) if support + predicted else 0.0}
    correct = sum(c['correct'] for c in classes.values())
    return {'correct': correct, 'total': len(y), 'accuracy': correct / len(y),
            'macro_f1': sum(c['f1'] for c in classes.values()) / 3,
            'worst_present_class_recall': min(c['recall'] for c in classes.values() if c['support']),
            'per_class': classes, 'unresolved': p.count(-1)}


def conflict_report(records, targets, source_groups):
    if len(records) != len(targets) or len(records) != len(source_groups):
        raise ValueError('Unpaired conflict inputs')
    buckets = defaultdict(list); missing = []
    for i, (x, y) in enumerate(zip(records, targets)):
        validate_record(x)
        if type(y) is not int or y not in (0, 1, 2):
            raise ValueError('Invalid reference label')
        if x is None:
            missing.append(source_groups[i])
        else:
            buckets[digest(x)].append(i)
    conflicts = []; unavoidable = len(missing)
    for key, indices in sorted(buckets.items()):
        counts = Counter(targets[i] for i in indices)
        unavoidable += len(indices) - max(counts.values())
        if len(counts) > 1:
            conflicts.append({'feature_ref': key, 'source_groups': [source_groups[i] for i in indices],
                              'reference_counts': dict(sorted(counts.items())),
                              'unavoidable_errors': len(indices) - max(counts.values())})
    # Closest contradictory pairs are diagnostics, never routing predicates.
    pairs = []
    present = [i for i, x in enumerate(records) if x is not None]
    for pos, i in enumerate(present):
        for j in present[pos + 1:]:
            if targets[i] != targets[j]:
                differences = [k for k in FEATURES if records[i]['features'][k] != records[j]['features'][k]]
                pairs.append({'source_groups': [source_groups[i], source_groups[j]],
                              'labels': [targets[i], targets[j]], 'distance': len(differences),
                              'distinguishing_features': differences})
    pairs.sort(key=lambda p: (p['distance'], p['source_groups']))
    return {'exact_conflicts': conflicts, 'missing_sources': missing,
            'feature_identifiability_upper_bound': len(records) - unavoidable,
            'total': len(records), 'closest_cross_label_pairs': pairs[:12],
            'scope': 'Equality bound only; does not establish perceptual truth or a supported-rule optimum.'}


def _indices(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


class ConflictAwareSemanticTree(Calibrator):
    version = VERSION

    def __init__(self, *, limits=None):
        self.limits = dict(LIMITS if limits is None else limits)
        if set(self.limits) != set(LIMITS) or any(type(v) is not int or v < 1 for v in self.limits.values()):
            raise ValueError('Invalid search limits')
        if self.limits['min_leaf_sources'] < 2 or self.limits['group_depth'] > self.limits['max_depth']:
            raise ValueError('At least two sources per leaf and a valid grouping depth are required')
        self._artifact = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None, source_batches=None):
        X, y = list(X), list(y); groups = list(source_groups or []); batches = list(source_batches or [])
        if (sample_weight is not None or len(X) != len(y) or len(groups) != len(y) or len(batches) != len(y)
                or len(set(groups)) != len(groups) or any(not isinstance(g, str) or not g for g in groups + batches)
                or any(type(v) is not int or v not in (0, 1, 2) for v in y)):
            raise ValueError('Distinct sources, paired labels, and originating batches required')
        for x in X:
            validate_record(x)
        order = sorted(range(len(X)), key=lambda i: groups[i])
        X, y, groups, batches = ([v[i] for i in order] for v in (X, y, groups, batches))
        present = [i for i, x in enumerate(X) if x is not None]
        if len(present) < self.limits['min_leaf_sources']:
            raise ValueError('Insufficient observed sources')
        full = sum(1 << i for i in present)
        targets = [sum(1 << i for i in present if y[i] == k) for k in range(3)]
        # Collapse identical finite-sample partitions, retaining a deterministic
        # semantic representative. Source IDs never become branch conditions.
        unique = {}
        for feature in FEATURES:
            mask = sum(1 << i for i in present if X[i]['features'][feature])
            if mask and mask != full:
                unique.setdefault(min(mask, full ^ mask), (feature, mask))
        predicates = list(unique.values()); visited = 0; truncated = False
        minimum = self.limits['min_leaf_sources']

        @lru_cache(None)
        def solve(mask, depth):
            nonlocal visited, truncated
            visited += 1
            counts = [(mask & t).bit_count() for t in targets]; n = sum(counts)
            label = max(range(3), key=lambda k: (counts[k], -k))
            best = (n - counts[label], 1, ('leaf', label, mask))
            if not best[0] or depth == 0 or n < 2 * minimum:
                return best
            if visited > self.limits['max_search_states']:
                truncated = True
                return best
            proposals = {}
            for index, (name, pmask) in enumerate(predicates):
                left = mask & pmask; right = mask ^ left
                nl, nr = left.bit_count(), right.bit_count()
                if min(nl, nr) < minimum:
                    continue
                lc = [(left & t).bit_count() for t in targets]; rc = [(right & t).bit_count() for t in targets]
                rank = (nl - max(lc) + nr - max(rc),
                        -sum(v * v / nl for v in lc) - sum(v * v / nr for v in rc), abs(nl - nr), name)
                key = min(left, right)
                if key not in proposals or rank < proposals[key][0]:
                    proposals[key] = (rank, index, left, right)
            for _, index, left, right in sorted(proposals.values())[:self.limits['split_candidates']]:
                a, b = solve(left, depth - 1), solve(right, depth - 1)
                candidate = (a[0] + b[0], 1 + a[1] + b[1], ('split', predicates[index][0], a[2], b[2]))
                if candidate[:2] < best[:2]:
                    best = candidate
                if best[0] == 0:
                    break
            return best

        answer = solve(full, self.limits['max_depth'])
        # Materialize provenance separately from executable branch fields.
        def materialize(node):
            if node[0] == 'leaf':
                indices = list(_indices(node[2]))
                return {'type': 'leaf', 'prediction': node[1], 'support': len(indices),
                        'counts': [sum(y[i] == k for i in indices) for k in range(3)],
                        'source_groups': [groups[i] for i in indices],
                        'source_batches': dict(sorted(Counter(batches[i] for i in indices).items()))}
            a, b = materialize(node[2]), materialize(node[3])
            return {'type': 'split', 'feature': node[1], 'true': a, 'false': b, 'support': a['support'] + b['support']}
        tree = materialize(answer[2]); solve.cache_clear()
        artifact = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': deepcopy(self.limits),
                    'tree': tree, 'search': {'states': visited, 'budget_exhausted': truncated,
                    'distinct_predicates': len(predicates), 'nodes': answer[1],
                    'objective': 'training errors, then nodes; first perfect subtree in bounded shortlist',
                    'global_optimality_claim': False},
                    'training': {'source_groups': groups, 'source_batches': batches, 'feature_ref': digest(X), 'target_ref': digest(y)},
                    'conflicts': conflict_report(X, y, groups)}
        self._artifact = artifact
        predictions = [p['prediction'] for p in self.predict_records(X)]
        artifact['training']['metrics'] = metrics(predictions, y)
        artifact['groups'] = self._groups(X, y, groups)
        artifact['artifact_ref'] = digest(artifact)
        return self

    def _is_group(self, node, depth):
        return (node['type'] == 'leaf' or depth >= self.limits['group_depth'] or
                min(node['true']['support'], node['false']['support']) < self.limits['min_group_sources'])

    def predict_records(self, X):
        if self._artifact is None:
            raise ValueError('No fitted policy')
        result = []
        for record in X:
            validate_record(record)
            if record is None:
                result.append({'prediction': -1, 'group_id': None, 'trace': [], 'reason': 'missing_evidence'})
                continue
            node = self._artifact['tree']; trace = []; group = None; depth = 0
            while True:
                if group is None and self._is_group(node, depth):
                    group = 'scope-' + digest(trace)[:16]
                if node['type'] == 'leaf':
                    break
                value = record['features'][node['feature']]
                trace.append({'feature': node['feature'], 'value': value})
                node = node['true' if value else 'false']; depth += 1
            result.append({'prediction': node['prediction'], 'group_id': group, 'trace': trace,
                           'leaf_support': node['support'], 'training_confidence': max(node['counts']) / node['support'],
                           'reason': 'learned_semantic_rule', 'conflicted_leaf': sum(v > 0 for v in node['counts']) > 1})
        return result

    def _groups(self, X, y, sources):
        nodes = []
        def visit(node, path):
            if self._is_group(node, len(path)):
                nodes.append((node, path)); return
            for value in (True, False):
                visit(node['true' if value else 'false'], path + [{'feature': node['feature'], 'value': value}])
        visit(self._artifact['tree'], [])
        predictions = self.predict_records(X); result = []
        for node, path in nodes:
            gid = 'scope-' + digest(path)[:16]
            selected = [i for i, p in enumerate(predictions) if p['group_id'] == gid]
            result.append({'group_id': gid, 'conditions': path, 'local_policy': deepcopy(node),
                           'source_groups': [sources[i] for i in selected],
                           'metrics': metrics([predictions[i]['prediction'] for i in selected], [y[i] for i in selected]),
                           'conflicts': conflict_report([X[i] for i in selected], [y[i] for i in selected], [sources[i] for i in selected])})
        return result

    def predict(self, X):
        return [math.nan if r['prediction'] < 0 else float(r['prediction']) for r in self.predict_records(X)]

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact else {'version': VERSION}

    def render(self):
        if self._artifact is None:
            raise ValueError('No fitted policy')
        lines = []
        def visit(node, path):
            if node['type'] == 'leaf':
                condition = ' AND '.join(('' if v else 'NOT ') + SPECS[k] for k, v in path) or 'Always'
                lines.append(condition + ' => ' + ('No', 'Partial', 'Yes')[node['prediction']] + f" [sources={node['support']}; labels={node['counts']}]")
            else:
                visit(node['true'], path + [(node['feature'], True)])
                visit(node['false'], path + [(node['feature'], False)])
        visit(self._artifact['tree'], [])
        return '\n'.join(lines)

    @classmethod
    def restore(cls, artifact):
        if (artifact.get('version') != VERSION or artifact.get('feature_contract_ref') != CONTRACT_REF
                or digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact.get('artifact_ref')):
            raise ValueError('Changed semantic tree contract')
        obj = cls(limits=artifact['limits']); sources = set(artifact['training']['source_groups'])
        if len(sources) != len(artifact['training']['source_groups']):
            raise ValueError('Duplicate source provenance')
        seen = set()
        def validate(node, depth):
            if depth > obj.limits['max_depth']:
                raise ValueError('Tree exceeds depth budget')
            if node['type'] == 'leaf':
                if set(node) != {'type','prediction','support','counts','source_groups','source_batches'}:
                    raise ValueError('Invalid leaf contract')
                if (type(node['prediction']) is not int or node['prediction'] not in (0,1,2)
                        or len(node['counts']) != 3 or any(type(v) is not int or v < 0 for v in node['counts'])
                        or sum(node['counts']) != node['support'] or node['support'] < obj.limits['min_leaf_sources']
                        or len(set(node['source_groups'])) != node['support']
                        or sum(node['source_batches'].values()) != node['support']):
                    raise ValueError('Invalid leaf support')
                if not set(node['source_groups']) <= sources or seen & set(node['source_groups']):
                    raise ValueError('Unbound or repeated leaf sources')
                seen.update(node['source_groups'])
                if node['prediction'] != max(range(3), key=lambda k: (node['counts'][k],-k)):
                    raise ValueError('Leaf prediction conflicts with fitted counts')
            elif node['type'] == 'split':
                if set(node) != {'type','feature','true','false','support'} or node['feature'] not in SPECS:
                    raise ValueError('Non-semantic branch')
                validate(node['true'], depth + 1); validate(node['false'], depth + 1)
                if node['support'] != node['true']['support'] + node['false']['support']:
                    raise ValueError('Invalid branch support')
            else:
                raise ValueError('Invalid node type')
        validate(artifact['tree'], 0)
        if seen | set(artifact['conflicts']['missing_sources']) != sources:
            raise ValueError('Incomplete fitting provenance')
        obj._artifact = deepcopy(artifact)
        return obj
