"""Eight-worker continuation of frozen observation slots with one shared budget."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fcntl
import hashlib
import json
import threading

from run.calitree_observation_repeats import MODEL, ROOT, prepare, read_jobs, sha, summarize
from run.calitree_observation50 import check_once
from tests.unit.calitree.assumption3_probe import (
    BudgetedEngine, BudgetExhausted, ProviderUnavailable, digest, save,
)
from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter
from pathlib import Path


class ThreadEngines:
    model = MODEL
    temperature = 0
    max_tokens = 1024

    def __init__(self, factory):
        self.factory = factory
        self.local = threading.local()

    def generate(self, prompt, **kwargs):
        if not hasattr(self.local, 'engine'):
            self.local.engine = self.factory()
            self.local.engine.max_http_attempts = 1
        return self.local.engine.generate(prompt, **kwargs)


class ConcurrentBudget(BudgetedEngine):
    """Reserve/save under lock, release the lock during the network request."""

    def __init__(self, engine, path, max_calls, completion_budget):
        self.lock = threading.RLock()
        super().__init__(engine, path, max_calls, completion_budget)

    @property
    def usage(self):
        with self.lock:
            return super().usage

    def generate(self, prompt, **kwargs):
        with self.lock:
            if len(self.records) >= self.max_calls:
                raise BudgetExhausted('Request allowance exhausted')
            if self.usage['completion_tokens_or_reserved'] + self.max_tokens > self.completion_budget:
                raise BudgetExhausted('Remaining completion budget cannot reserve a full request')
            record = {'request_sha256': digest({'prompt': prompt, 'kwargs': kwargs}),
                      'state': 'reserved', 'charged_completion': self.max_tokens}
            self.records.append(record)
            save(self.path, self.records)
        try:
            response = self.engine.generate(prompt, **kwargs)
        except BaseException as exc:
            with self.lock:
                record['state'] = 'failed_or_interrupted'
                save(self.path, self.records)
            if isinstance(exc, Exception):
                raise ProviderUnavailable(str(exc)) from exc
            raise
        with self.lock:
            used = response.get('completionTokens')
            record.update(state='complete', charged_completion=used if isinstance(used, int) and used >= 0 else self.max_tokens,
                          prompt_tokens=response.get('promptTokens', 0), finish_reason=response.get('finishReason'))
            save(self.path, self.records)
        return response


def execute_parallel(out, manifest, prior, factory, concurrency=8):
    if not 1 <= concurrency <= 8:
        raise ValueError('Concurrency must be between one and eight')
    records = dict(prior)
    new = read_jobs(out)
    if records.keys() & new.keys():
        raise ValueError('Extension overlaps original jobs')
    records.update(new)
    (out / 'jobs').mkdir(exist_ok=True)
    budget = ConcurrentBudget(ThreadEngines(factory), out / 'budget.json',
                              manifest['max_calls'], manifest['completion_budget'])
    jobs = iter((f'check/{rep}/{case}/{c["id"]}', row, c)
                for rep in manifest['new_repeat_indices']
                for case, row in manifest['rows'].items()
                for c in row['plan']['conditions']
                if f'check/{rep}/{case}/{c["id"]}' not in records)
    stop_reason = 'complete'
    consecutive_errors = 0

    def work(key, row, condition, path):
        try:
            value = {'job_id': key, **check_once(budget, row, condition)}
        except BudgetExhausted as exc:
            value = {'job_id': key, 'outcome': 'budget_exhausted', 'error': str(exc)}
        # Each worker durably completes its own slot, even while the coordinator
        # is draining requests after cancellation or a transport stop.
        save(path, value)
        return value

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = {}

        def fill():
            while len(pending) < concurrency and stop_reason == 'complete':
                item = next(jobs, None)
                if item is None:
                    break
                key, row, condition = item
                path = out / 'jobs' / (hashlib.sha256(key.encode()).hexdigest() + '.json')
                records[key] = {'job_id': key, 'outcome': 'interrupted_or_pending'}
                save(path, records[key])
                pending[pool.submit(work, key, row, condition, path)] = key

        fill()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: pending[f]):
                key = pending.pop(future)
                value = future.result()
                records[key] = value
                consecutive_errors = consecutive_errors + 1 if value['outcome'] == 'transport_error' else 0
                if consecutive_errors >= 3:
                    stop_reason = 'Three consecutive transport failures; drained in-flight calls'
                if value['outcome'] == 'budget_exhausted':
                    stop_reason = value['error']
                message = json.dumps({'job': key, 'outcome': value['outcome'], 'concurrency': concurrency, 'usage': budget.usage})
                print(message, flush=True)
                with (out / 'run.log').open('a') as log:
                    log.write(message + '\n')
            save(out / 'progress.json', summarize(manifest['rows'], records))
            fill()
    result = {'stop_reason': stop_reason, 'usage': budget.usage, 'summary': summarize(manifest['rows'], records)}
    save(out / 'results.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--concurrency', type=int, choices=range(1, 9), default=8)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    with (args.output_dir / 'parallel.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest, prior = prepare(ROOT / 'logs/exps/260929-22:30:00-exps', args.output_dir)
        path = args.output_dir / 'parallel_manifest.json'
        protocol = {'version': 'calitree-parallel-continuation-v1', 'concurrency': args.concurrency,
                    'driver_sha256': sha(__file__), 'base_manifest_sha256': sha(args.output_dir / 'manifest.json'),
                    'stop_rule': 'Stop dispatch after three consecutive completed transport errors; drain already dispatched calls.'}
        if path.exists() and json.loads(path.read_text()) != protocol:
            raise ValueError('Parallel protocol changed')
        save(path, protocol)
        completed = read_jobs(args.output_dir)
        print(json.dumps({'existing_slots': len(completed), 'remaining_slots': manifest['max_calls'] - len(completed),
                          'concurrency': args.concurrency, 'total_call_cap': manifest['max_calls']}), flush=True)
        if not args.live:
            return
        require_live(args.live, context='User requested concurrency eight for remaining authorized repeats')
        creds = load_creds(model=MODEL)
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI only')
        history = LLMHistoryWriter(args.output_dir / 'llm-histories.log')
        def factory():
            return get_engine('gpt', model=MODEL, creds=creds, temperature=0,
                              max_tokens=1024, timeout=60, history=history)
        result = execute_parallel(args.output_dir, manifest, prior, factory, args.concurrency)
        print(json.dumps({'stop_reason': result['stop_reason'], 'usage': result['usage'],
                          'metrics': result['summary']['metrics']}), flush=True)


if __name__ == '__main__':
    main()
