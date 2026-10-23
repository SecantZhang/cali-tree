"""Distill a frozen gate's abstentions after an expert merge.

Only existing accept/defer behavior supervises this rejection layer. Human
references, source memberships and case IDs are not inputs to its fitting rule
or runtime. The old v23 counterexample clauses stay unchanged in the core gate.
"""
from copy import deepcopy
from functools import lru_cache

from ..decision.artifacts import digest
from .evidence_coverage_v20 import FEATURES, CONTRACT_REF, feature_values, project
from .counterexample_coverage_v23 import RejectionCoverageGate

VERSION = 'merge-route-support-v24'


def core_artifact(gate):
    return gate.artifact['core_gate'] if gate.artifact['version'] == VERSION else gate.artifact


def restore(artifact):
    return MergeCoverageGate(artifact) if artifact['version'] == VERSION else RejectionCoverageGate(artifact)


class _Limit(Exception):
    pass


def preserve_routes(previous, candidate, probes, *, max_literals=3, max_states=20000):
    if type(max_literals) is not int or not 1 <= max_literals <= 3 or type(max_states) is not int or max_states < 1:
        raise ValueError('Positive route-support bounds and at most three literals are required')
    positive = []; negative = []
    for probe in probes:
        before = previous.select(probe['program'], probe['features'])
        after = candidate.select(probe['program'], probe['features'])
        if before['covered']:
            if not after['covered'] or before['prediction'] != after['prediction']:
                return None, {'status': 'cannot_repair_lost_coverage_or_verdict', 'new_deferrals': []}
            positive.append(feature_values(probe['program'], probe['features']))
        elif after['covered']:
            negative.append(feature_values(probe['program'], probe['features']))
    if not negative:
        return candidate, {'status': 'already_preserved', 'new_deferrals': [], 'clauses': [], 'states': 0}
    if not positive or any(v is None for v in positive + negative):
        return None, {'status': 'invalid_route_support', 'new_deferrals': []}
    positive.sort(key=digest); negative.sort(key=digest)
    full = (1 << len(positive)) - 1; candidates = {}; total_states = 0
    for neg in negative:
        options = {}
        for f in sorted(FEATURES, key=lambda f: (not f.startswith('meaning_'), not f.startswith('task_'), f)):
            value = not neg[f]; mask = sum(1 << i for i, row in enumerate(positive) if row[f] == value)
            if mask:
                options.setdefault(mask, {'feature': f, 'value': value})
        states = 0
        @lru_cache(None)
        def solve(remaining, depth):
            nonlocal states
            if not remaining:
                return ()
            if not depth:
                return None
            if states >= max_states:
                raise _Limit
            states += 1
            bits = [1 << i for i in range(len(positive)) if remaining >> i & 1]
            pivot = min(bits, key=lambda b: (sum(bool(m & b) for m in options), digest(positive[b.bit_length()-1])))
            best = None
            for mask in sorted((m for m in options if m & pivot), key=lambda m: (-(m & remaining).bit_count(), options[m]['feature'])):
                tail = solve(remaining & ~mask, depth-1)
                if tail is not None:
                    value = (mask,) + tail
                    if best is None or len(value) < len(best):
                        best = value
                    if len(best) == 1:
                        break
            return best
        try:
            answer = solve(full, max_literals)
        except _Limit:
            return None, {'status': 'route_support_search_limit', 'states': total_states + states}
        total_states += states
        if answer is None:
            return None, {'status': 'no_compact_route_support', 'states': total_states}
        clause = sorted((options[m] for m in answer), key=lambda c: (c['feature'], c['value']))
        rejected = sum(1 << i for i, row in enumerate(negative) if not any(row[c['feature']] == c['value'] for c in clause))
        candidates[digest(clause)] = (clause, rejected)
    uncovered = (1 << len(negative)) - 1; clauses = []
    while uncovered:
        clause, mask = min((v for v in candidates.values() if v[1] & uncovered),
                           key=lambda v: (-(v[1] & uncovered).bit_count(), len(v[0]), digest(v[0])))
        clauses.append(clause); uncovered &= ~mask
    clauses.sort(key=digest)
    artifact = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'core_gate': candidate.export(),
                'clauses': clauses, 'max_literals': max_literals,
                'calibration': {'protected_acceptances': len(positive), 'preserved_deferrals': len(negative)}}
    artifact['artifact_ref'] = digest(artifact)
    result = MergeCoverageGate(artifact)
    for probe in probes:
        before = previous.select(probe['program'], probe['features']); after = result.select(probe['program'], probe['features'])
        if (before['covered'], before['prediction']) != (after['covered'], after['prediction']):
            raise AssertionError('Routing distillation failed its frozen constraints')
    return result, {'status': 'preserved_with_compact_clauses', 'clauses': clauses, 'states': total_states,
                    'protected_acceptances': len(positive), 'preserved_deferrals': len(negative),
                    'human_reference_labels_used': False}


class MergeCoverageGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'feature_contract_ref', 'core_gate', 'clauses', 'max_literals', 'calibration', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['feature_contract_ref'] != CONTRACT_REF
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
                or type(artifact['max_literals']) is not int or not 1 <= artifact['max_literals'] <= 3):
            raise ValueError('Invalid merge coverage contract')
        self.core = RejectionCoverageGate(artifact['core_gate'])
        counts = artifact['calibration']
        if (set(counts) != {'protected_acceptances', 'preserved_deferrals'}
                or any(type(v) is not int or v < 1 for v in counts.values())):
            raise ValueError('Invalid routing calibration counts')
        for clause in artifact['clauses']:
            if not 1 <= len(clause) <= artifact['max_literals'] or len({c['feature'] for c in clause}) != len(clause):
                raise ValueError('Invalid merge support clause')
            for c in clause:
                if set(c) != {'feature', 'value'} or c['feature'] not in FEATURES or type(c['value']) is not bool:
                    raise ValueError('Undeclared merge support feature')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def accepts_task(self, program):
        return self.core.accepts_task(program)

    def select(self, program, record):
        route = self.core.select(program, record)
        if not route['covered']:
            return route
        values = feature_values(program, record)
        failed = [digest(clause) for clause in self.artifact['clauses'] if not any(values[c['feature']] == c['value'] for c in clause)]
        if failed:
            return {'covered': False, 'prediction': -1, 'reason': 'preserved_merge_abstention', 'matches': [], 'support_clauses': failed}
        return route

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, project(program, observation, pair_ref, interpretation))
