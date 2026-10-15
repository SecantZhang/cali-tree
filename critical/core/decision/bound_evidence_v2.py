"""Bound evidence with explicit absence polarity and preservation roles.

The v1 module and its recorded experiment remain immutable. Compiler links are
one-directional here: required check membership is derived, not generated twice.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from . import bound_evidence as base
from .artifacts import digest
from .compiler import TEXT, array, enum, object_schema, media_inputs

VERSION = 'bound-physical-evidence-v2'
TEMPLATES = Path(__file__).parents[1] / 'prompts/templates/bound_evidence_v2'
MAX_CHECKS = base.MAX_CHECKS
STATES = base.STATES
ROLES = (*base.ROLES, 'preservation')
KINDS = base.KINDS
REQUIRED_ROLES = ('outcome', 'identity', 'preservation')
TEMPORAL_KINDS = {'pose', 'grasp', 'contact', 'material_transfer', 'closure', 'orientation', 'separation', 'style'}
CHECK = object_schema({**base.CHECK['properties'], 'role': enum(ROLES),
                      'absence_when': enum(('true', 'false', 'never')),
                      'absence_source_anchor': enum(('required', 'not_required'))})
REQUIREMENT = object_schema({k: v for k, v in base.REQUIREMENT['properties'].items() if k != 'check_ids'})
COMPILER_SCHEMA = object_schema({'contract': base.CONTRACT,
    'requirements': {**array(REQUIREMENT), 'minItems': 1, 'maxItems': 6},
    'checks': {**array(CHECK), 'minItems': 3, 'maxItems': MAX_CHECKS}})


def validate_draft(draft, instruction):
    base._fields(draft, COMPILER_SCHEMA['properties'], 'program_fields')
    if not isinstance(draft['requirements'], list) or not isinstance(draft['checks'], list):
        base.fail('program_size', 'Requirements and checks must be lists')
    for r in draft['requirements']:
        base._fields(r, REQUIREMENT['properties'], 'requirement_fields')
    for c in draft['checks']:
        base._fields(c, CHECK['properties'], 'check_fields')
        if c['role'] not in ROLES or c['absence_when'] not in ('true', 'false', 'never') or c['absence_source_anchor'] not in ('required', 'not_required'):
            base.fail('invalid_check_type', 'Invalid role or absence evidence contract')
        if c['kind'] == 'absence' and (c['absence_when'] == 'never' or c['absence_source_anchor'] != 'required'):
            base.fail('absence_contract_missing', 'Absence-kind questions require explicit polarity and original-scene anchoring')
        if c['role'] == 'preservation' and c['expected_state'] != 'true':
            base.fail('preservation_polarity', 'Preservation asks positively about a retained physical property')
    legacy = deepcopy(draft)
    for r in legacy['requirements']:
        r['check_ids'] = [c['id'] for c in draft['checks'] if c['role'] in REQUIRED_ROLES and r['id'] in c['requirement_ids']]
    for c in legacy['checks']:
        c.pop('absence_when'); c.pop('absence_source_anchor')
        if c['role'] == 'preservation':
            c['role'] = 'identity'
    base.validate_draft(legacy, instruction)
    by_id = {c['id']: c for c in draft['checks']}
    for c in draft['checks']:
        if c['role'] == 'intermediate' and any(by_id[d]['role'] in ('identity', 'preservation') for d in c['dependencies']):
            base.fail('intermediate_identity_gate', 'Keep observable intermediate geometry separate from identity/preservation uncertainty')
    # A physical temporal/style endpoint requires a linked, separately observable
    # intermediate. Merely adding a field called progress cannot satisfy this.
    for r in draft['requirements']:
        required = [c for c in draft['checks'] if c['role'] == 'outcome' and r['id'] in c['requirement_ids']]
        if any(c['kind'] in TEMPORAL_KINDS for c in required):
            if not any(c['role'] == 'intermediate' and r['id'] in c['requirement_ids'] for c in draft['checks']):
                base.fail('missing_linked_intermediate', 'Temporal/style requirement has no physical intermediate: ' + r['id'])
    return draft


def bind_program(instruction, draft):
    validate_draft(draft, instruction)
    value = {'version': VERSION, 'instruction': instruction, **deepcopy(draft)}
    for r in value['requirements']:
        r['check_ids'] = [c['id'] for c in value['checks'] if c['role'] in REQUIRED_ROLES and r['id'] in c['requirement_ids']]
    context = [VERSION, instruction, value['contract'], value['requirements']]
    value['checks'] = [{**c, 'check_ref': digest([context, c])} for c in value['checks']]
    return {**value, 'program_ref': digest(value)}


def validate_program(program):
    base._fields(program, ('version', 'instruction', 'contract', 'requirements', 'checks', 'program_ref'), 'bound_program_fields')
    if program['version'] != VERSION:
        base.fail('program_version', 'Unsupported bound evidence version')
    d = {k: deepcopy(program[k]) for k in ('contract', 'requirements', 'checks')}
    for c in d['checks']:
        base._fields(c, (*CHECK['properties'], 'check_ref'), 'bound_check_fields'); c.pop('check_ref')
    for r in d['requirements']:
        base._fields(r, (*REQUIREMENT['properties'], 'check_ids'), 'bound_requirement_fields'); r.pop('check_ids')
    if program != bind_program(program['instruction'], d):
        base.fail('program_hash_mismatch', 'Bound question, role, polarity, dependency, or requirement membership changed')
    return program


def image_identity(evidence):
    base._fields(evidence, ('source_image', 'edited_image'), 'image_fields')
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
            'source_evidence': TEXT, 'edited_evidence': TEXT, 'comparison': TEXT})
    return object_schema({'program_ref': enum((program['program_ref'],)), 'image_pair_ref': enum((pair_ref,)),
                          'checks': object_schema(fields)})


def validate_observation(program, value, pair_ref):
    schema = observation_schema(program, pair_ref)
    base._fields(value, schema['properties'], 'observation_fields')
    if value['program_ref'] != program['program_ref'] or value['image_pair_ref'] != pair_ref:
        base.fail('observation_binding_mismatch', 'Wrong program or ordered image pair')
    base._fields(value['checks'], schema['properties']['checks']['properties'], 'observation_check_set')
    for c in program['checks']:
        row = value['checks'][c['id']]
        fields = schema['properties']['checks']['properties'][c['id']]['properties']
        base._fields(row, fields, 'observation_check_fields')
        for k, spec in fields.items():
            if 'enum' in spec and row[k] not in spec['enum']:
                base.fail('check_binding_mismatch' if k in ('check_ref', 'question') else 'invalid_observation_state', k)
            if not isinstance(row[k], str) or not row[k].strip():
                base.fail('missing_evidence_text', k)
    return value


def effective_state(check, observation):
    state, issues = observation['state'], []
    if observation['applicability'] == 'unknown':
        state = 'unknown'; issues.append('applicability_unknown')
    elif observation['applicability'] == 'not_applicable' or state == 'not_applicable':
        if check['role'] in REQUIRED_ROLES:
            state = 'unknown'; issues.append('required_check_not_applicable')
        else:
            state = 'not_applicable'
    if check['absence_when'] != 'never' and state == check['absence_when']:
        if check['absence_source_anchor'] == 'required' and observation['source_anchor'] != 'identified':
            state = 'unknown'; issues.append('absence_source_unanchored')
        if observation['edited_coverage'] != 'adequate':
            state = 'unknown'; issues.append('absence_view_inadequate')
    return state, issues


def derive_record(program, value, pair_ref):
    validate_observation(program, value, pair_ref)
    checks, diagnostics = {}, []
    for c in program['checks']:
        state, issues = effective_state(c, value['checks'][c['id']])
        checks[c['id']] = {**deepcopy(c), 'asserted_state': value['checks'][c['id']]['state'],
                           'state': state, 'desired_state': base.desired_state(state, c['expected_state']),
                           'observation': deepcopy(value['checks'][c['id']]), 'diagnostics': issues}
        diagnostics.extend({'check_id': c['id'], 'code': x} for x in issues)
    memo = {}
    def fulfilled(k):
        if k not in memo:
            c = checks[k]
            memo[k] = base.tri_all([c['desired_state'], *(fulfilled(d) for d in c['dependencies'])])
        return memo[k]
    requirements = [{**r, 'state': base.tri_all(fulfilled(k) for k in r['check_ids'])} for r in program['requirements']]
    primary = [c for c in checks.values() if c['role'] == 'outcome']
    mids = [c for c in checks.values() if c['role'] == 'intermediate' and c['state'] != 'not_applicable']
    conflict = lambda role: base.tri_any(c['state'] for c in checks.values() if c['role'] == role and c['state'] != 'not_applicable')
    features = {'all_requirements_satisfied': base.tri_all(r['state'] for r in requirements),
                'some_requirement_satisfied': base.tri_any(r['state'] for r in requirements),
                'any_required_witness': base.tri_any(fulfilled(c['id']) for c in primary),
                'linked_intermediate_witness': base.tri_any(fulfilled(c['id']) for c in mids),
                'collateral_disappearance': conflict('collateral_disappearance'),
                'collateral_deformation': conflict('collateral_deformation')}
    return {'version': VERSION, 'program_ref': program['program_ref'], 'image_pair_ref': pair_ref,
            'checks': checks, 'requirements': requirements, 'features': features, 'diagnostics': diagnostics}


# The diagnostic remains exactly the same fixed code as v1. Required preservation
# NA has already become unknown above; preserved context never supplies progress.
diagnostic_readout = base.diagnostic_readout


class BoundInstructionCompiler:
    def __init__(self, calls):
        self.calls = calls

    def compile(self, instruction, *, case_id=None, max_tokens=8192):
        value, ref = self.calls.call('bound_instruction_v2', {'instruction': instruction, 'max_checks': MAX_CHECKS},
                                     COMPILER_SCHEMA, template=(TEMPLATES / 'compile.txt').read_text(),
                                     slot='once', max_tokens=max_tokens, case_id=case_id)
        return {'program': bind_program(instruction, value), 'execution_ref': ref, 'version': VERSION}


class BoundVisualObserver:
    def __init__(self, calls):
        self.calls = calls

    def observe(self, program, evidence, *, case_id=None, max_tokens=16384):
        validate_program(program); hashes, pair = image_identity(evidence)
        value, ref = self.calls.call('bound_visual_observation_v2', {'program': program, 'image_pair_ref': pair},
                                     observation_schema(program, pair), template=(TEMPLATES / 'observe.txt').read_text(),
                                     media=media_inputs(evidence), slot='once', max_tokens=max_tokens, case_id=case_id)
        validate_observation(program, value, pair)
        return {'observation': value, 'image_hashes': hashes, 'execution_ref': ref, 'version': VERSION}
