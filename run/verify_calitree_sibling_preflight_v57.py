"""Rehearse all 540 case ledgers with four workers and mocked model engines."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import patch

from critical.core.decision.artifacts import save_json
from run import calitree_sibling_training_v57 as sibling
from run.calitree_aurora_pilot_v29 import read, fingerprint


def audit(prepared, out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    sibling.verify(prepared)
    assert not (prepared / 'authorization.json').exists() and not (prepared / 'case_ledgers').exists()
    counter_lock, first_four = Lock(), Barrier(4)
    calls, active, maximum = [], 0, 0
    def get_engine(name, **kwargs):
        class MockEngine:
            def generate(self, prompt, *, media_inputs, schema, strict_schema):
                nonlocal active, maximum
                payload = json.loads(prompt.split('\nINPUT_JSON: ', 1)[1])
                with counter_lock:
                    first = len(calls) < 4
                    calls.append({'cap': kwargs['max_tokens'], 'model': kwargs['model']})
                    active += 1
                    maximum = max(maximum, active)
                if first:
                    first_four.wait(timeout=30)
                try:
                    if 'program' in payload:
                        program = payload['program']
                        value = {'program_ref': program['program_ref'], 'image_pair_ref': payload['image_pair_ref'], 'checks': {}}
                        for check in program['checks']:
                            value['checks'][check['id']] = {'check_ref': check['check_ref'], 'question': check['question'],
                                'state': check['expected_state'], 'applicability': 'applicable', 'source_anchor': 'identified',
                                'edited_coverage': 'adequate', 'source_evidence': 'Mock source observation.',
                                'edited_evidence': 'Mock edited observation.', 'comparison': 'Mock comparison, no real image judgment.'}
                    elif 'evidence_ref' in payload:
                        value = {'evidence_ref': payload['evidence_ref'], 'requirements': {}}
                        for requirement in payload['requirements']:
                            value['requirements'][requirement['id']] = {
                                'progress': 'requested_endpoint', 'endpoint_gap': 'none', 'retention_need': 'same_instance_essential',
                                'identity_evidence': 'same_instance', 'identity_materiality': 'no_shortfall',
                                'collateral_materiality': 'none', 'evidence_consistency': 'coherent',
                                'support_check_ids': [c['id'] for c in payload['checks'] if requirement['id'] in c['requirement_ids']],
                                'explanation': 'Mock semantic interpretation for collection plumbing only.'}
                    else:
                        assert set(payload) == {'instruction'}
                        value = {'label': 'no', 'rationale': 'Mock regular judgment, not a real result.'}
                    return {'parsed': value, 'promptTokens': 1000, 'completionTokens': 100, 'finishReason': 'stop'}
                finally:
                    with counter_lock:
                        active -= 1
        return MockEngine()
    with TemporaryDirectory(prefix='calitree-sibling-preflight-') as temp:
        fixture = Path(temp) / 'fixture'
        shutil.copytree(prepared, fixture)
        save_json(fixture / 'authorization.json', {'test_only': True, 'protocol_sha256': fingerprint(fixture / 'protocol.json')})
        with patch('critical.lm_engine.load_creds', return_value=SimpleNamespace(endpoints=['https://api.openai.com/v1'])), \
             patch('critical.lm_engine.get_engine', side_effect=get_engine), \
             patch('critical.lm_engine.require_live', return_value=None):
            sibling.collect(fixture, live=True)
        assert len(calls) == 1620 and maximum == 4
        assert Counter(c['cap'] for c in calls) == {16384: 540, 8192: 540, 2048: 540}
        assert {c['model'] for c in calls} == {'gpt-6-luna'}
        budgets = [read(p) for p in (fixture / 'case_ledgers').glob('*/budget.json')]
        assert len(budgets) == 540 and sum(b['calls'] for b in budgets) == 1620
        assert all(b['calls'] == 3 and b['completion_tokens_or_reserved'] == 300 for b in budgets)
        assert all(b['limits']['max_calls'] == 3 and b['limits']['max_completion_tokens'] == sibling.CASE_CAP for b in budgets)
        assert read(fixture / 'results.json')['valid_feature_cases'] == 540
        assert len(read(fixture / 'training_data.json')) == 540
        assert not (prepared / 'authorization.json').exists() and not (prepared / 'case_ledgers').exists()
    out.mkdir(parents=True)
    result = {'passed': True, 'new_real_model_calls': 0, 'simulated_requests': len(calls), 'simulated_case_ledgers': 540,
              'maximum_concurrent_mock_requests': maximum, 'compiler_calls': 0, 'real_authorization_created': False,
              'aggregate_cap_proved': {'requests': sibling.MAX_CALLS, 'completion_tokens': sibling.MAX_OUTPUT},
              'scope': 'Mocked credential access and engines; full 540-output plumbing/budget rehearsal, not accuracy data.'}
    save_json(out / 'verification.json', result)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'prepared_manifest_sha256': fingerprint(prepared / 'manifest.json')})
    (out / 'run.log').write_text('All 1,620 simulated slots completed in 540 disjoint case ledgers with four concurrent mock calls. No network, credentials or real authorization. Temporary mock training data removed.\n')
    (out / 'llm-histories.log').write_text('Zero real model calls; mocked responses only.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.prepared_dir.resolve(), args.output_dir.resolve())
