"""M2-compatible parent induction with actual cross-batch rule support.

Each candidate terminal region must contain distinct sources from at least two
originating batches. This constraint participates in search, rather than merely
discarding an unconstrained winner after fitting. Child predicates are warm
search candidates; original references remain the only targets.
"""
from copy import deepcopy
from functools import lru_cache

from ...decision.artifacts import digest
from .portable_features_v8 import FEATURES, CONTRACT_REF, validate_record
from .portable_tree_v8 import VERSION, conflict_report

SEARCH_VERSION = 'shared-parent-search-v9.1'


def fit_shared(rows, warm_policies, limits):
    from .hierarchy_fit_v9 import _leaf, _refresh
    rows = sorted(rows, key=lambda r: r['source_group'])
    if (len({r['source_group'] for r in rows}) != len(rows)
            or len({r['batch'] for r in rows}) < 2):
        raise ValueError('A parent requires distinct sources and multiple originating batches')
    for r in rows:
        validate_record(r['features'])
    present = [i for i, r in enumerate(rows) if r['features'] is not None]
    full = sum(1 << i for i in present)
    targets = [sum(1 << i for i in present if rows[i]['reference'] == k) for k in range(3)]
    batches = [sum(1 << i for i in present if rows[i]['batch'] == b) for b in sorted({r['batch'] for r in rows})]
    warm_features = set()
    def collect(n):
        if 'feature' in n:
            warm_features.add(n['feature']); collect(n['true']); collect(n['false'])
    for p in warm_policies:
        collect(p['tree'])
    unique = {}
    for name in sorted(FEATURES, key=lambda k: (k not in warm_features, not k.startswith('meaning_'), k)):
        mask = sum(1 << i for i in present if rows[i]['features']['features'][name])
        if mask and mask != full:
            unique.setdefault(min(mask, full ^ mask), (name, mask))
    predicates = list(unique.values()); visited = 0; truncated = False
    minimum = limits['min_leaf_sources']
    def supported(mask):
        return mask.bit_count() >= minimum and sum(bool(mask & b) for b in batches) >= 2
    if not supported(full):
        raise ValueError('Insufficient observed cross-batch parent support')

    @lru_cache(None)
    def solve(mask, depth):
        nonlocal visited, truncated
        visited += 1
        counts = [(mask & t).bit_count() for t in targets]
        n = sum(counts); label = max(range(3), key=lambda k: (counts[k], -k))
        best = (n - counts[label], 1, ('leaf', mask))
        if not best[0] or depth == 0:
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
                    name not in warm_features, not name.startswith('meaning_'), name)
            key = min(a, b)
            if key not in options or rank < options[key][0]:
                options[key] = (rank, name, a, b)
        for _, name, a, b in sorted(options.values())[:limits['split_candidates']]:
            left, right = solve(a, depth - 1), solve(b, depth - 1)
            candidate = (left[0] + right[0], 1 + left[1] + right[1], ('split', name, left[2], right[2]))
            if candidate[:2] < best[:2]:
                best = candidate
            if best[0] == 0:
                break
        return best

    answer = solve(full, limits['max_depth'])
    def materialize(n):
        if n[0] == 'leaf':
            return _leaf([r for i, r in enumerate(rows) if n[1] & (1 << i)])
        a, b = materialize(n[2]), materialize(n[3])
        return {'type': 'split', 'feature': n[1], 'true': a, 'false': b, 'support': a['support'] + b['support']}
    tree = materialize(answer[2]); solve.cache_clear()
    policy = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': deepcopy(limits),
              'tree': tree, 'search': {'version': SEARCH_VERSION, 'states': visited,
              'budget_exhausted': truncated, 'distinct_predicates': len(predicates), 'nodes': answer[1],
              'objective': 'training errors, then nodes; bounded shortlist, shared-rule support constraints',
              'global_optimality_claim': False, 'min_rule_originating_batches': 2,
              'warm_predicates': sorted(warm_features)},
              'training': {'source_groups': [r['source_group'] for r in rows],
                           'source_batches': [r['batch'] for r in rows],
                           'feature_ref': digest([r['features'] for r in rows]),
                           'target_ref': digest([r['reference'] for r in rows])},
              'conflicts': conflict_report([r['features'] for r in rows], [r['reference'] for r in rows],
                                           [r['source_group'] for r in rows])}
    return _refresh(policy, rows)

