from copy import deepcopy
import json

import pytest

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import bind_program
from run.verify_calitree_local_review_cache_v98 import validate_response
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_local_rubric_v94 import value


def fixture():
    p = bind_program('Move the bowl left', draft())
    profile = {'model': 'Qwen/Qwen3-VL-8B-Instruct', 'engine': 'local_qwen_grammar_v95', 'max_new_tokens': 256}
    prompt = 'Fixed observation prompt.'
    job = {'case': 'fixture', 'program': p, 'image_pair_ref': 'pair', 'identity_ref': digest(profile),
           'schema': facts.schema(), 'prompt': prompt, 'prompt_ref': digest(prompt)}
    job['request_ref'] = digest(job)
    v = value(); record = facts.bind(p, 'pair', job['identity_ref'], job['prompt_ref'], v)
    raw = {'model': profile['model'], 'engine': profile['engine'], 'endpointHost': 'local-mps',
           'promptTokens': 100, 'completionTokens': 80, 'totalTokens': 180,
           'content': json.dumps(v), 'parsed': v, 'finishReason': 'stop'}
    response = {'case': 'fixture', 'request_ref': job['request_ref'], 'response': raw,
                'observation': v, 'record': record, 'error': None}
    return job, response, profile


def test_raw_observation_and_exact_request_are_checked_independently():
    job, response, profile = fixture(); assert validate_response(job, response, profile)
    wrong = deepcopy(response); wrong['response']['content'] = json.dumps({**value(), 'endpoint': 'absent'})
    with pytest.raises(ValueError, match='unmodified raw'):
        validate_response(job, wrong, profile)
    wrong = deepcopy(response); wrong['request_ref'] = 'other'
    with pytest.raises(ValueError, match='different request'):
        validate_response(job, wrong, profile)


def test_truncation_and_foreign_engines_cannot_be_counted_as_valid():
    job, response, profile = fixture()
    for field, replacement, expected in [('finishReason', 'length', 'truncated'), ('endpointHost', 'api.openai.com', 'remote model')]:
        wrong = deepcopy(response); wrong['response'][field] = replacement
        with pytest.raises(ValueError, match=expected):
            validate_response(job, wrong, profile)


def test_failed_slots_stay_failed_instead_of_receiving_repaired_observations():
    job, response, profile = fixture(); failed = {**response, 'record': None, 'observation': None, 'error': 'ValueError: invalid observation'}
    assert validate_response(job, failed, profile) is False
    with pytest.raises(ValueError, match='explicitly failed'):
        validate_response(job, {**failed, 'observation': value()}, profile)


def test_record_and_token_mutations_fail_even_if_the_label_looks_plausible():
    job, response, profile = fixture(); wrong = deepcopy(response); wrong['record']['image_pair_ref'] = 'other'
    with pytest.raises(ValueError, match='binding'):
        validate_response(job, wrong, profile)
    wrong = deepcopy(response); wrong['response']['totalTokens'] += 1
    with pytest.raises(ValueError, match='accounting'):
        validate_response(job, wrong, profile)


def test_a_new_resolution_profile_cannot_reuse_an_old_bound_record():
    job, response, profile = fixture()
    profile = {**profile, 'max_new_tokens': 512, 'max_pixels_per_image': 1048576}
    job = {k: v for k, v in job.items() if k != 'request_ref'}
    job['identity_ref'] = digest(profile); job['request_ref'] = digest(job)
    response['request_ref'] = job['request_ref']
    with pytest.raises(ValueError, match='binding'):
        validate_response(job, response, profile)


def test_new_profile_output_allowance_is_explicit_and_still_bounded():
    job, response, profile = fixture(); profile = {**profile, 'max_new_tokens': 512}
    job = {k: v for k, v in job.items() if k != 'request_ref'}
    job['identity_ref'] = digest(profile); job['request_ref'] = digest(job)
    response['request_ref'] = job['request_ref']
    response['record'] = facts.bind(job['program'], job['image_pair_ref'], job['identity_ref'], job['prompt_ref'], value())
    response['response'].update(completionTokens=300, totalTokens=400)
    assert validate_response(job, response, profile)
    response['response'].update(completionTokens=513, totalTokens=613)
    with pytest.raises(ValueError, match='accounting'):
        validate_response(job, response, profile)
