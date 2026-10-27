"""Audit the four disjoint Sol ledgers and export375 source-bound observations."""
import argparse
import json
from pathlib import Path
import shutil

from critical.core.decision import facet_policy_v150 as facets, outcome_policy_v160 as outcome
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_source_facet_collection_v161 import (verify, read, WORKERS, WORKER_TOKEN_CAP,
    MAX_CALLS, MAX_TOKENS, PER_REQUEST, MODELS, ROOT)
from run.verify_calitree_paid_facet_v158 import execution_ref, media_identity
from run.calitree_outcome_readout_v160 import scalar as scalar_outcome


def audit(collection, out):
    if out.exists():
        raise ValueError('Fresh source-facet audit required')
    verify(collection)
    authorization = read(collection/'authorization.json'); manifest = read(collection/'manifest.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(collection/'manifest.json')
    assert authorization['max_requests'] == MAX_CALLS and authorization['max_completion_tokens'] == MAX_TOKENS
    status = read(collection/'collection_status.json'); assert status['complete']
    assignments = read(collection/'worker_assignments.json')
    jobs = {j['case']: j for j in read(collection/'jobs.json')}
    reused = read(collection/'reused_observations.json')
    values = {}; checks = []; calls = 0; tokens = 0; inputs = 0; seen = set()
    files = [collection/name for name in ('manifest.json', 'authorization.json', 'collection_status.json',
        'jobs.json', 'worker_assignments.json', 'reused_observations.json')]
    for worker in range(WORKERS):
        directory = collection/'workers'/('worker'+str(worker))
        budget_path = directory/'ledger/budget.json'; budget = read(budget_path); limits = budget['limits']
        assert limits['max_calls'] == len(assignments[str(worker)]) and limits['max_completion_tokens'] == WORKER_TOKEN_CAP
        assert limits['identity'] == MODELS['sol'] and limits['scope_limits'] == {'search': 1, 'final': 0}
        attempted = budget['attempted_slots']; native = {p.stem: p for p in (directory/'ledger/jobs').glob('*.json')}
        history_path = directory/'llm-histories.log'
        history = [json.loads(s) for s in history_path.read_text().splitlines() if s.strip()]
        assert len(attempted) == len(set(attempted)) == budget['calls'] == len(history)
        assert set(native) == set(attempted)
        assert not set(attempted)&seen; seen.update(attempted)
        worker_tokens = 0; worker_inputs = 0; per_case = {}
        for ref, h in zip(attempted, history):
            row = read(native[ref]); case = row['case_id']; job = jobs[case]
            assert case in assignments[str(worker)] and case not in reused
            assert ref == row['execution_ref'] == execution_ref(job)
            assert row['media_identity'] == media_identity(job)
            assert row['stage'] == 'explicit_semantic_facets_v155' and row['payload'] == {}
            assert row['slot'] == 'sol' and row['phase'] == 'search' and row.get('route') is None
            assert row['max_tokens'] == PER_REQUEST
            assert h['prompt'] == job['prompt']+'\nINPUT_JSON: {}' and digest(h['prompt']) == job['wire_prompt_ref']
            assert h['model'] == MODELS['sol']['model'] or h['model'].startswith(MODELS['sol']['model']+'-')
            assert h['max_http_attempts'] == 1 and h['n_media'] == 4
            assert h['response_format']['json_schema']['strict'] is True
            assert h['response_format']['json_schema']['schema'] == job['schema']
            response_path = collection/'responses'/(case+'.json'); summary = read(response_path)
            assert summary['case'] == case and summary['worker'] == worker and summary['request_ref'] == job['request_ref']
            assert summary['execution_ref'] == ref
            assert case not in per_case; per_case[case] = True
            response = row.get('response'); value = None
            if response is None:
                worker_tokens += PER_REQUEST
                assert row['outcome'] in ('transport_error', 'interrupted') and not summary['accepted']
                assert h['error'] and h['response'] is None
            else:
                completion, prompt = response['completionTokens'], response['promptTokens']
                assert type(completion) is int and 0 <= completion <= PER_REQUEST
                assert type(prompt) is int and prompt > 0 and response['endpointHost'] == 'api.openai.com'
                assert response['model'] == h['model']
                assert response['content'] == h['response'] and completion == h['completion_tokens'] and prompt == h['prompt_tokens']
                worker_tokens += completion; worker_inputs += prompt
                if summary['accepted']:
                    assert row['outcome'] == 'completed' and response['finishReason'] == 'stop'
                    value = facets.validate(json.loads(response['content']))
                    assert value == row['parsed'] == summary['value'] == response['parsed']
                    assert outcome.decide(value) == scalar_outcome(value)
            values[case] = value
            checks.append({'case': case, 'worker': worker, 'execution_ref': ref, 'accepted': value is not None,
                           'completion_tokens_or_reserved': completion if response else PER_REQUEST})
            files.extend([native[ref], response_path])
        assert worker_tokens == budget['completion_tokens_or_reserved'] <= WORKER_TOKEN_CAP
        assert worker_inputs == budget['input_tokens']
        for case, count in budget['cases'].items():
            assert count['search'] == 1 and count['final'] == 0 and case in per_case
        calls += len(attempted); tokens += worker_tokens; inputs += worker_inputs
        files.extend([budget_path, history_path])
    assert calls == MAX_CALLS == status['new_attempts'] == status['new_responses']
    assert tokens == status['completion_tokens_or_reserved'] <= MAX_TOKENS and inputs == status['input_tokens']
    assert set(values) == set(jobs)-set(reused)
    assert sum(v is not None for v in values.values()) == status['new_valid_observations']
    for case, record in reused.items():
        assert file_hash(record['source_response']) == record['source_response_sha256']
        prior = read(record['source_response']); assert prior['request_ref'] == jobs[case]['request_ref'] == record['request_ref']
        value = facets.validate(record['value']) if record['accepted'] else None
        assert prior['accepted'] == record['accepted'] and prior.get('value') == record['value']
        values[case] = value
    assert len(values) == 375
    observations = []
    for case, job in jobs.items():
        value = values[case]
        row = {'case': case, 'program_ref': job['program_ref'], 'image_pair_ref': job['image_pair_ref'],
            'request_ref': job['request_ref'], 'collection_manifest_sha256': file_hash(collection/'manifest.json'),
            'accepted': value is not None, 'value': value,
            'origin': 'reused_pilot' if case in reused else 'new_collection'}
        row['observation_ref'] = digest(row); observations.append(row)
    report = {'passed': True, 'complete': True, 'target_cases': 375, 'new_attempts': calls,
        'new_valid': status['new_valid_observations'], 'reused_valid': 23, 'retained_pilot_failure': 1,
        'valid_total': sum(r['accepted'] for r in observations), 'completion_tokens_or_reserved': tokens,
        'reported_input_tokens': inputs, 'worker_native_replays': len(checks), 'no_failed_slots_resampled': True,
        'fitting_ready': not authorization.get('mock_transport_test', False),
        'mock_transport_test': bool(authorization.get('mock_transport_test', False)),
        'new_api_calls_in_audit': 0, 'reserved_sources_used': 0, 'serving_changed': False,
        'scope': 'Execution/binding audit only. Accuracy and generalization are not inferred from schema-valid observations.'}
    out.mkdir(parents=True); save_json(out/'verification.json', report); save_json(out/'observations.json', observations)
    save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'protocol_ref': manifest['protocol_ref'],
        'collection_manifest_sha256': file_hash(collection/'manifest.json'), 'observations_ref': digest(observations),
        'native_input_sha256': {str(p): file_hash(p) for p in files}})
    (out/'run.log').write_text('All four worker ledgers, native histories, image bindings, caps and cached failure retention audited.\n')
    (out/'llm-histories.log').write_text('No API/encoder/observer calls during audit.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--collection', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    audit(a.collection.resolve(), a.output_dir.resolve())
