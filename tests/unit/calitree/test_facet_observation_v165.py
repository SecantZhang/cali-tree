from copy import deepcopy
from types import SimpleNamespace

import pytest

from critical.core.decision import facet_observation_v165 as facts
from critical.core.decision.bound_evidence_v2 import bind_program, image_identity
from tests.unit.calitree.test_bound_evidence_v2 import draft
from run.calitree_source_facet_collection_v161 import make_job


def value(**changes):
    return {'evidence': 'Requested result visible', 'material_gap': 'none', 'new_requested_content': 'some',
        'all_material_facets': 'yes', 'operation_fidelity': 'faithful', 'source_entity_fidelity': 'preserved',
        'scope_coverage': 'full', **changes}


def inputs(tmp_path):
    p = bind_program('Move the bowl left', draft())
    a, b = tmp_path/'source.png', tmp_path/'edited.png'; a.write_bytes(b'source-fixture'); b.write_bytes(b'edited-fixture')
    evidence = {'source_image': str(a), 'edited_image': str(b)}
    hashes, pair = image_identity(evidence)
    return p, evidence, hashes, pair


def test_cached_collection_record_has_the_exact_inference_request_identity(tmp_path):
    p, evidence, hashes, pair = inputs(tmp_path); profile = facts.make_profile()
    job = make_job({'case': 'case', 'program': p, 'evidence': evidence}, {'source_group': 'fixture'})
    ref = facts.request_ref(p, profile, 'case', facts.media_identity(hashes))
    result = {'accepted': True, 'request_ref': job['request_ref'], 'execution_ref': ref, 'value': value()}
    record = facts.record_from_job(p, pair, profile, job, result)
    assert facts.validate_record(p, pair, profile, record) == value()
    assert facts.record_from_job(p, pair, profile, job, {'accepted': False}) is None
    with pytest.raises(ValueError):
        facts.validate_record(p, 'reversed-pair', profile, record)
    with pytest.raises(ValueError):
        facts.validate_record(bind_program('Move the bowl right', draft('Move the bowl right')), pair, profile, record)
    bad = deepcopy(record); bad['profile_ref'] = 'another-profile'
    with pytest.raises(ValueError):
        facts.validate_record(p, pair, profile, bad)


def test_whole_facet_record_uses_one_call_and_bound_routed_case_context(tmp_path):
    p, evidence, hashes, pair = inputs(tmp_path); profile = facts.make_profile()
    calls = []
    class BoundCalls:
        identity = facts.IDENTITY
        case_id = 'bound-case'
        parent = SimpleNamespace(route='facet-route')
        def call(self, stage, payload, schema, **kwargs):
            calls.append(1)
            assert stage == facts.STAGE and payload == {} and schema == profile['schema']
            assert kwargs['max_tokens'] == 8192 and kwargs['slot'] == 'sol' and 'case_id' not in kwargs
            assert kwargs['template'] == facts.prompt(p, profile) and len(kwargs['media']) == 4
            return value(), facts.request_ref(p, profile, self.case_id, facts.media_identity(hashes), 'facet-route')
    observer = facts.FacetObserver(BoundCalls())
    record = observer.observe(p, evidence, pair)
    assert len(calls) == 1 and facts.validate_record(p, pair, profile, record) == value()
    with pytest.raises(ValueError, match='case context'):
        observer.observe(p, evidence, pair, case_id='other-case')
    with pytest.raises(ValueError, match='pair differs'):
        observer.observe(p, evidence, 'wrong-pair')
    assert len(calls) == 1


def test_changed_model_or_profile_cannot_make_a_new_request():
    with pytest.raises(ValueError, match='Sol-low'):
        facts.FacetObserver(SimpleNamespace(identity={'model': 'another-model'}))
    profile = facts.make_profile(); profile['max_tokens'] = 8193
    with pytest.raises(ValueError, match='Changed facet'):
        facts.validate_profile(profile)
