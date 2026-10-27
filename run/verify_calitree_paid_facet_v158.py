"""Audit native v155 paid slots, scope, recovery and full-denominator readouts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from critical.core.decision import facet_policy_v150 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_paid_facet_probe_v155 import verify, read, MAX_CALLS, MAX_TOKENS, MODELS, CAPS, ROOT
from run.verify_calitree_facet_probe_v151 import classification_metrics, scalar_grade


def media_identity(job):
    return [{'type': 'text', 'text': 'SOURCE image'},
             {'type': 'image', 'sha256': job['image_hashes']['source_image']},
             {'type': 'text', 'text': 'EDITED image'},
             {'type': 'image', 'sha256': job['image_hashes']['edited_image']}]


def execution_ref(job):
    media = media_identity(job)
    key = digest([job['identity'], job['case'], 'explicit_semantic_facets_v155', {}, job['schema'],
                  job['prompt'], media, job['arm'], job['max_tokens']])
    return digest([key, 'luna']) if job['arm'] == 'luna' else key


def audit(probe, out, *, allow_incomplete=False):
    if out.exists():
        raise ValueError('Fresh paid-facet audit required')
    verify(probe)
    manifest, authorization = read(probe/'manifest.json'), read(probe/'authorization.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(probe/'manifest.json')
    assert authorization['max_requests'] == MAX_CALLS and authorization['max_completion_tokens'] == MAX_TOKENS
    jobs = read(probe/'jobs.json'); expected = {execution_ref(j): j for j in jobs}; assert len(expected) == 48
    budget = read(probe/'ledger/budget.json'); attempted = budget['attempted_slots']
    assert len(attempted) == len(set(attempted)) == budget['calls'] <= MAX_CALLS
    assert set(attempted) <= set(expected)
    slot_files = {p.stem: p for p in (probe/'ledger/jobs').glob('*.json')}
    assert set(slot_files) == set(attempted)
    assert budget['limits']['identity'] == MODELS['sol'] and budget['limits']['routes']['luna'] == MODELS['luna']
    assert budget['limits']['max_calls'] == MAX_CALLS and budget['limits']['max_completion_tokens'] == MAX_TOKENS
    history = [json.loads(s) for s in (probe/'llm-histories.log').read_text().splitlines() if s.strip()]
    assert len(history) == len(attempted), 'Every terminal engine attempt must have a native history row'
    total = 0; input_tokens = 0; values = {}; checks = []; scopes = Counter()
    bound_files = [probe/'manifest.json', probe/'authorization.json', probe/'ledger/budget.json', probe/'llm-histories.log']
    for ref, h in zip(attempted, history):
        row = read(slot_files[ref]); job = expected[ref]; arm = job['arm']; bound_files.append(slot_files[ref])
        assert row['execution_ref'] == ref and row['case_id'] == job['case'] and row['slot'] == arm
        assert row['stage'] == 'explicit_semantic_facets_v155' and row['payload'] == {} and row['phase'] == 'search'
        assert row['media_identity'] == media_identity(job)
        assert row['max_tokens'] == job['max_tokens'] == CAPS[arm]
        assert row.get('route') == ('luna' if arm == 'luna' else None)
        assert h['prompt'] == job['prompt']+'\nINPUT_JSON: {}' and digest(h['prompt']) == job['wire_prompt_ref']
        assert h['model'] == MODELS[arm]['model'] or h['model'].startswith(MODELS[arm]['model']+'-')
        assert h['max_http_attempts'] == 1 and h['n_media'] == 4
        assert h['response_format']['json_schema']['strict'] is True
        assert h['response_format']['json_schema']['schema'] == job['schema']
        scope = (job['case'], row['phase']); scopes[scope] += 1; assert scopes[scope] <= 2
        path = probe/'responses'/(job['case']+'-'+arm+'.json')
        assert path.exists(); summary = read(path); bound_files.append(path)
        assert summary['request_ref'] == job['request_ref'] and summary['case'] == job['case'] and summary['arm'] == arm
        response = row.get('response')
        if response is None:
            total += row['max_tokens']
            assert row['outcome'] in ('transport_error', 'interrupted') and not summary['accepted']
            assert h['response'] is None and h['error']
        else:
            completion, prompt = response['completionTokens'], response['promptTokens']
            assert type(completion) is int and 0 <= completion <= CAPS[arm] and type(prompt) is int and prompt > 0
            assert response['endpointHost'] == 'api.openai.com'
            assert response['content'] == h['response'] and completion == h['completion_tokens'] and prompt == h['prompt_tokens']
            total += completion; input_tokens += prompt
            if summary['accepted']:
                assert row['outcome'] == 'completed' and response['finishReason'] == 'stop'
                v = facets.validate(json.loads(response['content']))
                assert v == row['parsed'] == summary['value'] == response['parsed']
                assert scalar_grade(v) == facets.decide(v)
                values[(job['case'], arm)] = v
        checks.append({'execution_ref': ref, 'case': job['case'], 'arm': arm, 'outcome': row['outcome'],
                       'accepted': summary['accepted'], 'completion_tokens_or_reserved': completion if response else row['max_tokens']})
    assert total == budget['completion_tokens_or_reserved'] <= MAX_TOKENS
    assert input_tokens == budget['input_tokens']
    for case, counters in budget['cases'].items():
        assert counters['search'] == scopes[(case, 'search')] and counters['final'] == 0
    recovery_path = probe/'credential_recovery.json'
    if recovery_path.exists():
        recovery = read(recovery_path); before = read(probe/'provider_stop_budget.json')
        assert recovery['prior_budget_sha256'] == file_hash(probe/'provider_stop_budget.json')
        assert before['limits'] == budget['limits'] and set(before['attempted_slots']) <= set(attempted)
        assert before['calls'] == 1 and recovery['remaining_max_requests'] == MAX_CALLS-1
        assert all(file_hash(path) == sha for path, sha in recovery['unchanged_failed_slot_sha256'].items())
        bound_files.extend([recovery_path, probe/'provider_stop_budget.json'])
    authenticated_recovery = probe/'authenticated_provider_recovery_v159.json'
    if authenticated_recovery.exists():
        event = read(authenticated_recovery); before = read(probe/'provider_stop_budget_v159.json')
        assert event['prior_budget_sha256'] == file_hash(probe/'provider_stop_budget_v159.json')
        assert before['calls'] == 2 and before['limits'] == budget['limits']
        assert set(before['attempted_slots']) <= set(attempted)
        assert event['remaining_max_requests'] == MAX_CALLS-before['calls']
        assert event['remaining_completion_tokens_or_reserved'] == MAX_TOKENS-before['completion_tokens_or_reserved']
        assert all(file_hash(path) == sha for path, sha in event['unchanged_failed_slot_sha256'].items())
        auth = read(event['auth_probe']); assert event['auth_probe_sha256'] == file_hash(event['auth_probe'])
        assert auth['http_status'] == 200 and auth['generation_requests'] == auth['image_uploads'] == 0
        adapter = read(probe/'execution_adapter_v157.json')
        assert adapter['parent_manifest_sha256'] == file_hash(probe/'manifest.json')
        assert adapter['credential_resolution'] == auth['credential_resolution']
        assert adapter['prompts_models_slots_limits_changed'] is False
        assert adapter['helper_sha256'] == file_hash(probe/'source_snapshot/run/calitree_paid_facet_credentials_v157.py')
        bound_files.extend([authenticated_recovery, probe/'provider_stop_budget_v159.json',
                            Path(event['auth_probe']), probe/'execution_adapter_v157.json'])
    refs = read(probe/'references_training_only.json'); rows = []
    for case, reference in refs.items():
        row = {'case': case, 'reference': reference}
        for arm in MODELS:
            v = values.get((case, arm)); grade = scalar_grade(v) if v else None
            row[arm] = grade if grade is not None else -1
        rows.append(row)
    complete = len(attempted) == len(jobs)
    if not allow_incomplete:
        assert complete, 'Use --allow-incomplete only for a transport/budget audit, not an accuracy claim'
    report = {'passed': True, 'complete': complete, 'planned_cases': 24, 'planned_generation_slots': 48,
        'generation_attempts': len(attempted), 'valid_observations': len(values),
        'completion_tokens_or_reserved': total, 'reported_input_tokens': input_tokens,
        'remaining_max_generation_requests': MAX_CALLS-len(attempted), 'remaining_completion_tokens': MAX_TOKENS-total,
        'stopped': budget['stopped'], 'failed_slots_retried': 0,
        'metrics': {arm: classification_metrics(rows, arm) for arm in MODELS} if complete else None,
        'scope': 'Adapted training-only observer diagnostic. Incomplete authentication runs have no model-accuracy result.',
        'new_api_calls_in_audit': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'verification.json', report); save_json(out/'checks.json', checks)
    if complete:
        save_json(out/'predictions.json', rows)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__),
        'bound_input_sha256': {str(p): file_hash(p) for p in bound_files}, 'protocol_ref': manifest['protocol_ref']})
    (out/'run.log').write_text('Native paid slots, wire/history bindings, accounting and preserved failure records audited.\n')
    (out/'llm-histories.log').write_text('No API or neural calls during audit.\n')
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args(); audit(a.probe.resolve(), a.output_dir.resolve(), allow_incomplete=a.allow_incomplete)
