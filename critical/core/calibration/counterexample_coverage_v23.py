"""Monotone rejection of known unsupported evidence combinations.

Fit short Boolean support clauses that retain every protected correct route and
reject reviewed false acceptances. Calibration examples are development data;
runtime artifacts contain predicates only, never case/image identifiers or labels.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as features
from .evidence_support_v21 import SupportedCoverageGate

VERSION = 'counterexample-coverage-v23'
CONTRACT_REF = digest({'version': VERSION, 'features': features.CONTRACT_REF,
                       'semantics': 'All support clauses must pass; each clause is OR over declared Boolean literals. Only reject existing acceptances.'})


@dataclass(frozen=True)
class Config:
    max_literals: int = 3
    max_states_per_example: int = 20000
    max_clauses: int = 64
    max_examples: int = 256

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ValueError('Positive integer rejection limits required')


def _example_values(example):
    if type(example.get('reference')) is not int or example['reference'] not in (0, 1, 2):
        raise ValueError('A valid calibration reference is required')
    values = features.feature_values(example['program'], example['features'])
    if values is None:
        raise ValueError('Calibration requires complete existing evidence')
    return values


def clause_passes(clause, values):
    return any(values[c['feature']] == c['value'] for c in clause)


class _SearchLimit(Exception):
    pass


def fit(gate, protected, counterexamples, config=Config()):
    """Keep every protected prediction; use reviewed errors only for rejection.

    Clauses are selected under a bounded search. Failure to separate an error
    from protected observations fails explicitly rather than introducing an ID
    exception, changing a verdict or silently sacrificing local coverage.
    """
    if not protected or len(protected) + len(counterexamples) > config.max_examples:
        raise ValueError('A protected calibration pool within the declared size is required')
    positive = [(_example_values(e), e) for e in protected]
    negative = [(_example_values(e), e) for e in counterexamples]
    positive.sort(key=lambda item: digest(item[0])); negative.sort(key=lambda item: digest(item[0]))
    for expected_correct, collection in ((True, positive), (False, negative)):
        for _, example in collection:
            route = gate.select(example['program'], example['features'])
            if not route['covered'] or (route['prediction'] == example['reference']) != expected_correct:
                raise ValueError('Calibration groups must be existing correct acceptances and false acceptances')
    full = (1 << len(positive)) - 1; candidates = {}; searches = []
    for values, example in negative:
        options = {}
        for name in sorted(features.FEATURES, key=lambda k: (not k.startswith('meaning_'), not k.startswith('task_'), k)):
            value = not values[name]
            mask = sum(1 << i for i, (p, _) in enumerate(positive) if p[name] == value)
            if mask:
                options.setdefault(mask, {'feature': name, 'value': value})
        if any(values == p for p, _ in positive):
            raise ValueError('Counterexample is indistinguishable from a protected input under the declared features')
        visited = 0

        @lru_cache(None)
        def solve(remaining, depth):
            nonlocal visited
            if not remaining:
                return ()
            if depth == 0:
                return None
            if visited >= config.max_states_per_example:
                raise _SearchLimit
            visited += 1
            bits = [1 << i for i in range(len(positive)) if remaining >> i & 1]
            pivot = min(bits, key=lambda bit: (sum(bool(m & bit) for m in options), digest(positive[bit.bit_length()-1][0])))
            ordered = sorted((m for m in options if m & pivot),
                             key=lambda m: (-(m & remaining).bit_count(), options[m]['feature'], options[m]['value']))
            best = None
            for mask in ordered:
                tail = solve(remaining & ~mask, depth - 1)
                if tail is not None:
                    candidate = (mask,) + tail
                    if best is None or len(candidate) < len(best):
                        best = candidate
                    if len(best) == 1:
                        break
            return best

        try:
            solution = solve(full, config.max_literals)
        except _SearchLimit as error:
            raise ValueError('Rejection search budget exhausted; keep the previous gate') from error
        if solution is None:
            raise ValueError('Cannot reject every requested error within the declared clause-size bound')
        clause = sorted((options[m] for m in solution), key=lambda c: (c['feature'], c['value']))
        if not all(clause_passes(clause, p) for p, _ in positive) or clause_passes(clause, values):
            raise AssertionError('Support clause violated calibration constraints')
        rejected = sum(1 << i for i, (n, _) in enumerate(negative) if not clause_passes(clause, n))
        candidates[digest(clause)] = (clause, rejected)
        searches.append({'case': example.get('case'), 'states': visited, 'clause_ref': digest(clause), 'literals': len(clause)})
    remaining = (1 << len(negative)) - 1; selected = []
    while remaining:
        if len(selected) >= config.max_clauses:
            raise ValueError('Rejection clause budget exhausted; keep the previous gate')
        clause, rejected = min((v for v in candidates.values() if v[1] & remaining),
                               key=lambda v: (-(v[1] & remaining).bit_count(), len(v[0]), digest(v[0])))
        selected.append(clause); remaining &= ~rejected
    # Remove redundant clauses without losing any requested rejection.
    for clause in list(reversed(selected)):
        others = [c for c in selected if c != clause]
        if all(any(not clause_passes(c, n) for c in others) for n, _ in negative):
            selected.remove(clause)
    selected.sort(key=digest)
    artifact = {'version': VERSION, 'contract_ref': CONTRACT_REF, 'config': asdict(config),
                'previous_gate': gate.export(), 'support_clauses': selected,
                'calibration_counts': {'protected': len(positive), 'reviewed_errors': len(negative)},
                'scope': 'Counterexample-calibrated rejection; known transfer outcomes are development data, not an independent validation set.'}
    artifact['artifact_ref'] = digest(artifact)
    result = RejectionCoverageGate(artifact)
    for _, example in positive:
        before = gate.select(example['program'], example['features'])
        after = result.select(example['program'], example['features'])
        if not after['covered'] or after['prediction'] != before['prediction']:
            raise AssertionError('Rejection calibration lost a protected correct prediction')
    for _, example in negative:
        if result.select(example['program'], example['features'])['covered']:
            raise AssertionError('A requested counterexample remains accepted')
    return result, {'version': VERSION, 'config': asdict(config), 'protected': len(positive), 'rejected_errors': len(negative),
                    'clauses': len(selected), 'literal_tests': sum(map(len, selected)), 'searches': searches,
                    'global_optimality_claim': False, 'new_model_calls': 0}


class RejectionCoverageGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'contract_ref', 'config', 'previous_gate', 'support_clauses', 'calibration_counts', 'scope', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['contract_ref'] != CONTRACT_REF
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Changed rejection coverage contract')
        config = Config(**artifact['config']); self.previous = SupportedCoverageGate(artifact['previous_gate'])
        if len(artifact['support_clauses']) > config.max_clauses:
            raise ValueError('Too many support clauses')
        for clause in artifact['support_clauses']:
            if not 1 <= len(clause) <= config.max_literals or len({c['feature'] for c in clause}) != len(clause):
                raise ValueError('Invalid support-clause size or repeated predicate')
            for c in clause:
                if set(c) != {'feature', 'value'} or c['feature'] not in features.FEATURES or type(c['value']) is not bool:
                    raise ValueError('Undeclared rejection predicate')
        counts = artifact['calibration_counts']
        if (set(counts) != {'protected', 'reviewed_errors'} or any(type(v) is not int or v < 0 for v in counts.values())
                or not counts['protected'] or sum(counts.values()) > config.max_examples):
            raise ValueError('Invalid calibration counts')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def accepts_task(self, program):
        return self.previous.accepts_task(program)

    def select(self, program, record):
        route = self.previous.select(program, record)
        if not route['covered']:
            return route
        values = features.feature_values(program, record)
        violations = [digest(c) for c in self.artifact['support_clauses'] if not clause_passes(c, values)]
        if violations:
            return {'covered': False, 'prediction': -1, 'reason': 'unsupported_feature_combination',
                    'matches': [], 'violated_support_clauses': violations}
        return route

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, features.project(program, observation, pair_ref, interpretation))
