"""Paired execution of identical visual criteria, combined or independently checked."""
from copy import deepcopy
from itertools import combinations, product
from pathlib import Path
import re

from .artifacts import digest
from .calls import CallFailure
from .compiler import object_schema, array, enum, TEXT, media_inputs
from .models import STATES

VERSION = 'visual-check-ablation-v1'
TEMPLATES = Path(__file__).parents[1] / 'prompts/templates/decision_ablation_v1'
FACT_STATES = ('present', 'absent', 'unknown')
FACT_SCHEMA = object_schema({k: TEXT for k in ('id', 'question', 'present_when', 'absent_when', 'unknown_when')})
DECISION_SCHEMA = object_schema({'outcome_id': TEXT, 'fact_ids': array(TEXT),
    **{k: TEXT for k in ('complete_when', 'partial_when', 'absent_when', 'unknown_when')}})
BANK_SCHEMA = object_schema({'representable': {'type': 'boolean'}, 'reason': TEXT,
                            'facts': array(FACT_SCHEMA), 'decisions': array(DECISION_SCHEMA)})
AUDIT_SCHEMA = object_schema({'accepted': {'type': 'boolean'}, 'reason': TEXT})
FACT_OBSERVATION = object_schema({'status': enum(FACT_STATES), 'evidence': TEXT})
OUTCOME_OBSERVATION = object_schema({'status': enum(STATES), 'evidence': TEXT})


def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()


def validate_shape(value, schema, path='response'):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError(f'{path}: unexpected or missing fields')
        for key, child in schema['properties'].items():
            validate_shape(value[key], child, path + '.' + key)
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError(f'{path}: expected array')
        for item in value:
            validate_shape(item, schema['items'], path + '[]')
    elif kind == 'boolean':
        if type(value) is not bool:
            raise ValueError(f'{path}: expected boolean')
    elif kind == 'string':
        # Explanatory metadata may be empty; executable criteria and evidence may not.
        if not isinstance(value, str) or (not value.strip() and not path.endswith('.reason')) or ('enum' in schema and value not in schema['enum']):
            raise ValueError(f'{path}: invalid string')
    else:
        raise ValueError(f'Unsupported schema type {kind}')


def make_bank(seed, graph):
    validate_shape(graph, BANK_SCHEMA)
    if not graph['representable']:
        raise ValueError('Unrepresentable within fact cap: ' + graph['reason'])
    facts, decisions = graph['facts'], graph['decisions']
    ids = [f['id'] for f in facts]
    if not 2 <= len(ids) <= 3 or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', i) for i in ids):
        raise ValueError('Need two or three uniquely identified atomic facts')
    outcome_ids = [d['outcome_id'] for d in decisions]
    if len(set(outcome_ids)) != len(outcome_ids) or set(outcome_ids) != {o.id for o in seed.outcomes}:
        raise ValueError('Every original outcome must be covered exactly once')
    used = set()
    for decision in decisions:
        deps = decision['fact_ids']
        if not deps or len(set(deps)) != len(deps) or not set(deps) <= set(ids):
            raise ValueError('Broken or duplicate fact references')
        used.update(deps)
    if used != set(ids):
        raise ValueError('Unused visual facts')
    return {'version': VERSION, 'instruction': seed.instruction, 'rubric': seed.rubric,
            'outcomes': deepcopy(seed.to_dict()['outcomes']), **deepcopy(graph)}


def prepare(calls, seed, evidence):
    """One label-blind compilation and audit; never repair based on final labels."""
    record = {'status': 'unresolved', 'bank': None, 'audit': None}
    try:
        graph, ref = calls.call('compile', {'seed': seed.to_dict(), 'max_facts': 3}, BANK_SCHEMA,
            template=template('compile'), media=media_inputs(evidence), slot='compile', max_tokens=2048)
        record.update(compilation=graph, compilation_ref=ref)
        bank = make_bank(seed, graph)
        record.update(bank=bank, bank_ref=digest(bank))
        audit, ref = calls.call('audit', {'seed': seed.to_dict(), 'bank': bank}, AUDIT_SCHEMA,
            template=template('audit'), media=media_inputs(evidence), slot='audit', max_tokens=2048)
        validate_shape(audit, AUDIT_SCHEMA)
        record['audit'] = {**audit, 'execution_ref': ref}
        record['status'] = 'ready' if audit['accepted'] else 'audit_rejected'
    except (CallFailure, ValueError, TypeError, KeyError) as exc:
        record['error'] = str(exc)
    return record


def response_schemas(bank):
    facts = object_schema({f['id']: FACT_OBSERVATION for f in bank['facts']})
    outcomes = object_schema({o['id']: OUTCOME_OBSERVATION for o in bank['outcomes']})
    return object_schema({'facts': facts, 'outcomes': outcomes}), object_schema({'outcomes': outcomes})


def aggregate_observations(bank, facts, outcomes):
    states = []
    decisions = {d['outcome_id']: d for d in bank['decisions']}
    for outcome in bank['outcomes']:
        if outcome['applicability'] == 'not_applicable':
            continue
        if outcome['applicability'] != 'applicable':
            return None
        dependencies = decisions[outcome['id']]['fact_ids']
        if any(facts[key]['status'] == 'unknown' for key in dependencies):
            return None
        state = outcomes[outcome['id']]['status']
        if state == 'unknown':
            return None
        states.append(state)
    if not states:
        return None
    return 'yes' if all(s == 'complete' for s in states) else 'no' if all(s == 'absent' for s in states) else 'partial'


def execute_draw(calls, bank, evidence, arm, repeat):
    if arm not in ('combined', 'separated'):
        raise ValueError('Unknown execution arm')
    row = {'bank_ref': digest(bank), 'arm': arm, 'repeat': repeat, 'facts': {}, 'outcomes': {},
           'label': None, 'errors': [], 'execution_refs': []}
    combined_schema, fulfillment_schema = response_schemas(bank)
    def invoke(stage, payload, schema, media, slot):
        try:
            value, ref = calls.call(stage, payload, schema, template=template(stage), media=media,
                                    slot=slot, final=True, max_tokens=1024)
            row['execution_refs'].append(ref)
            validate_shape(value, schema)
            return value
        except (CallFailure, ValueError, KeyError, TypeError) as exc:
            row['errors'].append(str(exc))
            return None
    unknown = lambda: {'status': 'unknown', 'evidence': 'No valid observation'}
    if arm == 'combined':
        value = invoke('combined', {'bank': bank}, combined_schema, media_inputs(evidence), str(repeat))
        if value:
            row.update(value)
    else:
        for fact in bank['facts']:
            value = invoke('atomic', {'instruction': bank['instruction'], 'rubric': bank['rubric'], 'fact': fact},
                FACT_OBSERVATION, media_inputs(evidence), f'{repeat}/{fact["id"]}')
            row['facts'][fact['id']] = value or unknown()
        # Keep the same scheduled fulfillment call even with missing facts; the guard below propagates unknowns.
        value = invoke('fulfillment', {'bank': bank, 'facts': row['facts']}, fulfillment_schema, [], str(repeat))
        if value:
            row['outcomes'] = value['outcomes']
    for fact in bank['facts']:
        row['facts'].setdefault(fact['id'], unknown())
    for outcome in bank['outcomes']:
        row['outcomes'].setdefault(outcome['id'], unknown())
    row['label'] = aggregate_observations(bank, row['facts'], row['outcomes'])
    return row


def inconsistency(values, unknown=None):
    pairs = list(combinations(values, 2))
    return sum(a == unknown or b == unknown or a != b for a, b in pairs) / len(pairs) if pairs else None


def draw_metrics(draws, target):
    labels = [d['label'] for d in draws]
    known = [label for label in labels if label is not None]
    pairs = list(combinations(known, 2))
    facts = sorted({key for d in draws for key in d['facts']})
    atomic = [inconsistency([d['facts'].get(key, {'status': 'unknown'})['status'] for d in draws], 'unknown') for key in facts]
    return {'independent_cases': 1, 'repeats': len(draws), 'agreement': sum(label == target for label in labels) / len(draws),
            'coverage': len(known) / len(draws), 'all_matching': all(label == target for label in labels),
            'all_resolved_consistent': len(known) == len(labels) and len(set(known)) == 1,
            'pairwise_inconsistency': inconsistency(labels),
            'resolved_pairwise_disagreement': sum(a != b for a, b in pairs) / len(pairs) if pairs else None,
            'atomic_inconsistency': sum(atomic) / len(atomic) if atomic else None,
            'transport_or_schema_failed_draws': sum(bool(d['errors']) for d in draws)}


def paired_sign_flip(differences):
    """Exact, two-sided, case-level paired randomization diagnostic."""
    if not differences:
        return {'cases': 0, 'mean_difference': None, 'p_value': None}
    observed = abs(sum(differences))
    extreme = sum(abs(sum(sign * value for sign, value in zip(signs, differences))) >= observed - 1e-12
                  for signs in product((-1, 1), repeat=len(differences)))
    return {'cases': len(differences), 'mean_difference': sum(differences) / len(differences),
            'p_value': extreme / (2 ** len(differences))}
