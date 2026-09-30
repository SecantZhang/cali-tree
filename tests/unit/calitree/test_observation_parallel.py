from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import threading

import pytest

from run.calitree_observation_parallel import ConcurrentBudget, execute_parallel
from tests.unit.calitree.assumption3_probe import BudgetExhausted
from .test_observation50 import row
from .test_casewise_fitting import Engine, check


@pytest.mark.parametrize('max_calls,tokens', [(3, 999999), (100, 3072)])
def test_shared_budget_cannot_overspend_under_contention(tmp_path, max_calls, tokens):
    barrier = threading.Barrier(3)
    class Concurrent(Engine):
        max_tokens = 1024
        def generate(self, prompt, **kwargs):
            barrier.wait(timeout=3)
            return {'completionTokens': 1024, 'promptTokens': 1}
    budget = ConcurrentBudget(Concurrent([]), tmp_path / 'budget.json', max_calls, tokens)
    def call(i):
        try:
            budget.generate(str(i))
            return 'completed'
        except BudgetExhausted:
            return 'blocked'
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))
    assert results.count('completed') == 3
    assert budget.usage['calls'] == 3
    assert budget.usage['completion_tokens_or_reserved'] == 3072
    assert len(json.loads((tmp_path / 'budget.json').read_text())) == 3


def test_eight_workers_checkpoint_unique_jobs_and_resume_without_calls(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    rows = {f'C{i}': deepcopy(row(tmp_path)) for i in range(8)}
    barrier = threading.Barrier(8)
    seen = []; lock = threading.Lock()
    class Concurrent(Engine):
        def generate(self, prompt, **kwargs):
            assert self.max_http_attempts == 1
            with lock: seen.append(threading.get_ident())
            barrier.wait(timeout=3)
            return {'parsed': check('complete'), 'completionTokens': 5, 'promptTokens': 10}
    manifest = {'rows': rows, 'new_repeat_indices': [2], 'max_calls': 8, 'completion_budget': 8192}
    result = execute_parallel(out, manifest, {}, lambda: Concurrent([]), 8)
    assert len(set(seen)) == 8
    assert result['usage']['calls'] == 8 and result['stop_reason'] == 'complete'
    assert len(list((out / 'jobs').glob('*.json'))) == 8
    assert all(c['predictions'][2] == 'yes' for c in result['summary']['cases'].values())
    assert execute_parallel(out, manifest, {}, lambda: Engine([]), 8) == result


def test_parallel_continuation_keeps_interrupted_slot(tmp_path):
    import hashlib
    out = tmp_path / 'out'; (out / 'jobs').mkdir(parents=True)
    key = 'check/2/case/c1'
    (out / 'jobs' / (hashlib.sha256(key.encode()).hexdigest() + '.json')).write_text(
        json.dumps({'job_id': key, 'outcome': 'interrupted_or_pending'}))
    manifest = {'rows': {'case': row(tmp_path)}, 'new_repeat_indices': [2, 3, 4],
                'max_calls': 3, 'completion_budget': 3072}
    result = execute_parallel(out, manifest, {}, lambda: Engine([check('partial')] * 2), 8)
    assert result['usage']['calls'] == 2
    assert result['summary']['cases']['case']['predictions'][2:] == ['unresolved', 'partial', 'partial']


def test_transport_stop_drains_dispatched_calls_without_starting_whole_queue(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    rows = {f'C{i}': deepcopy(row(tmp_path)) for i in range(20)}
    class Broken(Engine):
        def generate(self, *args, **kwargs):
            raise RuntimeError('offline connection failure')
    manifest = {'rows': rows, 'new_repeat_indices': [2], 'max_calls': 20, 'completion_budget': 20480}
    result = execute_parallel(out, manifest, {}, lambda: Broken([]), 8)
    assert result['stop_reason'].startswith('Three consecutive')
    assert 8 <= result['usage']['calls'] <= 10
    assert result['summary']['outcomes'] == {'transport_error': result['usage']['calls']}
    assert all(json.loads(p.read_text())['outcome'] == 'transport_error' for p in (out / 'jobs').glob('*.json'))
