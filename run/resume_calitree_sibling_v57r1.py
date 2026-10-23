"""Continue unattempted stages after a retained SSL transport-stop epoch.

No failed slot is retried; all original ledgers, caps, programs, failures and
stop records remain. The original human authorization covers these unfinished
outputs. A new stop epoch applies the same shared three-error transport guard.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from pathlib import Path

from critical.core.decision.artifacts import save_json
from run import calitree_sibling_training_v57 as sibling
from run.calitree_aurora_pilot_v29 import read, fingerprint, exact

STAGES = {'bound_visual_observation_v2': 16384, 'instruction_relative_interpretation': 8192, 'flat_judge': 2048}


def prepare(out):
    sibling.verify(out)
    recovery = out / 'continuation_r1'
    if recovery.exists():
        raise ValueError('Fresh continuation directory required')
    assert read(out / 'provider_stop.json')['reason'] == 'three_consecutive_transport_failures'
    assert not (out / 'results.json').exists()
    entries = read(out / 'inputs_without_labels.json')
    pending, prior_calls, prior_tokens, hashes = [], 0, 0, {}
    for e in entries:
        directory = out / 'case_ledgers' / e['case']
        existing = {}
        if directory.exists():
            b = read(directory / 'budget.json')
            assert b['limits']['identity'] == sibling.IDENTITY
            assert b['limits']['max_calls'] == 3 and b['limits']['max_completion_tokens'] == sibling.CASE_CAP
            prior_calls += b['calls']
            prior_tokens += b['completion_tokens_or_reserved']
            for p in (directory / 'jobs').glob('*.json'):
                j = read(p)
                assert j['outcome'] in ('completed', 'transport_error', 'invalid')
                existing[j['stage']] = j['outcome']
                hashes[str(p.relative_to(out))] = fingerprint(p)
        path = out / 'cases' / (e['case'] + '.json')
        if path.exists():
            hashes[str(path.relative_to(out))] = fingerprint(path)
        else:
            assert not b.get('stopped') if directory.exists() else True
            pending.append({'case': e['case'], 'existing_stages': existing,
                            'allowed_new_stages': sorted(set(STAGES) - set(existing))})
    new_calls = sum(len(e['allowed_new_stages']) for e in pending)
    new_tokens = sum(STAGES[s] for e in pending for s in e['allowed_new_stages'])
    assert prior_calls + new_calls <= sibling.MAX_CALLS and prior_tokens + new_tokens <= sibling.MAX_OUTPUT
    for name in ('provider_stop.json', 'incomplete.json', 'authorization.json'):
        hashes[name] = fingerprint(out / name)
    recovery.mkdir()
    save_json(recovery / 'plan.json', {'pending': pending, 'prior_calls': prior_calls,
              'prior_completion_tokens_or_reserved': prior_tokens, 'maximum_new_slots': new_calls,
              'maximum_new_completion_allowance': new_tokens, 'maximum_total_slots': prior_calls + new_calls,
              'original_request_cap': sibling.MAX_CALLS, 'original_completion_cap': sibling.MAX_OUTPUT,
              'workers': 4, 'transport_retries': 0, 'original_authorization_sha256': fingerprint(out / 'authorization.json'),
              'reason': 'Original epoch stopped on consecutive SSL transport failures; unauthenticated official-API TLS check succeeded. Continue only unattempted stages under the original approval, without clearing the original stop latch.',
              'old_immutable_hashes': hashes,
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, sibling.__file__)}})
    (recovery / 'run.log').write_text('Prepared continuation of unattempted stages under original authorization. Original stop and failures retained.\n')
    (recovery / 'llm-histories.log').write_text('Histories remain in original per-case ledgers; no new model calls in preparation.\n')
    print({'pending_outputs': len(pending), 'prior_slots': prior_calls, 'max_new_slots': new_calls,
           'maximum_total_slots': prior_calls + new_calls, 'no_failed_slot_retries': True}, flush=True)


def verify(out):
    sibling.verify(out)
    recovery = out / 'continuation_r1'
    plan = read(recovery / 'plan.json')
    assert plan['original_authorization_sha256'] == fingerprint(out / 'authorization.json')
    auth = read(out / 'authorization.json')
    assert auth['authorized'] and auth['max_requests'] == sibling.MAX_CALLS and auth['max_completion_tokens'] == sibling.MAX_OUTPUT
    for p, sha in plan['old_immutable_hashes'].items():
        assert fingerprint(out / p) == sha, p
    for p, sha in plan['code_hashes'].items():
        assert fingerprint(p) == sha, p
    for p, sha in read(out / 'preflight_seal.json')['files'].items():
        assert fingerprint(out / p) == sha, p
    return plan


def collect(out, live=False):
    if not live:
        raise ValueError('--live and original paid authorization required')
    plan = verify(out)
    recovery = out / 'continuation_r1'
    assert read(recovery / 'preflight.json')['passed'] is True
    circuit = sibling.StopCircuit(recovery / 'provider_stop.json')
    circuit.check()
    from critical import config
    from critical.core.decision.calls import DurableCalls
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT, config.CREDENTIALS_FILE = sibling.SOURCE_ROOT, sibling.SOURCE_ROOT / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official endpoint required')
    entries = {e['case']: e for e in read(out / 'inputs_without_labels.json')}
    programs = read(out / 'programs.json')
    def work(item):
        e = entries[item['case']]
        path = out / 'cases' / (e['case'] + '.json')
        if path.exists():
            return
        circuit.check()
        directory = out / 'case_ledgers' / e['case']
        def factory(cap):
            engine = get_engine('gpt', creds=creds, model=sibling.IDENTITY['model'], temperature=0, max_tokens=cap,
                                timeout=180, max_http_attempts=1, history=LLMHistoryWriter(directory / 'llm-histories.log'))
            class GuardedEngine:
                def generate(self, *args, **kwargs):
                    circuit.check()
                    try:
                        value = engine.generate(*args, **kwargs)
                    except Exception as exc:
                        circuit.failure(exc)
                        raise
                    circuit.success()
                    return value
            return GuardedEngine()
        ledger = DurableCalls(directory, factory, identity=sibling.IDENTITY, max_calls=3,
                              max_completion_tokens=sibling.CASE_CAP, scope_limits={'search': 3, 'final': 0})
        class AllowedCalls:
            def call(self, stage, *args, **kwargs):
                if stage not in item['existing_stages'] and stage not in item['allowed_new_stages']:
                    raise ValueError('Unapproved continuation stage')
                return ledger.call(stage, *args, **kwargs)
        result = sibling.run_case(e, programs[e['task_uid']]['program'], AllowedCalls(), circuit)
        exact(path, result)
        print({'case': e['case'], 'extraction_error': result['extraction_error'], 'regular_error': result['regular_error']}, flush=True)
    with (out / 'collection.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        failures = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(work, item): item['case'] for item in plan['pending']}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    failures.append({'case': futures[future], 'error': type(exc).__name__})
        if failures:
            save_json(recovery / 'incomplete.json', {'worker_failures': failures, 'provider_stopped': circuit.stopped})
            raise RuntimeError('Continuation stopped; never retry a failed slot')
    # All pre-stop records are byte-identical, including failed slots and the
    # original global stop latch. Only unfinished budgets were appended.
    for p, sha in plan['old_immutable_hashes'].items():
        assert fingerprint(out / p) == sha, p
    sibling.report(out)
    save_json(recovery / 'completion.json', {'completed': True, 'no_failed_slot_retries': True,
              'aggregate_requests': read(out / 'results.json')['requests'], 'original_budget_unchanged': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    prepare(args.output_dir.resolve()) if args.prepare else collect(args.output_dir.resolve(), args.live)
