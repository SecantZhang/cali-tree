"""Instruction-only task coverage and optional tree references for a visual judge.

Coverage means a supported task structure, not established visual correctness.
Training labels establish rule support offline; inference takes only instruction,
its compiled program, and source/edited images. It never traverses a tree using
the new example's observed outcome to decide whether to supply a reference.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

from ....decision.artifacts import digest
from ....decision.bound_evidence_v2 import validate_program, KINDS
from ....decision.compiler import media_inputs
from ....calibration.local_compression_v18 import gate as local_gate
from ....calibration.semantic_hierarchy.portable_features_v8 import SPECS
from ....calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

VERSION = 'task-coverage-reference-v19'
TEMPLATES = Path(__file__).parents[3] / 'prompts/templates/task_coverage_v19'
SCHEMA = {'type': 'object', 'properties': {'rationale': {'type': 'string'},
          'label': {'type': 'string', 'enum': ['no', 'partial', 'yes', 'unresolved']}},
          'required': ['rationale', 'label'], 'additionalProperties': False}
LABELS = ('no', 'partial', 'yes')


@dataclass(frozen=True)
class Config:
    min_sources: int = 2
    max_rules: int = 12
    max_reference_chars: int = 16000

    def __post_init__(self):
        if (any(type(v) is not int or v < 1 for v in (self.min_sources, self.max_rules, self.max_reference_chars))
                or self.min_sources < 2):
            raise ValueError('At least two sources and positive packet bounds required')


def task_scope(program):
    validate_program(program)
    # Only declared structural attributes, no names, instruction embeddings,
    # outcomes, source membership or reference labels enter the gate.
    return {'outcomes': [list(v) for v in sorted({(c['kind'], c['expected_state']) for c in program['checks'] if c['role'] == 'outcome'})],
            'identity_required': any(c['role'] == 'identity' for c in program['checks']),
            'compound': len(program['requirements']) > 1}


def _validate_scope(scope):
    if (set(scope) != {'outcomes', 'identity_required', 'compound'}
            or type(scope['identity_required']) is not bool or type(scope['compound']) is not bool
            or not scope['outcomes']):
        raise ValueError('Invalid task scope')
    values = [tuple(v) for v in scope['outcomes']]
    if values != sorted(set(values)) or any(len(v) != 2 or v[0] not in KINDS or v[1] not in ('true', 'false') for v in values):
        raise ValueError('Invalid outcome scope')


def _paths(tree, conditions=()):
    if 'feature' not in tree:
        yield list(conditions), tree['prediction']
    else:
        for key, value in (('true', True), ('false', False)):
            yield from _paths(tree[key], conditions + ({'feature': tree['feature'], 'value': value},))


def build(models, rows, programs, config=Config()):
    """Export task-scoped conditional rules with genuine correct-source support."""
    if len({r['source_group'] for r in rows}) != len(rows):
        raise ValueError('Distinct training sources required')
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Every training source needs its compiled instruction')
    scopes = {}
    for r in rows:
        p = programs[r['source_group']]
        if p['instruction'] != r['instruction']:
            raise ValueError('Compiled instruction mismatch')
        scopes[r['source_group']] = task_scope(p)
    entries = []
    for model in models:
        sources = set(model['policy']['training']['source_groups'])
        if not sources <= set(scopes):
            raise ValueError('Policy includes outside training sources')
        selected = sorted((r for r in rows if r['source_group'] in sources), key=lambda r: r['source_group'])
        check = local_gate(model, selected, [{'sources': sorted(sources), 'correct': 0}], max_rules=10000)
        if check['status'] != 'accepted':
            raise ValueError('Invalid source policy: ' + ','.join(check['reasons']))
        executor = PortableRuleExecutor(model['runtime'])
        predictions = executor.predict_records([r['features'] for r in selected])
        for conditions, label in _paths(model['runtime']['tree']):
            if not any(c['feature'] != 'meaning_available' and not c['feature'].startswith('requires_') for c in conditions):
                continue  # A task type alone cannot justify a satisfaction verdict.
            cohorts = {}
            for r, pred in zip(selected, predictions):
                if pred['prediction'] != label or pred['prediction'] != r['reference'] or pred['trace'] != conditions:
                    continue
                key = digest(scopes[r['source_group']]); cohorts.setdefault(key, []).append(r)
            for cohort in cohorts.values():
                if len(cohort) < config.min_sources or len({r['instruction'] for r in cohort}) < 2:
                    continue
                scope_ref = digest(scopes[cohort[0]['source_group']])
                # Coverage is fitted on the local pool, beyond the source tree's
                # original scope. Do not offer a rule with a known counterexample
                # under this same task structure. Missing evidence is not a match.
                applicable = [r for r in rows if digest(scopes[r['source_group']]) == scope_ref
                              and r['features'] is not None
                              and (not executor.requires_interpretation or r['features']['features']['meaning_available'])
                              and all(r['features']['features'][c['feature']] == c['value'] for c in conditions)]
                if any(r['reference'] != label for r in applicable):
                    continue
                rule = {'conditions': conditions, 'conclusion_if_all_established': LABELS[label]}
                entries.append({'policy_ref': model['runtime']['artifact_ref'], 'rule_ref': digest(rule),
                                'scope': scopes[cohort[0]['source_group']], 'rule': rule,
                                'support': {'correct_sources': len(cohort),
                                            'distinct_instructions': len({r['instruction'] for r in cohort}),
                                            'batches': len({r['batch'] for r in cohort})}})
    unique = {digest(e): e for e in entries}
    artifact = {'version': VERSION, 'config': vars(config),
                'predicate_contract_ref': digest(SPECS), 'entries': [unique[k] for k in sorted(unique)]}
    artifact['artifact_ref'] = digest(artifact)
    return TaskCoverageGate(artifact)


class TaskCoverageGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'config', 'predicate_contract_ref', 'entries', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['predicate_contract_ref'] != digest(SPECS)
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Changed task coverage artifact')
        self.config = Config(**artifact['config'])
        for entry in artifact['entries']:
            if set(entry) != {'policy_ref', 'rule_ref', 'scope', 'rule', 'support'}:
                raise ValueError('Unexpected reference metadata')
            _validate_scope(entry['scope'])
            rule = entry['rule']; support = entry['support']
            if (set(rule) != {'conditions', 'conclusion_if_all_established'}
                    or entry['rule_ref'] != digest(rule) or rule['conclusion_if_all_established'] not in LABELS
                    or not rule['conditions'] or set(support) != {'correct_sources', 'distinct_instructions', 'batches'}
                    or any(type(v) is not int or v < 1 for v in support.values())
                    or support['correct_sources'] < self.config.min_sources
                    or not 2 <= support['distinct_instructions'] <= support['correct_sources']
                    or support['batches'] > support['correct_sources']):
                raise ValueError('Invalid conditional rule or support')
            for c in rule['conditions']:
                if set(c) != {'feature', 'value'} or c['feature'] not in SPECS or type(c['value']) is not bool:
                    raise ValueError('Undeclared rule predicate')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def select(self, instruction, program):
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError('A nonempty instruction is required')
        result = {'covered': False, 'reason': 'missing_or_invalid_compilation', 'reference': None}
        if program is None:
            return result
        try:
            scope = task_scope(program)
        except (ValueError, KeyError, TypeError):
            return result
        if program['instruction'] != instruction:
            return {**result, 'reason': 'instruction_program_mismatch'}
        candidates = {}
        for e in self.artifact['entries']:
            if digest(e['scope']) == digest(scope):
                candidates.setdefault(e['policy_ref'], []).append(e)
        ranked = []
        for policy_ref, entries in candidates.items():
            entries = sorted(entries, key=lambda e: e['rule_ref'])
            packet = {'task_scope': scope, 'rules': [e['rule'] for e in entries],
                      'predicate_meanings': {c['feature']: SPECS[c['feature']] for e in entries for c in e['rule']['conditions']}}
            if len(entries) > self.config.max_rules or len(json.dumps(packet, sort_keys=True)) > self.config.max_reference_chars:
                continue  # Do not truncate conditions and accidentally broaden a rule.
            rank = (-sum(e['support']['correct_sources'] for e in entries),
                    -sum(e['support']['batches'] >= 2 for e in entries), len(entries), policy_ref)
            ranked.append((rank, policy_ref, entries, packet))
        if not ranked:
            return {**result, 'reason': 'no_supported_task_scope' if not candidates else 'reference_budget_exceeded'}
        _, policy_ref, entries, packet = min(ranked, key=lambda r: r[0])
        return {'covered': True, 'reason': 'supported_task_scope', 'reference': packet,
                'policy_ref': policy_ref, 'rule_refs': [e['rule_ref'] for e in entries],
                'coverage_ref': self.artifact['artifact_ref']}


class TaskCoveredJudge:
    """Same regular visual judge, with an optional instruction-scoped reference."""
    def __init__(self, calls, gate, *, regular_prompt=None, compiler=None):
        self.calls, self.gate, self.compiler = calls, gate, compiler
        self.regular_prompt = regular_prompt if regular_prompt is not None else (TEMPLATES / 'regular.txt').read_text()

    def request(self, instruction, program=None):
        route = self.gate.select(instruction, program)
        payload = {'instruction': instruction}; template = self.regular_prompt
        if route['covered']:
            payload['tree_reference'] = route['reference']
            template += '\n\n' + (TEMPLATES / 'reference.txt').read_text()
        return {'stage': 'tree_reference_judge' if route['covered'] else 'flat_judge',
                'payload': payload, 'template': template, 'schema': deepcopy(SCHEMA), 'route': route}

    def judge(self, instruction, evidence, *, program=None, case_id=None, max_tokens=2048):
        compiler_error = None
        if program is None and self.compiler is not None:
            try:
                program = self.compiler.compile(instruction, case_id=case_id)['program']
            except (ValueError, RuntimeError) as error:
                compiler_error = type(error).__name__
        request = self.request(instruction, program)
        value, ref = self.calls.call(request['stage'], request['payload'], request['schema'],
                                     template=request['template'], media=media_inputs(evidence),
                                     case_id=case_id, slot='once', max_tokens=max_tokens)
        if (set(value) != {'rationale', 'label'} or value['label'] not in (*LABELS, 'unresolved')
                or not isinstance(value['rationale'], str) or not value['rationale'].strip()):
            raise ValueError('Invalid judge response')
        return {'judgment': value, 'execution_ref': ref, 'route': request['route'],
                'compiler_error': compiler_error}
