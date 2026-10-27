import json
import sys
from types import SimpleNamespace

import pytest

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest
from run import calitree_explicit_facet_probe_v153 as probe
from run.verify_calitree_facet_probe_v151 import classification_metrics


def test_unresolved_observation_remains_in_balanced_accuracy_denominator():
    rows = [{'reference': 0, 'prediction': 0}, {'reference': 1, 'prediction': -1},
            {'reference': 2, 'prediction': 2}]
    metrics = classification_metrics(rows, 'prediction')
    assert metrics['accuracy'] == metrics['balanced_accuracy'] == pytest.approx(2/3)
    assert metrics['unresolved'] == 1 and metrics['per_class']['partial']['recall'] == 0


def test_backend_failure_is_terminal_and_not_retried_or_replaced(tmp_path, monkeypatch):
    profile = {'max_pixels': 256*32*32, 'packages': {}}
    jobs = []
    for case in ('A', 'B'):
        job = {'case': case, 'arm': probe.ARMS[0], 'evidence': {'source_image': 'a', 'edited_image': 'b'},
               'image_hashes': ['hash-a', 'hash-b'], 'image_pair_ref': 'pair', 'prompt': 'fixture', 'schema': facets.schema()}
        job['request_ref'] = digest(job); jobs.append(job)
    protocol = {'fixture': True}
    checkpoint = tmp_path/'checkpoint.json'; checkpoint.write_text(json.dumps({'destination': str(tmp_path)}))
    manifest = {'profile_ref': digest(profile), 'jobs_ref': digest(jobs), 'protocol_ref': digest(protocol),
                'checkpoint_sha256': probe.file_hash(checkpoint), 'code_sha256': {}}
    out = tmp_path/'out'; out.mkdir()
    for name, value in [('profile', profile), ('jobs', jobs), ('protocol', protocol), ('manifest', manifest)]:
        (out/(name+'.json')).write_text(json.dumps(value))
    calls = []
    class FailingEngine:
        def __init__(self, *args, **kwargs):
            pass
        def _load(self):
            pass
        def generate(self, *args, **kwargs):
            calls.append(1)
            raise RuntimeError('fixed local backend failure')
    mx = SimpleNamespace(set_memory_limit=lambda _: 1, get_peak_memory=lambda: 0)
    monkeypatch.setitem(sys.modules, 'mlx', SimpleNamespace(core=mx)); monkeypatch.setitem(sys.modules, 'mlx.core', mx)
    monkeypatch.setattr(probe, 'CHECKPOINT', checkpoint); monkeypatch.setattr(probe, 'LargeMLXEngine', FailingEngine)
    monkeypatch.setattr(probe, 'image_identity', lambda _: (['hash-a', 'hash-b'], 'pair'))
    monkeypatch.setattr(probe.fcntl, 'flock', lambda *args: None)
    probe.collect(out)
    terminal = json.loads((out/'results.json').read_text())
    assert len(calls) == 1 and terminal['attempts'] == 1 and not terminal['complete']
    assert terminal['reserved_tokens'] == 512 and terminal['accepted'] == 0
    response = json.loads(next((out/'responses').glob('*.json')).read_text())
    assert response['error'] == 'RuntimeError: fixed local backend failure' and not response['accepted']
    with pytest.raises(ValueError, match='No resume'):
        probe.collect(out)


def test_new_prompt_preparation_preserves_images_and_exposes_literal_contract(tmp_path):
    prior = tmp_path/'prior'; prior.mkdir()
    (prior/'results.json').write_text(json.dumps({'complete': True}))
    (prior/'profile.json').write_text('{}'); (prior/'references.json').write_text('{}'); (prior/'manifest.json').write_text('{}')
    jobs = [{'case': str(i), 'arm': 'facets', 'prompt': 'bound original instruction', 'evidence': {'pair': i},
             'image_pair_ref': str(i), 'image_hashes': [str(i)], 'schema': facets.schema()} for i in range(24)]
    (prior/'jobs.json').write_text(json.dumps(jobs))
    out = tmp_path/'out'; probe.prepare(prior, out)
    prepared = json.loads((out/'jobs.json').read_text())
    assert len(prepared) == 48
    for job in prepared:
        old = jobs[int(job['case'])]
        assert job['evidence'] == old['evidence'] and job['image_pair_ref'] == old['image_pair_ref']
        assert json.dumps(job['schema']) in job['prompt'] and job['prompt'].startswith(old['prompt'])
        if job['arm'].endswith('evidence_first'):
            assert list(job['schema']['properties'])[:2] == ['evidence', 'material_gap']
        else:
            assert list(job['schema']['properties'])[0] == 'new_requested_content'
