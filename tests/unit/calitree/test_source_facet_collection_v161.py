import json
from threading import Lock
from types import SimpleNamespace

import pytest

from critical.core.decision import facet_policy_v150 as facets
from critical.lm_engine import openai_compat
from critical.lm_engine.creds import ProviderCreds
from run import calitree_source_facet_collection_v161 as collection


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, 'verify', lambda _: {'passed': True})
    creds = ProviderCreds('public-fixture', collection.ENDPOINT, provider='openai')
    monkeypatch.setattr(collection, 'resolve_credentials', lambda _: (creds, {'source': 'mock'}))
    source = tmp_path/'source.png'; source.write_bytes(b'source-fixture')
    edited = tmp_path/'edit.png'; edited.write_bytes(b'edited-fixture')
    jobs = []
    for i in range(8):
        raw = {'case': 'C'+str(i), 'program': {'instruction': 'fixture '+str(i), 'program_ref': str(i)},
               'evidence': {'source_image': str(source), 'edited_image': str(edited)}}
        jobs.append(collection.make_job(raw, {'source_group': 'group'+str(i)}))
    out = tmp_path/'out'; out.mkdir()
    (out/'jobs.json').write_text(json.dumps(jobs)); (out/'manifest.json').write_text('{}')
    queues = {str(w): [j['case'] for j in jobs[w::4]] for w in range(4)}
    (out/'worker_assignments.json').write_text(json.dumps(queues))
    (out/'authorization.json').write_text(json.dumps({'approved': True, 'upload_approved': True,
        'manifest_sha256': collection.file_hash(out/'manifest.json'), 'max_requests': collection.MAX_CALLS,
        'max_completion_tokens': collection.MAX_TOKENS}))
    return out


def test_unapproved_collection_never_loads_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, 'verify', lambda _: pytest.fail('No collection before explicit authorization'))
    with pytest.raises(ValueError, match='New351-request'):
        collection.collect(tmp_path, live=True)


def test_worker_ledgers_cannot_borrow_or_exceed_reserved_token_allowances(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, 'WORKER_TOKEN_CAP', collection.PER_REQUEST)
    monkeypatch.setattr(collection, 'MAX_TOKENS', collection.WORKERS*collection.PER_REQUEST)
    out = fixture(tmp_path, monkeypatch); calls = []; guard = Lock()
    value = {'new_requested_content': 'some', 'all_material_facets': 'yes', 'operation_fidelity': 'faithful',
        'source_entity_fidelity': 'preserved', 'scope_coverage': 'full', 'evidence': 'fixture', 'material_gap': 'none'}
    def post(url, **kwargs):
        with guard:
            calls.append(kwargs['json'])
        request = kwargs['json']; assert url == collection.ENDPOINT+'/chat/completions'
        assert request['model'] == collection.MODELS['sol']['model'] and request['reasoning_effort'] == 'low'
        assert 'temperature' not in request and kwargs['allow_redirects'] is False
        assert request['max_completion_tokens'] == collection.PER_REQUEST
        data = {'model': request['model'], 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': collection.PER_REQUEST,
                          'total_tokens': 10+collection.PER_REQUEST}}
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(openai_compat.requests, 'post', post)
    collection.collect(out, live=True)
    assert len(calls) == 4  # Each worker's second job cannot reserve another call.
    status = json.loads((out/'collection_status.json').read_text())
    assert status['new_attempts'] == 4 and status['completion_tokens_or_reserved'] == collection.MAX_TOKENS
    assert not status['complete']
    assert all(r['status'] == 'budget_exhausted_before_next_reservation' for r in json.loads((out/'worker_status.json').read_text()))
    with pytest.raises(ValueError, match='Terminal/stopped'):
        collection.collect(out, live=True)
    assert len(calls) == 4


def test_provider_rejection_stops_all_new_work_without_retrying_slots(tmp_path, monkeypatch):
    out = fixture(tmp_path, monkeypatch); calls = []; guard = Lock()
    def rejected(url, **kwargs):
        with guard:
            calls.append(kwargs['json'])
        return SimpleNamespace(status_code=401, text='public fixture rejection')
    monkeypatch.setattr(openai_compat.requests, 'post', rejected)
    collection.collect(out, live=True)
    assert 1 <= len(calls) <= 4  # Only one already-reserved request per worker.
    status = json.loads((out/'collection_status.json').read_text())
    assert status['global_stop'] and status['new_valid_observations'] == 0
    assert status['new_attempts'] == len(calls) and status['completion_tokens_or_reserved'] == len(calls)*collection.PER_REQUEST
    assert all(not json.loads(p.read_text())['accepted'] for p in (out/'responses').glob('*.json'))
    with pytest.raises(ValueError, match='Terminal/stopped'):
        collection.collect(out, live=True)
