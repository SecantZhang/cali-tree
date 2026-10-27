"""Resume unattempted v155 slots after a positive, non-generating auth check."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_paid_facet_probe_v155 import verify, read, ENDPOINT, MAX_CALLS, MAX_TOKENS


def recover(out, auth_probe):
    verify(out)
    if (out/'authenticated_provider_recovery_v159.json').exists():
        raise ValueError('Authenticated recovery already recorded')
    auth = read(auth_probe)
    assert auth['method'] == 'GET' and auth['endpoint'] == ENDPOINT+'/models' and auth['http_status'] == 200
    assert auth['generation_requests'] == auth['image_uploads'] == 0
    assert all(auth['requested_models_listed'].values()) and len(auth['requested_models_listed']) == 2
    authorization = read(out/'authorization.json')
    assert authorization['approved'] is True and authorization['upload_approved'] is True
    assert authorization['manifest_sha256'] == file_hash(out/'manifest.json')
    path = out/'ledger/budget.json'; before = read(path)
    assert before['stopped'] == 'Provider rejected the request'
    assert before['limits']['max_calls'] == authorization['max_requests'] == MAX_CALLS
    assert before['limits']['max_completion_tokens'] == authorization['max_completion_tokens'] == MAX_TOKENS
    slots = sorted((out/'ledger/jobs').glob('*.json')); summaries = sorted((out/'responses').glob('*.json'))
    assert before['calls'] == len(slots) == len(summaries) == len(set(before['attempted_slots'])) == 2
    for p in slots:
        row = read(p)
        assert row['outcome'] == 'transport_error' and 'HTTP 401' in row['error']
        assert row['execution_ref'] in before['attempted_slots']
    assert all(not read(p)['accepted'] for p in summaries)
    hashes = {str(p): file_hash(p) for p in [*slots, *summaries]}
    save_json(out/'provider_stop_budget_v159.json', before)
    save_json(out/'authenticated_provider_recovery_v159.json', {
        'reason': 'User supplied the refreshed worktree.env; official non-generating auth check now succeeds.',
        'auth_probe_sha256': file_hash(auth_probe), 'auth_probe': str(auth_probe),
        'prior_budget_sha256': file_hash(out/'provider_stop_budget_v159.json'),
        'unchanged_failed_slot_sha256': hashes, 'failed_slots_retried': 0, 'limits_changed': False,
        'remaining_max_requests': MAX_CALLS-before['calls'],
        'remaining_completion_tokens_or_reserved': MAX_TOKENS-before['completion_tokens_or_reserved'],
        'helper_sha256': file_hash(__file__)})
    after = deepcopy(before); after['stopped'] = None; after['consecutive_errors'] = 0
    save_json(path, after)
    assert all(file_hash(p) == sha for p, sha in hashes.items())
    destination = out/'source_snapshot/run'/Path(__file__).name; destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, destination)
    print({'provider_recovered': True, 'retained_failed_slots': 2,
        'remaining_requests': MAX_CALLS-before['calls'],
        'remaining_completion_tokens': MAX_TOKENS-before['completion_tokens_or_reserved']}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--auth-probe', type=Path, required=True); a = p.parse_args()
    recover(a.output_dir.resolve(), a.auth_probe.resolve())
