"""Training partitions for router-free union learning; never inference scopes."""
from collections import defaultdict
from fractions import Fraction

from ...decision.artifacts import digest
from .portable_features_v8 import FEATURES, OPERATIONS, validate_record

VERSION = 'union-training-groups-v10'
AXES = {
    'operation': tuple('requires_' + k for k in OPERATIONS),
    'progress': tuple(k for k in FEATURES if k.startswith('meaning_progress_')),
    'endpoint': tuple(k for k in FEATURES if k.startswith('meaning_endpoint_gap_')),
    'context': tuple(k for k in FEATURES if k.startswith(('meaning_retention_need_',
        'meaning_identity_materiality_', 'meaning_collateral_materiality_', 'meaning_evidence_consistency_'))),
    'physical': tuple(k for k in FEATURES if any(k.startswith(p + '_all_') for p in (
        'outcome', 'identity', 'preservation', 'intermediate', 'collateral_disappearance', 'collateral_deformation'))),
}
WEIGHTS = {'operation': 2, 'progress': 3, 'endpoint': 3, 'context': 1, 'physical': 1}


def distance(a, b):
    validate_record(a); validate_record(b)
    if a is None or b is None:
        return Fraction(0) if a is b else Fraction(1)
    return sum(Fraction(WEIGHTS[name] * sum(a['features'][k] != b['features'][k] for k in keys), len(keys))
               for name, keys in AXES.items() if keys) / sum(WEIGHTS.values())


def original(rows):
    buckets = defaultdict(list)
    for r in rows:
        buckets[r['batch']].append(r['source_group'])
    return [sorted(v) for _, v in sorted(buckets.items())]


def split_balanced(rows):
    """Split each original twelve into two six-case, two-per-label batches."""
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r['batch'], r['reference'])].append(r)
    result = defaultdict(list)
    for (batch, label), selected in sorted(buckets.items()):
        if len(selected) != 4:
            raise ValueError('This declared split requires four sources per batch/class')
        for i, row in enumerate(sorted(selected, key=lambda r: r['source_group'])):
            result[(batch, i % 2)].append(row['source_group'])
    return [sorted(v) for _, v in sorted(result.items())]


def semantic(rows, size=6):
    """Capacity-bounded semantic clustering without reading reference labels.

    Farthest-first centers, constrained greedy assignment, then improving swaps.
    Missing evidence stays in the partition and is never used as a center.
    """
    rows = sorted(rows, key=lambda r: r['source_group'])
    if len(rows) % size or len(rows) // size < 2:
        raise ValueError('Semantic seed groups must divide the complete source set')
    n, k = len(rows), len(rows) // size
    costs = [[distance(a['features'], b['features']) for b in rows] for a in rows]
    present = [i for i, r in enumerate(rows) if r['features'] is not None]
    if len(present) < k:
        raise ValueError('Insufficient observed sources for distinct semantic centers')
    centers = [min(present, key=lambda i: (sum(costs[i]), i))]
    while len(centers) < k:
        centers.append(max((i for i in present if i not in centers),
                           key=lambda i: (min(costs[i][j] for j in centers), -i)))
    groups = [[c] for c in centers]
    remaining = [i for i in range(n) if i not in centers]
    remaining.sort(key=lambda i: (-sorted(costs[i][c] for c in centers)[1]
                                  + min(costs[i][c] for c in centers), i))
    for i in remaining:
        best = min((j for j in range(k) if len(groups[j]) < size),
                   key=lambda j: (costs[i][centers[j]], j))
        groups[best].append(i)
    for _ in range(64):
        choices = []
        for a in range(k):
            for b in range(a + 1, k):
                for i in groups[a]:
                    for j in groups[b]:
                        before = sum(costs[i][v] for v in groups[a] if v != i) + sum(costs[j][v] for v in groups[b] if v != j)
                        after = sum(costs[j][v] for v in groups[a] if v != i) + sum(costs[i][v] for v in groups[b] if v != j)
                        if after < before:
                            choices.append((after - before, a, b, i, j))
        if not choices:
            break
        _, a, b, i, j = min(choices)
        groups[a].remove(i); groups[b].remove(j); groups[a].append(j); groups[b].append(i)
    return sorted((sorted(rows[i]['source_group'] for i in g) for g in groups), key=digest)


def validate_partition(groups, rows):
    flat = [s for g in groups for s in g]
    if (not groups or any(not g for g in groups) or len(flat) != len(set(flat))
            or set(flat) != {r['source_group'] for r in rows}):
        raise ValueError('Training partition dropped or duplicated original sources')

