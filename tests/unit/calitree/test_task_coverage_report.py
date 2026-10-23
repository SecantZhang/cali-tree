import pytest

from critical.core.decision.artifacts import save_json
from run import calitree_task_coverage as run


def fixture(tmp_path, monkeypatch):
    cases = {}; slots = []; jobs = {}
    for i, (baseline, hybrid) in enumerate(zip((0, 0, 1, 1), (1, 0, 0, 1))):
        name = f'case{i}'; cases[name] = {'case': name, 'reference': 0}
        slot = {'case': name, 'batch': 'G1' if i < 2 else 'G2', 'route': {'covered': baseline != hybrid}, 'cached_tree_prediction': 0}
        for arm, prediction in (('baseline', baseline), ('hybrid', hybrid)):
            key = name + (arm if baseline != hybrid else 'shared')
            slot[arm+'_job'] = key
            spec = {'payload': {'instruction': 'test'}, 'stage': 'flat_judge'}
            jobs[key] = {'case': name, 'request': spec}
            judgment = {'label': run.tc.LABELS[prediction], 'rationale': 'test'}
            save_json(tmp_path / 'responses' / (key+'.json'), {'judgment': judgment, 'execution_ref': key, 'error': None})
            save_json(tmp_path / 'ledger/jobs' / (key+'.json'), {'parsed': judgment, 'payload': spec['payload'],
                      'stage': spec['stage'], 'case_id': name, 'outcome': 'completed'})
        slots.append(slot)
    manifest = {'cases': cases, 'splits': [{'split': 1, 'slots': slots}], 'jobs': jobs}
    save_json(tmp_path / 'ledger/budget.json', {'calls': 6})
    monkeypatch.setattr(run, 'verify', lambda out: manifest)
    return manifest


def test_report_detects_child_regression_despite_unchanged_overall_accuracy(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    result = run.report(tmp_path)['splits'][0]
    assert result['overall']['baseline_correct'] == result['overall']['hybrid_correct'] == 2
    assert result['batches']['G1']['baseline_correct'] == 2 and result['batches']['G1']['hybrid_correct'] == 1
    assert not result['preserves_each_child_vs_regular']
    assert not result['preserves_each_child_vs_cached_tree']
    assert result['overall']['wins'] == ['case2'] and result['overall']['losses'] == ['case0']


def test_incomplete_evaluation_cannot_report_accuracy(tmp_path, monkeypatch):
    manifest = fixture(tmp_path, monkeypatch)
    key = manifest['splits'][0]['slots'][0]['hybrid_job']
    (tmp_path / 'responses' / (key+'.json')).unlink()
    with pytest.raises(ValueError, match='incomplete'):
        run.report(tmp_path)


def test_response_must_match_its_actual_model_job(tmp_path, monkeypatch):
    manifest = fixture(tmp_path, monkeypatch)
    key = manifest['splits'][0]['slots'][0]['hybrid_job']
    p = tmp_path / 'responses' / (key+'.json'); response = run.read(p)
    response['judgment']['label'] = 'no'; save_json(p, response)
    with pytest.raises(AssertionError):
        run.report(tmp_path)
