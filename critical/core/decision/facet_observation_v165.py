"""Exact Sol facet request contract and instruction/image-bound observations."""
from copy import deepcopy
import json
from pathlib import Path

from . import facet_policy_v150 as facts
from .artifacts import digest
from .bound_evidence_v2 import image_identity, validate_program

VERSION = 'bound-semantic-facet-observation-v165'
IDENTITY = {'model': 'gpt-6.1-sol', 'provider': 'openai', 'temperature': None, 'reasoning_effort': 'low'}
STAGE = 'explicit_semantic_facets_v155'
MAX_TOKENS = 8192
TEMPLATES = Path(__file__).parents[1]/'prompts/templates/facet_policy_v150'


def make_profile():
    schema = facts.schema(); order = ['evidence', 'material_gap']+list(facts.FIELDS)
    schema['properties'] = {k: schema['properties'][k] for k in order}; schema['required'] = order
    guide = (TEMPLATES/'field_guide_v153.txt').read_text().replace('{schema}', json.dumps(schema)).replace('{field_order}', ', '.join(order))
    template = (TEMPLATES/'observe.txt').read_text()+'\n\n'+guide
    value = {'version': VERSION+'-profile', 'identity': deepcopy(IDENTITY), 'stage': STAGE,
             'slot': 'sol', 'max_tokens': MAX_TOKENS, 'schema': schema, 'template': template}
    value['profile_ref'] = digest(value)
    return value


def validate_profile(profile):
    if profile != make_profile():
        raise ValueError('Changed facet model, prompt, schema or budget profile')
    return profile


def prompt(program, profile):
    validate_program(program); validate_profile(profile)
    return profile['template'].replace('{instruction}', json.dumps(program['instruction']))


def media_identity(hashes):
    return [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'sha256': hashes['source_image']},
            {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'sha256': hashes['edited_image']}]


def request_ref(program, profile, case_id, media, route=None):
    validate_profile(profile)
    if not isinstance(case_id, str) or not case_id or (route is not None and (not isinstance(route, str) or not route)):
        raise ValueError('Explicit request identity and optional named route required')
    ref = digest([profile['identity'], case_id, STAGE, {}, profile['schema'], prompt(program, profile),
                  media, 'sol', MAX_TOKENS])
    return digest([ref, route]) if route is not None else ref


def bind(program, pair_ref, profile, case_id, hashes, observation, execution_ref, route=None):
    validate_program(program); validate_profile(profile); facts.validate(observation)
    if (set(hashes) != {'source_image', 'edited_image'} or
        any(not isinstance(v, str) or len(v) != 64 for v in hashes.values()) or
        digest(['bound-physical-evidence-v2', 'source_first', hashes['source_image'], hashes['edited_image']]) != pair_ref):
        raise ValueError('Ordered facet image identity differs')
    media = media_identity(hashes)
    if execution_ref != request_ref(program, profile, case_id, media, route):
        raise ValueError('Facet request execution differs')
    record = {'version': VERSION, 'program_ref': program['program_ref'], 'image_pair_ref': pair_ref,
        'profile_ref': profile['profile_ref'], 'prompt_ref': digest(prompt(program, profile)+'\nINPUT_JSON: {}'),
        'case_id': case_id, 'image_hashes': deepcopy(hashes), 'route': route,
        'execution_ref': execution_ref, 'observation': deepcopy(observation)}
    record['record_ref'] = digest(record)
    return record


def validate_record(program, pair_ref, profile, record):
    if not isinstance(record, dict):
        raise ValueError('Bound facet observation required')
    expected = bind(program, pair_ref, profile, record.get('case_id'), record.get('image_hashes', {}),
                    record.get('observation'), record.get('execution_ref'), record.get('route'))
    if expected != record:
        raise ValueError('Facet observation belongs to another program, image pair or profile')
    return record['observation']


def record_from_job(program, pair_ref, profile, job, result):
    """Convert an independently audited cached response, without another call."""
    validate_profile(profile)
    if result is None or not result.get('accepted'):
        return None
    if (job['program_ref'] != program['program_ref'] or job['instruction'] != program['instruction'] or
        job['image_pair_ref'] != pair_ref or job['prompt'] != prompt(program, profile) or
        job['schema'] != profile['schema'] or job['identity'] != IDENTITY or job['max_tokens'] != MAX_TOKENS or
        job['request_ref'] != digest({k: v for k, v in job.items() if k != 'request_ref'}) or
        result['request_ref'] != job['request_ref']):
        raise ValueError('Cached facet request differs from the inference contract')
    return bind(program, pair_ref, profile, job['case'], job['image_hashes'], result['value'], result['execution_ref'])


class FacetObserver:
    """One explicitly supplied, budgeted model call for the whole facet record."""
    def __init__(self, calls, profile=None):
        self.profile = deepcopy(validate_profile(profile or make_profile()))
        if getattr(calls, 'identity', None) != IDENTITY:
            raise ValueError('Explicit Sol-low budgeted call interface required')
        self.calls = calls

    def observe(self, program, evidence, pair_ref, *, case_id=None):
        validate_profile(self.profile)
        hashes, actual_pair = image_identity(evidence)
        if actual_pair != pair_ref:
            raise ValueError('Facet observer source/edited pair differs')
        bound_case = getattr(self.calls, 'case_id', None)
        if bound_case is not None:
            if case_id is not None and case_id != bound_case:
                raise ValueError('Facet observer case context differs')
            case_id = bound_case
        case_id = case_id or digest([program['program_ref'], pair_ref])
        routed = self.calls; route = None
        for _ in range(8):
            route = getattr(routed, 'route', None)
            if route is not None or not hasattr(routed, 'parent'):
                break
            routed = routed.parent
        media = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': evidence['source_image']},
                 {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': evidence['edited_image']}]
        options = {} if bound_case is not None else {'case_id': case_id}
        value, ref = self.calls.call(STAGE, {}, self.profile['schema'], template=prompt(program, self.profile),
            media=media, slot='sol', max_tokens=MAX_TOKENS, **options)
        return bind(program, pair_ref, self.profile, case_id, hashes, value, ref, route)
