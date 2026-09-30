import hashlib
import json

import pytest

from run.calitree_observation_repeats import execute, summarize, prepare
from .test_observation50 import row
from .test_casewise_fitting import Engine, check


def records(statuses, condition='c1'):
    return {f'check/{i}/case/{condition}': {'job_id': f'check/{i}/case/{condition}',
            'outcome': 'completed', 'check': check(s)} for i, s in enumerate(statuses)}


@pytest.mark.parametrize('statuses,count', [
    (['absent', 'absent', 'absent', 'partial', 'complete'], 3),
    (['partial', 'partial', 'partial', 'partial', 'unknown'], 4),
    (['complete'] * 5, 5), (['unknown'] * 5, 0),
])
def test_agreement_uses_five_and_excludes_unknown(tmp_path, statuses, count):
    result = summarize({'case': row(tmp_path)}, records(statuses))
    assert result['cases']['case']['final_agreement']['count'] == count
    assert result['cases']['case']['final_agreement']['fraction'] == count / 5
    for k in (3, 4, 5):
        assert result['metrics']['final_prediction']['at_least'][str(k)]['count'] == int(count >= k)


def test_final_consistency_can_hide_vector_changes(tmp_path):
    r = row(tmp_path)
    r['plan']['conditions'].append({**r['plan']['conditions'][0], 'id': 'c2'})
    data = records(['absent'] * 5)
    data.update(records(['complete', 'partial', 'complete', 'partial', 'complete'], 'c2'))
    s = summarize({'case': r}, data)['cases']['case']
    assert s['final_agreement']['count'] == 5
    assert s['vector_agreement']['count'] == 3


def test_failed_slot_is_not_a_vote_or_removed_from_denominator(tmp_path):
    data = records(['partial'] * 4)
    data['check/4/case/c1'] = {'outcome': 'transport_error'}
    s = summarize({'case': row(tmp_path)}, data)['cases']['case']
    assert s['final_agreement']['fraction'] == .8
    assert s['incomplete_draws'] == 1 and s['model_unknown_draws'] == 0


def test_only_three_new_draws_and_no_retries_on_resume(tmp_path):
    out = tmp_path / 'extension'; out.mkdir()
    r = row(tmp_path)
    manifest = {'rows': {'case': r}, 'new_repeat_indices': [2, 3, 4],
                'max_calls': 3, 'completion_budget': 3072}
    prior = records(['absent', 'partial'])
    engine = Engine([check('complete')] * 3); engine.max_tokens = 1024
    result = execute(out, manifest, prior, engine)
    assert len(engine.calls) == 3
    assert result['summary']['cases']['case']['predictions'] == ['no', 'partial', 'yes', 'yes', 'yes']
    for prompt, _ in engine.calls:
        assert set(json.loads(prompt.split('INPUT_JSON: ')[1])) == {'instruction', 'condition'}
    assert execute(out, manifest, prior, Engine([])) == result


def test_interrupted_new_slot_is_not_resampled(tmp_path):
    out = tmp_path / 'extension'; (out / 'jobs').mkdir(parents=True)
    key = 'check/2/case/c1'
    (out / 'jobs' / (hashlib.sha256(key.encode()).hexdigest() + '.json')).write_text(
        json.dumps({'job_id': key, 'outcome': 'interrupted_or_pending'}))
    engine = Engine([check('complete')] * 2); engine.max_tokens = 1024
    s = execute(out, {'rows': {'case': row(tmp_path)}, 'new_repeat_indices': [2, 3, 4],
                     'max_calls': 3, 'completion_budget': 3072}, records(['complete'] * 2), engine)
    assert len(engine.calls) == 2
    assert s['summary']['cases']['case']['final_agreement']['fraction'] == .8


def test_prepare_rejects_dependency_change_before_calls(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'manifest.json').write_text(json.dumps({'source_sha256': {__file__: 'wrong'}}))
    with pytest.raises(ValueError, match='dependency changed'):
        prepare(source, tmp_path / 'out')


def test_budget_stops_before_fourth_request(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    engine = Engine([check('complete')] * 3); engine.max_tokens = 1024
    result = execute(out, {'rows': {'case': row(tmp_path)}, 'new_repeat_indices': [2, 3, 4],
                          'max_calls': 1, 'completion_budget': 3072}, records(['complete'] * 2), engine)
    assert len(engine.calls) == 1
    assert result['stop_reason'] == 'Request allowance exhausted'
