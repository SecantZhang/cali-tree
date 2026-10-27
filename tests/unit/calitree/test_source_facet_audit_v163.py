import json
from pathlib import Path
import shutil
from threading import Lock
from types import SimpleNamespace

from critical.lm_engine import openai_compat
from critical.lm_engine.creds import ProviderCreds
from run import calitree_source_facet_collection_v161 as collection
from run import verify_calitree_source_facet_v163 as auditor


def test_full_prepared_collection_and_native_audit_with_no_network(tmp_path, monkeypatch):
    prepared = collection.ROOT/'logs/exps/261025-source-facet-collection-v161-r1'
    out = tmp_path/'collection'; out.mkdir()
    # Copy only frozen, offline preparation inputs, never credentials or any
    # concurrently collected real responses/authorization.
    for name in ('manifest.json', 'protocol.json', 'jobs.json', 'memberships.json', 'worker_assignments.json',
                 'reused_observations.json', 'upload_inventory.json', 'references_not_uploaded.json'):
        shutil.copyfile(prepared/name, out/name)
    shutil.copytree(prepared/'source_snapshot', out/'source_snapshot')
    authorization = {'approved': True, 'upload_approved': True, 'mock_transport_test': True,
        'manifest_sha256': collection.file_hash(out/'manifest.json'), 'max_requests': collection.MAX_CALLS,
        'max_completion_tokens': collection.MAX_TOKENS}
    (out/'authorization.json').write_text(json.dumps(authorization))
    public = ProviderCreds('public-fixture', collection.ENDPOINT, provider='openai')
    monkeypatch.setattr(collection, 'resolve_credentials', lambda _: (public, {'source': 'mock_transport_test'}))
    calls = []; mutex = Lock()
    value = {'evidence': 'TEST FIXTURE: no model inference', 'material_gap': 'none',
        'new_requested_content': 'some', 'all_material_facets': 'yes', 'operation_fidelity': 'faithful',
        'source_entity_fidelity': 'preserved', 'scope_coverage': 'full'}
    def post(url, **kwargs):
        assert url == collection.ENDPOINT+'/chat/completions'
        assert kwargs['headers']['Authorization'] == 'Bearer public-fixture'
        with mutex:
            calls.append(1)
        request = kwargs['json']
        data = {'model': request['model'], 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}}
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(openai_compat.requests, 'post', post)
    collection.collect(out, live=True)
    assert len(calls) == 351
    audited = tmp_path/'audit'; auditor.audit(out, audited)
    report = json.loads((audited/'verification.json').read_text())
    assert report['passed'] and report['complete'] and report['worker_native_replays'] == 351
    assert report['valid_total'] == 374 and report['retained_pilot_failure'] == 1
    assert report['completion_tokens_or_reserved'] == 351*20
    assert report['reported_input_tokens'] == 351*10
    assert not report['fitting_ready'] and report['mock_transport_test']
    observations = json.loads((audited/'observations.json').read_text())
    assert len(observations) == 375 and sum(r['accepted'] for r in observations) == 374
    assert next(r for r in observations if r['case'] == 'N108')['value'] is None
