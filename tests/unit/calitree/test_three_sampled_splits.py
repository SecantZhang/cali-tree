from copy import deepcopy

import pytest

from run.calitree_three_splits import select, assert_splits, LABELS, SEEDS


def pool():
    return [{'id': f'{label}-{i}', 'group': f'{label}-{i}', 'reference': label,
             'task': str(i % 4), 'instruction': f'Request {label}-{i}'}
            for label in LABELS for i in range(70)]


def sampled():
    data = pool(); all_eval = set(); evaluations = []
    for seed in SEEDS:
        rows = select(data, seed, 4, all_eval); evaluations.append(rows)
        all_eval.update(r['group'] for r in rows)
    result = []
    for i, seed in enumerate(SEEDS):
        rows = select(data, seed + 100, 16, all_eval)
        for j, row in enumerate(rows):
            row['batch'] = 'G' + str((j // 3) % 4 + 1)
        result.append({'train': rows, 'evaluation': evaluations[i]})
    return result


def test_sampling_is_deterministic_order_invariant_and_without_replacement():
    data = pool()
    assert select(data, SEEDS[0], 16) == select(list(reversed(data)), SEEDS[0], 16)
    assert select(data, SEEDS[0], 16) != select(data, SEEDS[1], 16)
    assert len({r['group'] for r in select(data, SEEDS[0], 16)}) == 48
    assert all(r['group'] != 'no-0' for r in select(data, SEEDS[0], 16, {'no-0'}))


def test_global_evaluation_exclusion_and_exact_batches():
    splits = sampled()
    assert_splits(splits, {'reserved-source'})
    assert len({r['group'] for s in splits for r in s['evaluation']}) == 36


@pytest.mark.parametrize('kind', ['evaluation_overlap', 'cross_split_leak', 'reserved_leak', 'dropped_source', 'duplicate_source', 'class_imbalance', 'batch_imbalance'])
def test_invalid_resampling_protocol_is_rejected(kind):
    splits = deepcopy(sampled()); excluded = {'reserved-source'}
    if kind == 'evaluation_overlap':
        splits[1]['evaluation'][0] = splits[0]['evaluation'][0]
    elif kind == 'cross_split_leak':
        splits[0]['train'][0] = {**splits[1]['evaluation'][0], 'batch': 'G1'}
    elif kind == 'reserved_leak':
        excluded.add(splits[0]['train'][0]['group'])
    elif kind == 'dropped_source':
        splits[0]['train'].pop()
    elif kind == 'duplicate_source':
        splits[0]['train'][1] = splits[0]['train'][0]
    elif kind == 'class_imbalance':
        splits[0]['train'][0]['reference'] = 'yes'
    else:
        splits[0]['train'][0]['batch'] = 'G2'
    with pytest.raises(ValueError):
        assert_splits(splits, excluded)


def test_luna_wire_profile_and_offline_factory(tmp_path):
    from run.calitree_three_splits import IDENTITY, validate_settings, model_factory
    assert IDENTITY == {'provider': 'openai', 'model': 'gpt-6-luna', 'reasoning_effort': 'none', 'temperature': 0}
    validate_settings()
    with pytest.raises(AssertionError, match='Offline replay'):
        model_factory(tmp_path, False)(8192)


def test_failed_luna_case_is_reused_without_retry_or_replacement(tmp_path, monkeypatch):
    from critical.core.decision.artifacts import save_json
    from run import calitree_three_splits as runner
    retained = {'case': 'N001', 'compilation': None, 'observation': None, 'record': None,
                'error': {'stage': 'compile', 'code': 'invalid_dependency'},
                'diagnostic': {'prediction': -1}}
    save_json(tmp_path / 'cases/N001.json', retained)
    def forbidden(*args, **kwargs):
        raise AssertionError('Retained failure attempted a new call')
    monkeypatch.setattr(runner, 'model_factory', forbidden)
    assert runner.collect_physical(tmp_path, {'workers': 1, 'cases': [{'case': 'N001'}]}, True) == [retained]


def test_every_new_stage_factory_uses_luna_profile(tmp_path, monkeypatch):
    from critical import lm_engine
    from run.calitree_three_splits import model_factory
    class Credentials:
        provider = 'openai'
        endpoints = ['https://api.openai.com/v1']
    monkeypatch.setattr(lm_engine, 'load_creds', lambda **kwargs: Credentials())
    seen = []
    monkeypatch.setattr(lm_engine, 'get_engine', lambda kind, **kwargs: seen.append((kind, kwargs)))
    factory = model_factory(tmp_path, True)
    for cap in (8192, 16384, 8192):
        factory(cap)
    assert len(seen) == 3
    assert all(kind == 'gpt' and kw['model'] == 'gpt-6-luna' and kw['temperature'] == 0
               and kw['max_http_attempts'] == 1 and 'reasoning_effort' not in kw for kind, kw in seen)


def test_different_instructions_on_same_pixels_cannot_share_cache_alias():
    from run.verify_calitree_three_splits import audit_input_bindings
    first = {'case': 'N006', 'id': 'source-task-a', 'group': 'same-pixels',
             'instruction': 'Make it blue', 'reference': 'no', 'image_hashes': {'source': 's', 'edited': 'a'}}
    sibling = {**first, 'id': 'source-task-b', 'instruction': 'Make it yellow',
               'reference': 'partial', 'image_hashes': {'source': 's', 'edited': 'b'}}
    with pytest.raises(ValueError, match='conflated'):
        audit_input_bindings([first], [{'train': [sibling], 'evaluation': []}])
    corrected = {**sibling, 'case': 'N135'}
    audit_input_bindings([first, corrected], [{'train': [corrected], 'evaluation': []}])
