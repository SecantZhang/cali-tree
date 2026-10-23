"""Mock the unfinished output stages while preserving every pre-stop slot."""
import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import patch

from critical.core.decision.artifacts import save_json
from run import resume_calitree_sibling_v57r1 as resume
from run.calitree_aurora_pilot_v29 import read, fingerprint


def audit(out):
    plan = resume.verify(out)
    target = out / 'continuation_r1/preflight.json'
    assert not target.exists()
    count, active, maximum = 0, 0, 0
    lock, first_four = Lock(), Barrier(4)
    def factory(name, **kwargs):
        class MockEngine:
            def generate(self, prompt, *, media_inputs, schema, strict_schema):
                nonlocal count, active, maximum
                payload = json.loads(prompt.split('\nINPUT_JSON: ', 1)[1])
                with lock:
                    first = count < 4
                    count += 1
                    active += 1
                    maximum = max(active, maximum)
                if first:
                    first_four.wait(timeout=30)
                try:
                    if 'program' in payload:
                        p = payload['program']
                        value = {'program_ref': p['program_ref'], 'image_pair_ref': payload['image_pair_ref'],
                                 'checks': {c['id']: {'check_ref': c['check_ref'], 'question': c['question'],
                                   'state': c['expected_state'], 'applicability': 'applicable', 'source_anchor': 'identified',
                                   'edited_coverage': 'adequate', 'source_evidence': 'Mock source.',
                                   'edited_evidence': 'Mock edit.', 'comparison': 'Mock comparison.'} for c in p['checks']}}
                    elif 'evidence_ref' in payload:
                        value = {'evidence_ref': payload['evidence_ref'], 'requirements': {r['id']: {
                                   'progress': 'requested_endpoint', 'endpoint_gap': 'none', 'retention_need': 'same_instance_essential',
                                   'identity_evidence': 'same_instance', 'identity_materiality': 'no_shortfall',
                                   'collateral_materiality': 'none', 'evidence_consistency': 'coherent',
                                   'support_check_ids': [c['id'] for c in payload['checks'] if r['id'] in c['requirement_ids']],
                                   'explanation': 'Mock plumbing interpretation.'} for r in payload['requirements']}}
                    else:
                        value = {'label': 'no', 'rationale': 'Mock response, not real accuracy data.'}
                    return {'parsed': value, 'promptTokens': 1000, 'completionTokens': 100, 'finishReason': 'stop'}
                finally:
                    with lock:
                        active -= 1
        return MockEngine()
    with TemporaryDirectory(prefix='calitree-continuation-rehearsal-') as temporary:
        fixture = Path(temporary) / 'fixture'
        shutil.copytree(out, fixture)
        save_json(fixture / 'continuation_r1/preflight.json', {'passed': True, 'mock_fixture_only': True})
        with patch('critical.lm_engine.load_creds', return_value=SimpleNamespace(endpoints=['https://api.openai.com/v1'])), \
             patch('critical.lm_engine.get_engine', side_effect=factory), \
             patch('critical.lm_engine.require_live', return_value=None):
            resume.collect(fixture, live=True)
        assert count == plan['maximum_new_slots'] == 596 and maximum == 4
        assert read(fixture / 'results.json')['requests'] == plan['maximum_total_slots'] == 1615
        assert len(read(fixture / 'training_data.json')) == 540
        # Both incomplete cases retain their original extraction slots: S0339
        # reuses successful observation/interpretation; S0340's failed
        # interpretation stays failed and gets no second model request.
        assert read(fixture / 'cases/S0340.json')['features'] is None
        assert read(fixture / 'cases/S0339.json')['features'] is not None
        assert read(fixture / 'provider_stop.json')['reason'] == 'three_consecutive_transport_failures'
        assert not (out / 'results.json').exists()
    result = {'passed': True, 'simulated_new_requests': count, 'new_real_model_calls': 0,
              'maximum_concurrent_mock_requests': maximum, 'maximum_total_slots': 1615,
              'prior_slots_byte_identical': True, 'original_stop_latch_retained': True,
              'failed_slots_retried': 0, 'mock_training_data_discarded': True, 'auditor_sha256': fingerprint(__file__)}
    save_json(target, result)
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
