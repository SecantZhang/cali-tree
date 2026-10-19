"""M2-compatible, router-free parent induction over complete training unions.

Written semantic contradictions are excluded during search. Cold union fits and
relabeled child trees compete using original labels; no outside-union fitted
policy is a permitted warm start.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import time

from ...decision.artifacts import digest, save_json
from .portable_features_v8 import FEATURES, CONTRACT_REF, validate_record
from .portable_tree_v8 import PortableSemanticTree, VERSION as TREE_VERSION, LIMITS, conflict_report, metrics
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_review_v8 import CONTRADICTS_YES, violations
from .hierarchy_fit_v9 import _leaf, _refresh, _warm_tree, review, complexity

VERSION = 'union-semantic-learning-v10'
PROFILES = {'shallow': {**LIMITS, 'max_depth': 3},
            'compact': {**LIMITS, 'max_depth': 5}, 'deep': {**LIMITS, 'max_depth': 6}}


@contextmanager
def fit_lock(output, key):
    path = Path(output) / 'locks' / (key + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def validate_rows(rows):
    if (not rows or len({r['source_group'] for r in rows}) != len(rows)
            or any(type(r['reference']) is not int or r['reference'] not in (0, 1, 2)
                   or any(not isinstance(r[k], str) or not r[k].strip()
                          for k in ('source_group', 'instruction', 'batch')) for r in rows)):
        raise ValueError('Original references and distinct training sources required')
    for r in rows:
        validate_record(r['features'])


def constrained_fit(rows, limits, *, features=None):
    rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
    restricted = features is not None
    allowed = tuple(FEATURES if features is None else features)
    if len(allowed) != len(set(allowed)) or not set(allowed) <= set(FEATURES):
        raise ValueError('A merge vocabulary must use declared portable predicates only')
    present = [i for i, r in enumerate(rows) if r['features'] is not None]
    full = sum(1 << i for i in present)
    minimum = limits['min_leaf_sources']
    instruction_masks = {}
    for i in present:
        instruction_masks[rows[i]['instruction']] = instruction_masks.get(rows[i]['instruction'], 0) | (1 << i)
    all_instructions_distinct = len(instruction_masks) == len(present)
    def supported(mask):
        return mask.bit_count() >= minimum and (all_instructions_distinct
            or sum(bool(mask & m) for m in instruction_masks.values()) >= 2)
    if not supported(full):
        raise ValueError('Insufficient distinct-source/instruction support')
    targets = [sum(1 << i for i in present if rows[i]['reference'] == k) for k in range(3)]
    unique = {}
    for name in sorted(allowed, key=lambda k: (not k.startswith('meaning_'), k)):
        mask = sum(1 << i for i in present if rows[i]['features']['features'][name])
        if mask and mask != full:
            # Complementary partitions have different written implications.
            # Retain contradictory-Yes tests separately from ordinary aliases.
            key = (mask if name in CONTRADICTS_YES else min(mask, full ^ mask), name in CONTRADICTS_YES)
            unique.setdefault(key, (name, mask))
    predicates = list(unique.values()); visited = 0; truncated = False
    impossible = len(rows) + 1

    @lru_cache(None)
    def solve(mask, depth, forbids_yes):
        nonlocal visited, truncated
        visited += 1
        counts = [(mask & t).bit_count() for t in targets]
        label = max(range(3), key=lambda k: (counts[k], -k)); n = sum(counts)
        best = (impossible, 10 ** 9, None) if forbids_yes and label == 2 else (n - counts[label], 1, ('leaf', mask))
        if not best[0] or depth == 0 or n < 2 * minimum or counts[2] == n and forbids_yes:
            return best
        if visited > limits['max_search_states']:
            truncated = True; return best
        options = {}
        for name, pmask in predicates:
            a, b = mask & pmask, mask & (full ^ pmask)
            if not supported(a) or not supported(b):
                continue
            ca, cb = [(a & t).bit_count() for t in targets], [(b & t).bit_count() for t in targets]
            na, nb = sum(ca), sum(cb)
            rank = (na - max(ca) + nb - max(cb),
                    -sum(v * v / na for v in ca) - sum(v * v / nb for v in cb),
                    not name.startswith('meaning_'), name)
            key = (a if name in CONTRADICTS_YES else min(a, b), name in CONTRADICTS_YES)
            if key not in options or rank < options[key][0]:
                options[key] = (rank, name, a, b)
        for _, name, a, b in sorted(options.values())[:limits['split_candidates']]:
            left = solve(a, depth - 1, forbids_yes or name in CONTRADICTS_YES)
            right = solve(b, depth - 1, forbids_yes)
            if left[2] is None or right[2] is None:
                continue
            candidate = (left[0] + right[0], 1 + left[1] + right[1], ('split', name, left[2], right[2]))
            if candidate[:2] < best[:2]:
                best = candidate
            if best[0] == 0:
                break
        return best

    answer = solve(full, limits['max_depth'], False)
    if answer[2] is None:
        raise ValueError('No supported semantic tree within the declared search budget')
    def materialize(n):
        if n[0] == 'leaf':
            return _leaf([r for i, r in enumerate(rows) if n[1] & (1 << i)])
        a, b = materialize(n[2]), materialize(n[3])
        return {'type': 'split', 'feature': n[1], 'true': a, 'false': b, 'support': a['support'] + b['support']}
    tree = materialize(answer[2]); solve.cache_clear()
    artifact = {'version': TREE_VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': deepcopy(limits),
        'tree': tree, 'search': {'version': VERSION, 'states': visited, 'budget_exhausted': truncated,
            'distinct_predicates': len(predicates), 'nodes': answer[1], 'global_optimality_claim': False,
            'objective': 'Training errors then nodes; bounded shortlist; written-contradiction and distinct-instruction constraints inside search.'},
        'training': {'source_groups': [r['source_group'] for r in rows], 'source_batches': [r['batch'] for r in rows],
                     'feature_ref': digest([r['features'] for r in rows]), 'target_ref': digest([r['reference'] for r in rows])},
        'conflicts': conflict_report([r['features'] for r in rows], [r['reference'] for r in rows], [r['source_group'] for r in rows])}
    artifact = _refresh(artifact, rows)
    if restricted:
        artifact.pop('artifact_ref')
        artifact['search']['allowed_predicates'] = sorted(allowed)
        artifact['artifact_ref'] = digest(artifact)
        PortableSemanticTree.restore(artifact)
    if violations(artifact['tree']):
        raise ValueError('Constrained fitting emitted an explicitly contradictory Yes rule')
    return artifact


def describe(policy, rows, initialization):
    runtime = PortableRuleExecutor.from_training_policy(policy).metadata()
    decisions = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
    leaf_support = []
    def visit(node):
        if 'feature' in node:
            visit(node['true']); visit(node['false'])
        else:
            selected = [r for r in rows if r['source_group'] in set(node['source_groups'])]
            leaf_support.append({'sources': len(selected), 'instructions': len({r['instruction'] for r in selected}),
                                 'original_batches': len({r['batch'] for r in selected})})
    visit(policy['tree'])
    return {'policy': policy, 'runtime': runtime, 'initialization': initialization,
            'metrics': metrics([d['prediction'] for d in decisions], [r['reference'] for r in rows]),
            'complexity': complexity(runtime['tree']), 'leaf_support': leaf_support,
            'portable': all(s['sources'] >= 2 and s['instructions'] >= 2 for s in leaf_support) and not violations(policy['tree'])}


class UnionFits:
    def __init__(self, output, replay=False):
        self.output = Path(output); self.replay = replay; self.new_fits = 0

    def cold(self, rows, engine, profile):
        key = digest([VERSION, engine, PROFILES[profile], sorted(rows, key=lambda r: r['source_group'])])
        with fit_lock(self.output, key):
            return self._cold_locked(rows, engine, profile)

    def _cold_locked(self, rows, engine, profile):
        rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
        key = digest([VERSION, engine, PROFILES[profile], rows])
        path = self.output / 'fits' / (key + '.json')
        if path.exists():
            value = json.loads(path.read_text())
            if value['fit_ref'] != key or value['content_ref'] != digest({k: v for k, v in value.items() if k != 'content_ref'}):
                raise ValueError('Changed cold union fit cache')
            if value['result'] is not None:
                PortableSemanticTree.restore(value['result']['policy'])
                PortableRuleExecutor(value['result']['runtime'])
            return deepcopy(value)
        if self.replay:
            raise ValueError('Replay cannot fit missing union ' + key)
        start = time.monotonic(); result, error = None, None
        try:
            if engine == 'constrained':
                policy = constrained_fit(rows, PROFILES[profile])
            elif engine == 'postreview':
                model = PortableSemanticTree(limits=PROFILES[profile]).fit(
                    [r['features'] for r in rows], [r['reference'] for r in rows],
                    source_groups=[r['source_group'] for r in rows], source_batches=[r['batch'] for r in rows])
                policy = review(model.metadata(), rows)
            else:
                raise ValueError('Undeclared union learner')
            result = describe(policy, rows, 'cold:' + engine + ':' + profile)
        except ValueError as exc:
            error = str(exc)
        value = {'fit_ref': key, 'engine': engine, 'profile': profile, 'source_groups': [r['source_group'] for r in rows],
                 'feature_ref': digest([r['features'] for r in rows]), 'target_ref': digest([r['reference'] for r in rows]),
                 'result': result, 'error': error, 'elapsed_seconds': time.monotonic() - start}
        value['content_ref'] = digest(value); save_json(path, value); self.new_fits += 1
        print({'cold_union': len(rows), 'engine': engine, 'profile': profile,
               'correct': result['metrics']['correct'] if result else None,
               'seconds': round(value['elapsed_seconds'], 2), 'error': error}, flush=True)
        return value

    def candidates(self, rows, engine, children=()):
        rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
        sources = {r['source_group'] for r in rows}
        for child in children:
            if not set(child['policy']['training']['source_groups']) <= sources:
                raise ValueError('A warm policy contains outside-union training knowledge')
        profiles = ('shallow', 'compact') if len(rows) <= 12 else ('compact', 'deep')
        cold = [self.cold(rows, engine, p) for p in profiles]
        bank = [v['result'] for v in cold if v['result'] is not None]
        if bank:
            template = bank[-1]['policy']
            for child in children:
                warm = deepcopy(template)
                warm['tree'] = _warm_tree(child['runtime']['tree'], [r for r in rows if r['features'] is not None], 2)
                warm = review(_refresh(warm, rows), rows)
                bank.append(describe(warm, rows, 'child_conditions:' + child['runtime']['artifact_ref']))
        unique = {}
        for candidate in bank:
            if candidate['portable']:
                unique.setdefault(candidate['runtime']['artifact_ref'], candidate)
        return list(unique.values()), [v['fit_ref'] for v in cold]

