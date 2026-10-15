"""Exact-question, label-blind physical evidence for semantic calibration.

Hashes guarantee program/pair identity, not visual truth. Physical claims still
need image auditing. This version is separate from the frozen v16 representation.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re

from .artifacts import digest
from .compiler import TEXT, array, enum, media_inputs, object_schema

VERSION = 'bound-physical-evidence-v1'
TEMPLATES = Path(__file__).parents[1] / 'prompts/templates/bound_evidence_v1'
MAX_CHECKS = 16
STATES = ('true', 'false', 'unknown', 'not_applicable')
ROLES = ('outcome', 'identity', 'intermediate', 'collateral_disappearance', 'collateral_deformation')
KINDS = ('presence', 'absence', 'attribute', 'spatial_relation', 'identity', 'pose',
         'contact', 'grasp', 'material_transfer', 'orientation', 'closure', 'separation',
         'count', 'style', 'background', 'other_physical')
CHECK = object_schema({
    'id': TEXT, 'requirement_ids': array(TEXT), 'role': enum(ROLES), 'kind': enum(KINDS),
    'question': TEXT, 'source_quote': TEXT, 'target': TEXT, 'reference': TEXT,
    'applicability_condition': TEXT, 'expected_state': enum(('true', 'false')),
    'dependencies': array(TEXT),
})
REQUIREMENT = object_schema({'id': TEXT, 'source_quote': TEXT, 'description': TEXT, 'check_ids': array(TEXT)})
CONTRACT = object_schema({'authorized_changes': array(TEXT), 'preservation_scope': TEXT})
COMPILER_SCHEMA = object_schema({
    'contract': CONTRACT,
    'requirements': {**array(REQUIREMENT), 'minItems': 1, 'maxItems': 6},
    'checks': {**array(CHECK), 'minItems': 3, 'maxItems': MAX_CHECKS},
})


class EvidenceContractError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(code + ': ' + message)


def fail(code, message):
    raise EvidenceContractError(code, message)


def _fields(value, expected, code):
    if not isinstance(value, dict) or set(value) != set(expected):
        fail(code, 'Unexpected or missing fields')


def _strings(values, *, nonempty=False):
    return (isinstance(values, list) and (not nonempty or bool(values)) and
            all(isinstance(v, str) and v.strip() for v in values) and len(set(values)) == len(values))


def validate_draft(value, instruction):
    if not isinstance(instruction, str) or not instruction.strip():
        fail('instruction_missing', 'A nonempty instruction is required')
    _fields(value, COMPILER_SCHEMA['properties'], 'program_fields')
    _fields(value['contract'], CONTRACT['properties'], 'contract_fields')
    if not _strings(value['contract']['authorized_changes'], nonempty=True) or not isinstance(value['contract']['preservation_scope'], str) or not value['contract']['preservation_scope'].strip():
        fail('invalid_contract', 'Authorized changes and preservation scope are required')
    requirements, checks = value['requirements'], value['checks']
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 6 or not isinstance(checks, list) or not 3 <= len(checks) <= MAX_CHECKS:
        fail('program_size', 'One to six requirements and three to sixteen checks required')
    for r in requirements:
        _fields(r, REQUIREMENT['properties'], 'requirement_fields')
        if any(not isinstance(r[k], str) or not r[k].strip() for k in ('id', 'source_quote', 'description')) or not _strings(r['check_ids'], nonempty=True):
            fail('invalid_requirement', 'A requirement must contain concrete checks')
        if r['source_quote'] not in instruction:
            fail('quote_mismatch', 'Requirement anchor is not an exact instruction span')
    for c in checks:
        _fields(c, CHECK['properties'], 'check_fields')
        if any(not isinstance(c[k], str) or not c[k].strip() for k in ('id', 'question', 'source_quote', 'target', 'reference', 'applicability_condition')):
            fail('invalid_check', 'Physical question and explicit bindings are required')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', c['id']):
            fail('invalid_check_id', 'Use a short lowercase identifier')
        if c['role'] not in ROLES or c['kind'] not in KINDS or c['expected_state'] not in ('true', 'false'):
            fail('invalid_check_type', 'Unknown role, physical kind, or desired polarity')
        if not _strings(c['requirement_ids'], nonempty=True) or not _strings(c['dependencies']):
            fail('invalid_links', 'Distinct linked requirement and dependency IDs required')
        if c['source_quote'] not in instruction:
            fail('quote_mismatch', 'Check anchor is not an exact instruction span')
        if c['role'] in ('identity', 'intermediate') and c['expected_state'] != 'true':
            fail('invalid_polarity', 'Identity and intermediate checks assert a positive witness')
        if c['role'].startswith('collateral_') and c['expected_state'] != 'false':
            fail('invalid_polarity', 'Collateral questions ask whether an unauthorized change occurred')
    req = {r['id']: r for r in requirements}; by_id = {c['id']: c for c in checks}
    if len(req) != len(requirements) or len(by_id) != len(checks):
        fail('duplicate_id', 'Requirement/check IDs must be unique')
    for c in checks:
        if not set(c['requirement_ids']) <= set(req) or not set(c['dependencies']) <= set(by_id) or c['id'] in c['dependencies']:
            fail('dangling_link', 'Unknown requirement/dependency or self dependency')
        if any(by_id[d]['role'] not in ('outcome', 'identity') for d in c['dependencies']):
            fail('invalid_dependency', 'Dependencies must refer to physical outcome or identity checks')
    for r in requirements:
        if not set(r['check_ids']) <= set(by_id):
            fail('dangling_link', 'Unknown required check')
        if not any(by_id[k]['role'] == 'outcome' for k in r['check_ids']):
            fail('vacuous_requirement', 'Each requirement needs an outcome check')
        for k in r['check_ids']:
            if by_id[k]['role'] not in ('outcome', 'identity') or r['id'] not in by_id[k]['requirement_ids']:
                fail('inconsistent_requirement', 'Required checks must have matching outcome/identity links')
    for c in checks:
        if c['role'] in ('outcome', 'identity') and any(c['id'] not in req[r]['check_ids'] for r in c['requirement_ids']):
            fail('orphan_required_check', 'Outcome/identity checks cannot escape their requirements')
    roles = {c['role'] for c in checks}
    if not {'collateral_disappearance', 'collateral_deformation'} <= roles:
        fail('missing_preservation_channels', 'Keep disappearance and deformation separately available')
    visited, active = set(), set()
    def visit(k):
        if k in active:
            fail('dependency_cycle', 'Dependency graph must be acyclic')
        if k in visited:
            return
        active.add(k)
        for d in by_id[k]['dependencies']:
            visit(d)
        active.remove(k); visited.add(k)
    for k in by_id:
        visit(k)
    return value


def bind_program(instruction, draft):
    validate_draft(draft, instruction)
    value = {'version': VERSION, 'instruction': instruction, **deepcopy(draft)}
    context = [VERSION, instruction, value['contract'], value['requirements']]
    value['checks'] = [{**c, 'check_ref': digest([context, c])} for c in value['checks']]
    return {**value, 'program_ref': digest(value)}


def validate_program(program):
    _fields(program, ('version', 'instruction', 'contract', 'requirements', 'checks', 'program_ref'), 'bound_program_fields')
    if program['version'] != VERSION or not isinstance(program['checks'], list):
        fail('program_version', 'Unsupported bound evidence version')
    for c in program['checks']:
        _fields(c, (*CHECK['properties'], 'check_ref'), 'bound_check_fields')
    draft = {k: deepcopy(program[k]) for k in ('contract', 'requirements', 'checks')}
    for c in draft['checks']:
        c.pop('check_ref')
    expected = bind_program(program['instruction'], draft)
    if expected != program:
        fail('program_hash_mismatch', 'Question, binding, role, dependency, or program reference changed')
    return program


def image_identity(evidence):
    _fields(evidence, ('source_image', 'edited_image'), 'image_fields')
    hashes = {k: sha256(Path(v).read_bytes()).hexdigest() for k, v in evidence.items()}
    return hashes, digest([VERSION, 'source_first', hashes['source_image'], hashes['edited_image']])


def observation_schema(program, pair_ref):
    validate_program(program)
    fields = {}
    for c in program['checks']:
        fields[c['id']] = object_schema({
            'check_ref': enum((c['check_ref'],)), 'question': enum((c['question'],)),
            'state': enum(STATES), 'applicability': enum(('applicable', 'not_applicable', 'unknown')),
            'source_anchor': enum(('identified', 'ambiguous', 'not_found', 'not_needed')),
            'edited_coverage': enum(('adequate', 'occluded', 'cropped', 'unclear', 'not_needed')),
            'source_evidence': TEXT, 'edited_evidence': TEXT, 'comparison': TEXT,
        })
    return object_schema({'program_ref': enum((program['program_ref'],)),
                          'image_pair_ref': enum((pair_ref,)), 'checks': object_schema(fields)})


def validate_observation(program, value, pair_ref):
    schema = observation_schema(program, pair_ref)
    _fields(value, schema['properties'], 'observation_fields')
    if value['program_ref'] != program['program_ref'] or value['image_pair_ref'] != pair_ref:
        fail('observation_binding_mismatch', 'Observation belongs to another program or ordered image pair')
    _fields(value['checks'], schema['properties']['checks']['properties'], 'observation_check_set')
    for c in program['checks']:
        row = value['checks'][c['id']]
        fields = schema['properties']['checks']['properties'][c['id']]['properties']
        _fields(row, fields, 'observation_check_fields')
        for k, spec in fields.items():
            if 'enum' in spec and row[k] not in spec['enum']:
                fail('check_binding_mismatch' if k in ('check_ref', 'question') else 'invalid_observation_state', k)
            if not isinstance(row[k], str) or not row[k].strip():
                fail('missing_evidence_text', k)
    return value


def effective_state(check, observation):
    state, issues = observation['state'], []
    if observation['applicability'] == 'unknown':
        state = 'unknown'; issues.append('applicability_unknown')
    elif observation['applicability'] == 'not_applicable' or state == 'not_applicable':
        if check['role'] in ('outcome', 'identity'):
            state = 'unknown'; issues.append('required_check_not_applicable')
        else:
            state = 'not_applicable'
    # A target cannot be declared removed merely because its source binding is
    # unclear or the edited image does not expose the relevant region.
    absence_asserted = (check['kind'] == 'absence' and state == 'true') or (check['kind'] == 'presence' and state == 'false')
    if check['role'] in ('outcome', 'identity') and absence_asserted:
        if observation['source_anchor'] != 'identified':
            state = 'unknown'; issues.append('absence_source_unanchored')
        if observation['edited_coverage'] != 'adequate':
            state = 'unknown'; issues.append('absence_view_inadequate')
    return state, issues


def tri_all(values):
    values = list(values)
    if not values:
        return 'not_applicable'
    if 'false' in values:
        return 'false'
    return 'true' if all(v == 'true' for v in values) else 'unknown'


def tri_any(values):
    values = list(values)
    if not values:
        return 'not_applicable'
    if 'true' in values:
        return 'true'
    return 'false' if all(v == 'false' for v in values) else 'unknown'


def desired_state(state, expected):
    return state if state in ('unknown', 'not_applicable') else ('true' if state == expected else 'false')


def derive_record(program, value, pair_ref):
    validate_observation(program, value, pair_ref)
    checks = {}; diagnostics = []
    for c in program['checks']:
        state, issues = effective_state(c, value['checks'][c['id']])
        checks[c['id']] = {**deepcopy(c), 'asserted_state': value['checks'][c['id']]['state'],
                           'state': state, 'desired_state': desired_state(state, c['expected_state']),
                           'observation': deepcopy(value['checks'][c['id']]), 'diagnostics': issues}
        diagnostics.extend({'check_id': c['id'], 'code': issue} for issue in issues)
    memo = {}
    def fulfilled(k):
        if k not in memo:
            c = checks[k]
            memo[k] = tri_all([c['desired_state'], *(fulfilled(d) for d in c['dependencies'])])
        return memo[k]
    requirements = [{**r, 'state': tri_all(fulfilled(k) for k in r['check_ids'])} for r in program['requirements']]
    primary = [c for c in checks.values() if c['role'] == 'outcome']
    intermediates = [c for c in checks.values() if c['role'] == 'intermediate' and c['state'] != 'not_applicable']
    conflicts = lambda role: tri_any(c['state'] for c in checks.values() if c['role'] == role and c['state'] != 'not_applicable')
    features = {'all_requirements_satisfied': tri_all(r['state'] for r in requirements),
                'some_requirement_satisfied': tri_any(r['state'] for r in requirements),
                'any_required_witness': tri_any(fulfilled(c['id']) for c in primary),
                'linked_intermediate_witness': tri_any(fulfilled(c['id']) for c in intermediates),
                'collateral_disappearance': conflicts('collateral_disappearance'),
                'collateral_deformation': conflicts('collateral_deformation')}
    return {'version': VERSION, 'program_ref': program['program_ref'], 'image_pair_ref': pair_ref,
            'checks': checks, 'requirements': requirements, 'features': features, 'diagnostics': diagnostics}


def diagnostic_readout(record):
    """Fixed, uncalibrated test readout; not an M2 fitted satisfaction policy.

Every condition is monotone in its desired physical truth. Unknowns are evaluated
at both extreme assignments, sharing the same variable across all dependencies.
This prevents missing proof from defaulting directly to No.
"""
    checks = record['checks']
    def at_bound(upper):
        states = {}
        for k, c in checks.items():
            v = c['desired_state']
            if v == 'not_applicable' and c['role'] not in ('outcome', 'identity'):
                states[k] = None
            else:
                states[k] = upper if v in ('unknown', 'not_applicable') else v == 'true'
        memo = {}
        def ok(k):
            if k not in memo:
                memo[k] = bool(states[k]) and all(ok(d) for d in checks[k]['dependencies'])
            return memo[k]
        complete = all(all(ok(k) for k in r['check_ids']) for r in record['requirements'])
        preserved = all(ok(k) for k, c in checks.items() if c['role'].startswith('collateral_') and states[k] is not None)
        positive = any(ok(k) for k, c in checks.items() if c['role'] in ('outcome', 'intermediate'))
        return 2 if complete and preserved else 1 if positive else 0
    low, high = at_bound(False), at_bound(True)
    pred = low if low == high else -1
    return {'prediction': pred, 'label': ('No', 'Partial', 'Yes')[pred] if pred >= 0 else 'Unresolved',
            'lower_label': low, 'upper_label': high, 'policy': 'fixed-uncalibrated-m1-diagnostic-v1'}


class BoundInstructionCompiler:
    def __init__(self, calls):
        self.calls = calls

    def compile(self, instruction, *, case_id=None, max_tokens=8192):
        value, ref = self.calls.call('bound_instruction_v1', {'instruction': instruction, 'max_checks': MAX_CHECKS},
                                     COMPILER_SCHEMA, template=(TEMPLATES / 'compile.txt').read_text(),
                                     slot='once', max_tokens=max_tokens, case_id=case_id)
        return {'program': bind_program(instruction, value), 'execution_ref': ref, 'version': VERSION}


class BoundVisualObserver:
    def __init__(self, calls):
        self.calls = calls

    def observe(self, program, evidence, *, case_id=None, max_tokens=16384):
        validate_program(program)
        hashes, pair_ref = image_identity(evidence)
        value, ref = self.calls.call('bound_visual_observation_v1', {'program': program, 'image_pair_ref': pair_ref},
                                     observation_schema(program, pair_ref), template=(TEMPLATES / 'observe.txt').read_text(),
                                     media=media_inputs(evidence), slot='once', max_tokens=max_tokens, case_id=case_id)
        validate_observation(program, value, pair_ref)
        return {'observation': value, 'image_hashes': hashes, 'execution_ref': ref, 'version': VERSION}
