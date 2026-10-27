"""Record credential recovery without retrying a rejected v155 request slot."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_paid_facet_probe_v155 import verify, read, MAX_CALLS, MAX_TOKENS


def recover(out, human_evidence):
    verify(out)
    if (out/'credential_recovery.json').exists():
        raise ValueError('Credential recovery event already recorded')
    evidence = read(human_evidence)
    if evidence.get('answer') != 'Key refreshed' or not evidence.get('question_item_id'):
        raise ValueError('Explicit credential-refresh user reply required')
    authorization = read(out/'authorization.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(out/'manifest.json')
    budget_path = out/'ledger/budget.json'; before = read(budget_path)
    assert before['stopped'] == 'Provider rejected the request'
    assert before['limits']['max_calls'] == authorization['max_requests'] == MAX_CALLS
    assert before['limits']['max_completion_tokens'] == authorization['max_completion_tokens'] == MAX_TOKENS
    slots = sorted((out/'ledger/jobs').glob('*.json'))
    # Only the observed initial expired-key rejection is eligible for this
    # one-shot recovery. Every failed slot remains present and non-retryable.
    assert before['calls'] == len(slots) == len(before['attempted_slots']) == 1
    rejected = read(slots[0]); assert rejected['outcome'] == 'transport_error'
    assert 'expired_secret_key' in rejected['error'] and rejected['execution_ref'] == before['attempted_slots'][0]
    assert before['completion_tokens_or_reserved'] == rejected['max_tokens'] == 2048
    responses = sorted((out/'responses').glob('*.json')); assert len(responses) == 1
    failed = read(responses[0]); assert failed['accepted'] is False
    response_hashes = {str(p): file_hash(p) for p in [*slots, *responses]}
    save_json(out/'provider_stop_budget.json', before)
    event = {'reason': 'Human refreshed expired OpenAI credential; clear only the global provider stop latch.',
        'human_evidence': evidence, 'prior_budget_sha256': file_hash(out/'provider_stop_budget.json'),
        'unchanged_failed_slot_sha256': response_hashes,
        'remaining_max_requests': MAX_CALLS-before['calls'],
        'remaining_completion_tokens_or_reserved': MAX_TOKENS-before['completion_tokens_or_reserved'],
        'failed_slots_retried': 0, 'limits_changed': False, 'new_requests_in_recovery': 0,
        'helper_sha256': file_hash(__file__)}
    save_json(out/'credential_recovery.json', event)
    after = deepcopy(before); after['stopped'] = None; after['consecutive_errors'] = 0
    save_json(budget_path, after)
    assert all(file_hash(path) == sha for path, sha in response_hashes.items())
    destination = out/'source_snapshot/run'/Path(__file__).name; destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, destination)
    print({'recovered_provider_latch': True, 'failed_slots_retried': 0,
        'remaining_max_requests': event['remaining_max_requests'],
        'remaining_completion_tokens': event['remaining_completion_tokens_or_reserved']}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--human-evidence', type=Path, required=True); a = p.parse_args()
    recover(a.output_dir.resolve(), a.human_evidence.resolve())
