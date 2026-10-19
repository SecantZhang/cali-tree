"""Reuse child condition vocabularies before adding generic evidence predicates.

No child answers become targets. Recombination and bounded vocabulary repair are
supervised on the full original union. Full-grammar repairs are disclosed.
"""
from copy import deepcopy
import json
import time

from ...decision.artifacts import digest, save_json
from .portable_features_v8 import FEATURES, CONTRACT_REF
from .portable_tree_v8 import VERSION as TREE_VERSION, conflict_report
from .hierarchy_fit_v9 import _warm_tree, _refresh, review, complexity
from .union_learning_v10 import UnionFits, constrained_fit, describe, PROFILES, validate_rows, fit_lock
from .union_merges_v10 import gate, rank, predicates

VERSION = 'reuse-first-union-learning-v11'
REPAIR = {'max_new_predicates': 4, 'restricted_profiles': ['compact', 'deep'],
          'feature_ranking': 'Total leaf split errors, weighted impurity, semantic name; original union labels only',
          'fallback': 'Disclosed full-grammar repair only when no reuse/refinement candidate passes the union gates.'}


def used_leaves(model, rows):
    result = {}
    for r in rows:
        if r['features'] is None:
            continue
        tree = model['runtime']['tree']; path = []
        while 'feature' in tree:
            name = tree['feature']; value = r['features']['features'][name]
            path.append((name, value)); tree = tree['true' if value else 'false']
        result.setdefault(tuple(path), []).append(r)
    return list(result.values())


def repair_ranking(model, rows, existing):
    leaves = used_leaves(model, rows); result = []
    for name in FEATURES:
        if name in existing:
            continue
        errors, impurity, supported_splits = 0, 0.0, 0
        for selected in leaves:
            parts = [[r for r in selected if r['features']['features'][name] == v] for v in (True, False)]
            if min(map(len, parts)) < 2 or any(len({r['instruction'] for r in part}) < 2 for part in parts):
                counts = [sum(r['reference'] == k for r in selected) for k in range(3)]
                errors += len(selected) - max(counts)
                impurity -= sum(v * v / len(selected) for v in counts)
                continue
            supported_splits += 1
            for part in parts:
                counts = [sum(r['reference'] == k for r in part) for k in range(3)]
                errors += len(part) - max(counts)
                impurity -= sum(v * v / len(part) for v in counts)
        result.append(((errors, impurity, not name.startswith('meaning_'), name), name, supported_splits))
    result.sort()
    return [{'feature': name, 'hypothetical_leaf_errors': key[0],
             'supported_leaf_splits': supported} for key, name, supported in result]


def warm_candidate(child, rows, vocabulary):
    rows = sorted(rows, key=lambda r: r['source_group'])
    tree = _warm_tree(child['runtime']['tree'], [r for r in rows if r['features'] is not None], 2)
    artifact = {'version': TREE_VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': PROFILES['deep'],
        'tree': tree, 'search': {'version': VERSION, 'states': 0, 'budget_exhausted': False,
            'distinct_predicates': len(vocabulary), 'nodes': complexity(tree)['nodes'],
            'objective': 'Keep child conditions, reassign terminal labels from the original complete union',
            'global_optimality_claim': False, 'allowed_predicates': sorted(vocabulary)},
        'training': {'source_groups': [r['source_group'] for r in rows],
                     'source_batches': [r['batch'] for r in rows],
                     'feature_ref': digest([r['features'] for r in rows]), 'target_ref': digest([r['reference'] for r in rows])},
        'conflicts': conflict_report([r['features'] for r in rows], [r['reference'] for r in rows], [r['source_group'] for r in rows])}
    return describe(review(_refresh(artifact, rows), rows), rows, 'child_tree_relabel:' + child['runtime']['artifact_ref'])


class ReuseFits(UnionFits):
    def restricted(self, rows, vocabulary, profile):
        key = digest([VERSION, sorted(rows, key=lambda r: r['source_group']), sorted(vocabulary), PROFILES[profile]])
        with fit_lock(self.output, key):
            return self._restricted_locked(rows, vocabulary, profile)

    def _restricted_locked(self, rows, vocabulary, profile):
        rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
        key = digest([VERSION, rows, sorted(vocabulary), PROFILES[profile]])
        path = self.output / 'reuse_fits' / (key + '.json')
        if path.exists():
            value = json.loads(path.read_text())
            if value['fit_ref'] != key or value['content_ref'] != digest({k: v for k, v in value.items() if k != 'content_ref'}):
                raise ValueError('Changed restricted fit cache')
            return deepcopy(value)
        if self.replay:
            raise ValueError('Replay lacks a restricted vocabulary fit')
        start = time.monotonic(); result, error = None, None
        try:
            policy = constrained_fit(rows, PROFILES[profile], features=sorted(vocabulary))
            result = describe(policy, rows, 'child_predicate_recombination:' + profile)
        except ValueError as exc:
            error = str(exc)
        value = {'fit_ref': key, 'vocabulary': sorted(vocabulary), 'profile': profile,
                 'source_groups': [r['source_group'] for r in rows], 'result': result,
                 'error': error, 'elapsed_seconds': time.monotonic() - start}
        value['content_ref'] = digest(value); save_json(path, value); self.new_fits += 1
        return value

    def candidates(self, rows, engine, children=()):
        if engine != 'reuse':
            return super().candidates(rows, engine, children)
        if not children:
            return super().candidates(rows, 'constrained')
        rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
        source_set = {r['source_group'] for r in rows}
        if any(not set(c['policy']['training']['source_groups']) <= source_set for c in children):
            raise ValueError('Child knowledge came from outside the parent union')
        inherited = set().union(*(predicates(c['runtime']['tree']) for c in children))
        vocabulary = set(inherited)
        bank = [warm_candidate(c, rows, vocabulary) for c in children]
        attempts, fit_refs, added = [], [], []
        for count in range(REPAIR['max_new_predicates'] + 1):
            restricted = [self.restricted(rows, vocabulary, p) for p in REPAIR['restricted_profiles']]
            fit_refs.extend(v['fit_ref'] for v in restricted)
            bank.extend(v['result'] for v in restricted if v['result'] is not None)
            # Earlier-stage models remain valid alternatives; prefer the first
            # vocabulary budget with a passing union/retention candidate.
            passing = [c for c in bank if c['portable'] and gate(c, children, rows)['status'] == 'accepted']
            attempts.append({'new_predicate_budget': count, 'vocabulary': sorted(vocabulary),
                             'added_predicates': list(added), 'passing_candidates': len(passing)})
            if passing:
                unique = {}
                for c in sorted(passing, key=rank):
                    value = deepcopy(c); used = predicates(c['runtime']['tree'])
                    value['reuse'] = {'version': VERSION, 'kind': 'child_only' if not used - inherited else 'bounded_refinement',
                        'child_predicates': sorted(inherited), 'used_predicates': sorted(used),
                        'new_used_predicates': sorted(used - inherited),
                        'searched_new_predicates': list(added), 'attempts': attempts,
                        'parent_union_only': True}
                    unique.setdefault(value['runtime']['artifact_ref'], value)
                return list(unique.values()), fit_refs
            if count == REPAIR['max_new_predicates']:
                break
            if not bank:
                break
            best = min(bank, key=rank)
            ranked = repair_ranking(best, rows, vocabulary)
            if not ranked:
                break
            chosen = ranked[0]['feature']; vocabulary.add(chosen); added.append(chosen)
            attempts[-1]['next_predicate_ranking'] = ranked[:8]
        # The repair is visible in each node, never described as child-rule reuse.
        cold, refs = super().candidates(rows, 'constrained', children)
        for c in cold:
            used = predicates(c['runtime']['tree'])
            c['reuse'] = {'version': VERSION, 'kind': 'full_grammar_repair',
                'child_predicates': sorted(inherited), 'used_predicates': sorted(used),
                'new_used_predicates': sorted(used - inherited), 'attempts': attempts,
                'parent_union_only': True}
        return cold, fit_refs + refs
