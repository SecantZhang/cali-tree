"""Exact all/any semantic simplification of reconstructed grading rules.

Each interpretation field assigns exactly one state per requested requirement.
Enumerating nonempty sets of present states proves per-field equivalence for
any positive requirement count, rather than assuming training-row equivalence.
"""
from copy import deepcopy

from ..decision.semantic_interpretation_v5 import FIELDS
from ..decision.artifacts import digest
from .semantic_rubric_v70 import Config, SemanticRubric
from .semantic_rubric_runtime_v70 import SemanticRubricExecutor

INDEX = {'meaning_' + field + '_' + state + '_' + q: (field, i, q)
         for field, states in FIELDS.items() for i, state in enumerate(states) for q in ('all', 'any')}


def domain(field, terms):
    selected = []
    for present in range(1, 1 << len(FIELDS[field])):
        matches = True
        for term in terms:
            _, state, quantifier = INDEX[term['feature']]
            value = present == (1 << state) if quantifier == 'all' else bool(present & (1 << state))
            matches &= value == term['value']
        if matches:
            selected.append(present)
    return selected


def simplify(artifact):
    SemanticRubricExecutor(artifact)
    value, proof = deepcopy(artifact), []
    for index, rule in enumerate(value['rules']):
        terms = rule['conditions']
        fields = sorted({INDEX[t['feature']][0] for t in terms if t['feature'] in INDEX})
        for field in fields:
            def own():
                return [t for t in terms if t['feature'] in INDEX and INDEX[t['feature']][0] == field]
            before = domain(field, own())
            if not before:
                raise ValueError('Contradictory semantic field states')
            # Prefer all-state witnesses when an any-state test is redundant.
            order = sorted(own(), key=lambda t: (INDEX[t['feature']][2] == 'any', t['feature']), reverse=True)
            for term in order:
                remaining = [t for t in own() if t is not term]
                after = domain(field, remaining)
                if before == after:
                    terms.remove(term)
                    proof.append({'rule_index': index, 'field': field, 'removed': term,
                                  'remaining': deepcopy(remaining), 'equivalent_nonempty_state_sets': before})
    value['feature_names'] = sorted({t['feature'] for r in value['rules'] for t in r['conditions']})
    renderer = SemanticRubric(value['feature_names'] or ['meaning_progress_none_all'], Config(**value['config']))
    renderer.rules = value['rules']
    value['rubric'] = renderer.render()
    value['artifact_ref'] = digest({k: v for k, v in value.items() if k != 'artifact_ref'})
    SemanticRubricExecutor(value)
    certificate = {'version': 'semantic-all-any-equivalence-v72', 'input_ref': artifact['artifact_ref'],
                   'output_ref': value['artifact_ref'], 'assumption': 'Validated nonempty requested requirements, one categorical state per interpretation field.',
                   'literals_before': sum(len(r['conditions']) for r in artifact['rules']),
                   'literals_after': sum(len(r['conditions']) for r in value['rules']), 'proof_steps': proof}
    return value, certificate
