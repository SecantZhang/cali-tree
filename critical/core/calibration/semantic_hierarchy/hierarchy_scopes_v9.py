"""Instruction-only, reusable applicability scopes for portable M2 policies.

No operation-signature lookup or training membership is available to routing.
Outcome states and semantic interpretations are deliberately absent here.
"""
from itertools import combinations, product

from ...decision.artifacts import digest
from ...decision.bound_evidence_v2 import validate_program
from .portable_features_v8 import OPERATIONS

VERSION = 'portable-instruction-scopes-v9'
FLAGS = tuple('requires_' + k for k in OPERATIONS) + (
    'requires_identity_binding', 'has_outcome_dependency', 'combines_operation_kinds')
CONTRACT_REF = digest({'version': VERSION, 'flags': FLAGS,
    'inputs': 'Compiled instruction only; no observations, interpretations, labels, IDs, or signature table.',
    'grammar': 'OR of ANDs, at most two distinct Boolean flags per conjunction.'})


def project(program):
    if program is None:
        return None
    validate_program(program)
    outcomes = [c for c in program['checks'] if c['role'] == 'outcome']
    kinds = {c['kind'] for c in outcomes}
    values = {'requires_' + k: k in kinds for k in OPERATIONS}
    values.update(requires_identity_binding=any(c['role'] == 'identity' for c in program['checks']),
                  has_outcome_dependency=any(c['dependencies'] for c in outcomes),
                  combines_operation_kinds=len(kinds) > 1)
    validate_values(values)
    return values


def validate_values(values):
    if values is not None and (not isinstance(values, dict) or set(values) != set(FLAGS)
                               or any(type(v) is not bool for v in values.values())):
        raise ValueError('Routing accepts only declared instruction-derived Booleans')


def validate_scope(scope):
    if not isinstance(scope, list) or not scope:
        raise ValueError('A scope is a nonempty union of instruction conjunctions')
    seen = set()
    for clause in scope:
        if not isinstance(clause, list) or not 1 <= len(clause) <= 2:
            raise ValueError('Instruction scopes require one or two tests per clause')
        names = []
        for c in clause:
            if (not isinstance(c, dict) or set(c) != {'flag', 'value'} or c['flag'] not in FLAGS
                    or type(c['value']) is not bool):
                raise ValueError('A scope contains an inference-prohibited field')
            names.append(c['flag'])
        if len(set(names)) != len(names) or digest(clause) in seen:
            raise ValueError('Duplicate or contradictory scope tests')
        seen.add(digest(clause))


def matches(values, scope):
    validate_values(values)
    validate_scope(scope)
    return values is not None and any(all(values[c['flag']] == c['value'] for c in clause) for clause in scope)


def union(scopes):
    clauses = {digest(c): c for scope in scopes for c in scope}
    result = sorted(clauses.values(), key=lambda c: (len(c), digest(c)))
    # Remove conjunctions already covered by a less restrictive conjunction.
    result = [c for c in result if not any(len(a) < len(c) and all(x in c for x in a) for a in result)]
    validate_scope(result)
    return result


def proposals(values):
    """All bounded conjunctions, deduplicated by instruction coverage only."""
    for v in values:
        validate_values(v)
    seen = set()
    for size in (1, 2):
        for flags in combinations(FLAGS, size):
            for states in product((True, False), repeat=size):
                scope = [[{'flag': k, 'value': v} for k, v in zip(flags, states)]]
                covered = tuple(i for i, v in enumerate(values) if matches(v, scope))
                if covered and covered not in seen:
                    seen.add(covered)
                    yield scope, covered

