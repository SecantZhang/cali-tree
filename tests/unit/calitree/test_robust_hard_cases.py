"""Offline checks for failure-selected stress-test protocol and reporting."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from run.calitree_robust_hard_cases import HISTORY, PREVIOUS, SOURCE, preflight, select_hard_cases
from run.calitree_robust_leaf_optimization import write_report


def test_hard_case_selection_uses_only_saved_seed_scores():
    source = json.loads(SOURCE.read_text())
    history = json.loads(HISTORY.read_text())
    previous = json.loads(PREVIOUS.read_text())
    cases, ranking = select_hard_cases(source, history, previous)
    assert {r['instruction'] for r in cases} == {
        'Put a frog in the toilet', 'Turn the image into a drawing made from chalk',
        'Change the background into a basketball court'}
    assert not ({r['id'] for r in cases} & {r['id'] for r in previous['cases']})
    assert [r['mean_seed_agreement'] for r in ranking] == sorted(r['mean_seed_agreement'] for r in ranking)
    altered = deepcopy(history)
    for arms in altered['cases'].values():
        for row in arms.values():
            row['final']['selected']['agreement'] = 0
    assert select_hard_cases(source, altered, previous) == (cases, ranking)
    reversed_source = deepcopy(source)
    reversed_source['cases'].reverse()
    assert select_hard_cases(reversed_source, history, previous) == (cases, ranking)


def test_hard_preflight_pins_sources_and_budget(tmp_path):
    manifest = preflight(tmp_path)
    assert len(manifest['cases']) == len({r['group'] for r in manifest['cases']}) == 3
    assert manifest['max_calls'] == 1800 and manifest['reserve_calls'] == 480
    assert manifest['planned_maximum_calls'] == 12 * (109 + 40) + 6 == 1794
    assert manifest['reserve_tokens'] == 480 * 1024
    assert preflight(tmp_path) == manifest
    manifest['selection']['ranking'][0]['mean_seed_agreement'] = .5
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Frozen'):
        preflight(tmp_path)


def test_report_uses_actual_case_count_and_scope(tmp_path):
    manifest = {'cases': [{'id': 'hard', 'target': 'partial'}], 'scope': 'Failure-selected stress test.'}
    result = {'status': 'completed', 'cases': {}, 'budget': {}}
    write_report(tmp_path, result, manifest)
    report = (tmp_path / 'report.md').read_text()
    assert 'Failure-selected stress test.' in report and 'Robust / 1' in report
    assert 'all 1 cases' in report and 'all six cases' not in report
