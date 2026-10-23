from pathlib import Path

import pytest

from critical.core.decision.artifacts import save_json
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as learner
from run import calitree_frozen_final_v14 as runner
from tests.unit.calitree.test_regularized_tree_v13 import rows


def test_collection_requires_live_flag_before_loading_any_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'prepare', lambda _: pytest.fail('Prepared a non-authorized collection'))
    with pytest.raises(ValueError, match='explicit --live'):
        runner.collect(tmp_path, False)


def test_all_predictions_are_saved_before_references_are_loaded(tmp_path, monkeypatch):
    data = rows(50); data[-1]['features'] = None
    model = learner.TreeFits().fit(rows(24), learner.Config(min_sources=2, leaf_penalty=0))
    policies = {f'{arm}_split{i}': model['runtime'] for i in (1, 2, 3) for arm in ('v14_merge', 'v14_direct', 'v12_merge')}
    save_json(tmp_path / 'policies.json', policies)
    save_json(tmp_path / 'portable_records.json', [{'case': r['case'], 'features': r['features']} for r in data])
    reserved = tmp_path / 'reserved'; monkeypatch.setattr(runner, 'RESERVED', reserved)
    save_json(reserved / 'test_references.json', {'cases': [{'case': r['case'], 'reference': ('No', 'Partial', 'Yes')[r['reference']]} for r in data]})
    monkeypatch.setattr(runner, 'prepare', lambda _: {})
    original_read = runner.base.read
    def read(path):
        if Path(path).name == 'test_references.json':
            assert (tmp_path / 'predictions.json').exists()
        return original_read(path)
    monkeypatch.setattr(runner.base, 'read', read)
    runner.evaluate(tmp_path)
    result = original_read(tmp_path / 'results.json')
    assert all(m['total'] == 50 and m['correct'] == 49 and m['unresolved'] == 1 for m in result['metrics'].values())
    assert len(result['paired']) == 6
    assert all(p == {'both_correct': 49, 'both_wrong': 1} for p in result['paired'].values())
    assert result['unique_evaluation_sources'] == 50 and result['fitting_or_selection'] is False


def test_preflight_seals_target_free_inputs_and_budgets_without_calls(tmp_path):
    manifest = runner.prepare(tmp_path)
    protocol = runner.base.read(tmp_path / 'protocol.json')
    assert len(manifest['cases']) == 50
    assert all('reference' not in r and 'human_score' not in r for r in manifest['cases'])
    assert protocol['new_calls_max'] == 200
    assert protocol['completion_tokens_max'] == 2_048_000
    assert protocol['selection_and_fitting'] is False
    assert not list(tmp_path.glob('**/ledgers')) and not (tmp_path / 'portable_records.json').exists()
    assert runner.prepare(tmp_path) == manifest
