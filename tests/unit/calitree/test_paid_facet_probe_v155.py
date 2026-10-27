import base64
import json
from types import SimpleNamespace

import pytest

from critical import config
from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest
from critical.lm_engine import creds as credentials
from critical.lm_engine import openai_compat
from run import calitree_paid_facet_probe_v155 as probe
from run import calitree_paid_facet_credentials_v157 as credentials_runner


def test_unapproved_pilot_does_not_even_verify_or_load_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'verify', lambda _: pytest.fail('No credential/network preparation before authorization'))
    for live in (False, True):
        with pytest.raises(ValueError, match='authorization'):
            probe.collect(tmp_path, live=live)


def test_authorization_is_bound_to_frozen_manifest_before_provider_access(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'verify', lambda _: {'passed': True})
    (tmp_path/'manifest.json').write_text('{}')
    authorization = {'approved': True, 'upload_approved': True, 'manifest_sha256': 'wrong',
        'max_requests': probe.MAX_CALLS, 'max_completion_tokens': probe.MAX_TOKENS}
    (tmp_path/'authorization.json').write_text(json.dumps(authorization))
    with pytest.raises(AssertionError):
        probe.collect(tmp_path, live=True)


@pytest.mark.parametrize('runner', [probe, credentials_runner])
def test_mocked_wire_models_caps_strict_schema_and_failed_slot_retention(tmp_path, monkeypatch, runner):
    import critical.lm_engine as engines
    monkeypatch.setattr(probe, 'verify', lambda _: {'passed': True})
    monkeypatch.setattr(credentials_runner, 'verify', lambda _: {'passed': True})
    monkeypatch.setattr(config, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(config, 'CREDENTIALS_FILE', tmp_path/'no-credentials')
    public = credentials.ProviderCreds('public-fixture', probe.ENDPOINT, provider='openai')
    monkeypatch.setattr(engines, 'load_creds', lambda **kwargs: public)
    monkeypatch.setattr(credentials_runner, 'resolve_credentials', lambda _: (public, {'source': 'test', 'path': 'fixture'}))
    source = tmp_path/'source.png'; source.write_bytes(b'source-pixel-fixture')
    edited = tmp_path/'edited.png'; edited.write_bytes(b'edited-pixel-fixture')
    jobs = []
    for arm in ('luna', 'sol'):
        job = {'case': 'A', 'arm': arm, 'max_tokens': probe.CAPS[arm], 'prompt': 'fixture rubric',
               'schema': facets.schema(), 'evidence': {'source_image': str(source), 'edited_image': str(edited)}}
        job['request_ref'] = digest(job); jobs.append(job)
    (tmp_path/'jobs.json').write_text(json.dumps(jobs)); (tmp_path/'manifest.json').write_text('{}')
    (tmp_path/'references_training_only.json').write_text(json.dumps({'A': 2}))
    (tmp_path/'protocol.json').write_text(json.dumps({'collection_admission': {'accepted_min': 23, 'correct_min': 18,
        'each_grade_correct_min': 5, 'literal_gap_contradictions_max': 2}}))
    (tmp_path/'authorization.json').write_text(json.dumps({'approved': True, 'upload_approved': True,
        'manifest_sha256': probe.file_hash(tmp_path/'manifest.json'), 'max_requests': probe.MAX_CALLS,
        'max_completion_tokens': probe.MAX_TOKENS}))
    fixture = {'new_requested_content': 'some', 'all_material_facets': 'yes', 'operation_fidelity': 'faithful',
        'source_entity_fidelity': 'preserved', 'scope_coverage': 'full', 'evidence': 'requested change visible', 'material_gap': 'none'}
    requests = []
    def post(url, **kwargs):
        requests.append((url, kwargs)); payload = kwargs['json']; arm = 'luna' if payload['model'] == probe.MODELS['luna']['model'] else 'sol'
        assert url == probe.ENDPOINT+'/chat/completions' and kwargs['allow_redirects'] is False
        assert payload['max_completion_tokens'] == probe.CAPS[arm]
        assert payload['reasoning_effort'] == probe.MODELS[arm]['reasoning_effort']
        assert (payload.get('temperature') == 0.) if arm == 'luna' else ('temperature' not in payload)
        schema = payload['response_format']; assert schema['type'] == 'json_schema' and schema['json_schema']['strict'] is True
        assert schema['json_schema']['schema'] == facets.schema()
        parts = payload['messages'][0]['content']
        assert parts[0]['text'] == 'fixture rubric\nINPUT_JSON: {}'
        assert [parts[1]['text'], parts[3]['text']] == ['SOURCE image', 'EDITED image']
        assert base64.b64decode(parts[2]['image_url']['url'].split(',', 1)[1]) == source.read_bytes()
        assert base64.b64decode(parts[4]['image_url']['url'].split(',', 1)[1]) == edited.read_bytes()
        data = {'model': payload['model'], 'choices': [{'finish_reason': 'length' if arm == 'luna' else 'stop',
                 'message': {'content': json.dumps(fixture)}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}}
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(openai_compat.requests, 'post', post)
    runner.collect(tmp_path, live=True)
    assert len(requests) == 2
    rows = json.loads((tmp_path/'predictions.json').read_text())
    assert rows[0]['luna'] == -1 and rows[0]['sol'] == 2
    budget = json.loads((tmp_path/'ledger/budget.json').read_text())
    assert budget['calls'] == 2 and budget['completion_tokens_or_reserved'] == 40
    # Simulate losing only the per-case summary. The invalid durable slot must
    # still refuse resampling and cannot produce a third HTTP request.
    (tmp_path/'responses/A-luna.json').unlink()
    runner.collect(tmp_path, live=True)
    assert len(requests) == 2
    assert json.loads((tmp_path/'responses/A-luna.json').read_text())['accepted'] is False
