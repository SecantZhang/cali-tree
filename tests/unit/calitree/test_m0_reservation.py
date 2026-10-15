from copy import deepcopy
from pathlib import Path
import pytest

from run.calitree_m0 import (
    QUOTAS, LABELS, context_aliases, execution_aliases, execution_value,
    prepare, protocol, public_input, refs, scrub, select_test, verify,
)


def candidates():
    return [{'id': f'{label}-{i}', 'group': f'{label}-{i}', 'reference': label,
             'task': str(i % 8)} for label in LABELS for i in range(20)]


def test_exact_fifty_nearly_balanced_and_order_independent():
    chosen = select_test(candidates())
    assert chosen == select_test(list(reversed(candidates())))
    assert len(chosen) == len({c['group'] for c in chosen}) == 50
    assert {label: sum(c['reference'] == label for c in chosen) for label in LABELS} == QUOTAS


def test_not_enough_yes_refuses_instead_of_relaxing_or_repeating():
    rows = [r for r in candidates() if r['reference'] != 'yes'] + [r for r in candidates() if r['reference'] == 'yes'][:6]
    with pytest.raises(ValueError, match='Insufficient'):
        select_test(rows)


def test_source_siblings_cannot_fill_test_quota():
    rows = candidates()
    for r in rows:
        if r['reference'] == 'yes':
            r['group'] = 'same-source'
    with pytest.raises(ValueError, match='Insufficient'):
        select_test(rows)


def test_catalog_and_exclusion_lists_are_not_execution_evidence():
    uid = 'aurora-task-' + 'a' * 20
    value = {'manifest': {'cases': [{'task_uid': uid}], 'prior_sources': ['old'],
                          'unused_task_uids_reusing_seen_pixels': ['unused']},
             'raw_dataset': {'all': 'catalog'}, 'source_hashes': {'code': 'hash'}, 'prediction': 'yes'}
    clean = scrub(value)
    assert clean == {'manifest': {'cases': [{'task_uid': uid}]}, 'prediction': 'yes'}
    canvas = {'node_results': {'data': {'status': 'done', 'meta': {'dry_run': True}, 'outputs': {'samples': value}},
                              'partition': {'status': 'done', 'outputs': {'partition': {'fit_ids': [uid]}}}}}
    assert execution_value(canvas) == {}


def test_canvas_execution_does_not_import_entire_dataset_catalog():
    value = {'node_results': {'dataset': {'status': 'done', 'outputs': {'samples': {'all': 'catalog'}}},
                             'judge': {'status': 'done', 'outputs': {'predictions': {'one': {'label': 'yes'}}}}}}
    assert execution_value(value) == {'judge': {'predictions': {'one': {'label': 'yes'}}}}


def test_alias_resolution_and_embedded_png_directory():
    uid = 'aurora-task-' + 'a' * 20
    path = 'human_ratings/whatsup/instruction.png/editor.jpg'
    tasks = {uid: {}}
    by_path = {path: {uid}}
    manifest = {'cases': {'F01': {'source_image': '/old/root/' + path}}}
    assert context_aliases(manifest, tasks, by_path, {})['F01'] == {uid}
    assert refs({'source_image': '/old/root/' + path}, tasks, by_path, {}) == {uid}
    assert execution_aliases({'results': {'F01': {'arms': {'a': {'label': 'yes', 'valid': True}}}}}) == {'F01'}


def test_public_inference_input_cannot_contain_reference_or_exposure():
    row = {'instruction': 'move it', 'evidence': {'source_image': 'a', 'edited_image': 'b'},
           'reference': 'yes', 'human_score': 2, 'historical_status': 'historically_referenced', 'id': 'secret'}
    before = deepcopy(row)
    value = public_input(row)
    assert set(value) == {'instruction', 'evidence'}
    value['evidence']['source_image'] = 'changed'
    assert row == before


def test_m0_forbids_live_calls_and_reserves_fifty():
    p = protocol('no_known_historical_exposure')
    assert p['test_size'] == 50 and sum(p['test_class_quotas'].values()) == 50
    assert p['calls']['m0'] == 0 and p['calls']['m0_model_calls_forbidden']
    assert p['calls']['final_total_max_if_two_stage_extractor_validated'] == 150


def test_incomplete_reservation_does_not_verify(tmp_path):
    with pytest.raises(ValueError, match='incomplete'):
        verify(tmp_path)


def test_historical_scope_requires_recorded_authorization(tmp_path):
    with pytest.raises(ValueError, match='explicit scope authorization'):
        prepare(tmp_path, allow_historical=True)
