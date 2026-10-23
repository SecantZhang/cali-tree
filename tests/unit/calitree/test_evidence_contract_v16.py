from pathlib import Path
import json

import pytest

from critical.core.decision.artifacts import save_json
from critical.core.decision.bound_compiler_v3 import checked_program
from tests.unit.calitree.test_bound_compiler_v3 import valid
from tests.unit.calitree.test_bound_evidence import observation
from run import calitree_evidence_contract_v16 as runner


def setup(tmp_path, monkeypatch, fail=False):
    instruction, draft = valid(); program = checked_program(instruction, draft)
    source, edited = tmp_path / 'source.png', tmp_path / 'edited.png'
    source.write_bytes(b'source-test-bytes'); edited.write_bytes(b'edited-test-bytes')
    cases = [{'case': name, 'instruction': instruction, 'evidence': {'source_image': str(source), 'edited_image': str(edited)}} for name in ('T1', 'T2')]
    monkeypatch.setattr(runner, 'prepare', lambda _: {'cases': cases})
    save_json(tmp_path / 'programs.json', {r['case']: program for r in cases})
    save_json(tmp_path / 'prompts.json', {arm: {'observe': arm + '-observe', 'interpret': arm + '-interpret'} for arm in runner.ARMS})
    save_json(tmp_path / 'references.json', {'secret_reference': 'DO_NOT_SEND_REFERENCE'})
    calls = []
    class Fake:
        def generate(self, text, media_inputs, **kwargs):
            assert 'DO_NOT_SEND_REFERENCE' not in text
            payload = json.loads(text.split('INPUT_JSON: ', 1)[1]); calls.append((text, payload, media_inputs))
            if fail:
                raise RuntimeError('Synthetic provider failure')
            if 'program' in payload:
                assert set(payload) == {'program', 'image_pair_ref'}
                assert len(media_inputs) == 4
                value = observation(payload['program']); value['image_pair_ref'] = payload['image_pair_ref']
            else:
                assert not media_inputs
                value = {'evidence_ref': payload['evidence_ref'], 'requirements': {r['id']: {
                    'progress': 'requested_endpoint', 'endpoint_gap': 'none', 'retention_need': 'same_instance_essential',
                    'identity_evidence': 'same_instance', 'identity_materiality': 'no_shortfall', 'collateral_materiality': 'none',
                    'evidence_consistency': 'coherent', 'support_check_ids': [c['id'] for c in payload['checks']],
                    'explanation': 'Test-visible endpoint with the same counterpart.'} for r in payload['requirements']}}
            return {'parsed': value, 'finishReason': 'stop', 'completionTokens': 10, 'promptTokens': 20}
    monkeypatch.setattr(runner.base, 'model_factory', lambda *_: lambda cap: Fake())
    return calls


def test_no_live_flag_refuses_before_preflight_or_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'prepare', lambda _: pytest.fail('Unexpected preflight'))
    with pytest.raises(ValueError, match='explicit --live'):
        runner.collect(tmp_path)


def test_paired_arms_are_fresh_label_blind_and_resume_without_more_calls(tmp_path, monkeypatch):
    calls = setup(tmp_path, monkeypatch)
    runner.collect(tmp_path, True)
    assert len(calls) == 8
    prefixes = [text.split('\nINPUT_JSON:')[0] for text, _, _ in calls]
    assert sorted(prefixes) == sorted([arm + '-' + stage for arm in runner.ARMS for stage in ('observe', 'interpret') for _ in range(2)])
    rows = runner.base.read(tmp_path / 'observations.json')
    assert len(rows) == 4 and all(r['features'] is not None and r['error'] is None for r in rows)
    assert len(list(tmp_path.glob('ledgers/*/*/jobs/*.json'))) == 8
    runner.collect(tmp_path, True)
    assert len(calls) == 8


def test_failed_probe_is_retained_and_never_retried(tmp_path, monkeypatch):
    calls = setup(tmp_path, monkeypatch, fail=True)
    for _ in range(2):
        with pytest.raises(RuntimeError, match='probe'):
            runner.collect(tmp_path, True)
    assert len(calls) == 1
    jobs = list(tmp_path.glob('ledgers/*/*/jobs/*.json'))
    assert len(jobs) == 1 and runner.base.read(jobs[0])['outcome'] == 'transport_error'


def test_template_adapter_cannot_override_another_stage():
    wrapper = runner.ObserverCalls(None, 'clarification')
    with pytest.raises(ValueError, match='Only the observer'):
        wrapper.call('optimizer', {}, {})
