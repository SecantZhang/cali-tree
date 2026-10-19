from copy import deepcopy
from pathlib import Path

import pytest

from critical.core.calibration.semantic_hierarchy import union_validation_v12 as v12
from critical.core.calibration.semantic_hierarchy import union_merges_v10 as original
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import describe, constrained_fit, PROFILES, UnionFits
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import ReuseFits
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from tests.unit.calitree.test_union_merging_v10 import rows


def candidate(data, family='reuse'):
    n = describe(constrained_fit(data, PROFILES['compact']), data, 'test')
    n['generation_families'] = [family]
    n['generation_alternatives'] = {family: {'initialization': 'test', 'reuse': {'kind': family}}}
    return n


def test_gate_is_the_original_function_and_limits_are_unmodified():
    assert v12.gate is original.gate
    assert v12.LIMITS is original.LIMITS
    assert v12.LIMITS['retained_policies_per_union'] == 2


def test_always_challenges_even_when_reuse_already_passes(tmp_path, monkeypatch):
    data = rows(12); warm = candidate(data)
    warm['reuse'] = {'kind': 'child_only'}
    monkeypatch.setattr(ReuseFits, 'candidates', lambda *a, **k: ([deepcopy(warm)], ['restricted-fit']))
    cold_calls = []
    def cold(self, selected, engine, profile):
        cold_calls.append((len(selected), engine, profile))
        value = deepcopy(warm); value['initialization'] = 'cold:' + profile
        return {'fit_ref': 'cold-' + profile, 'result': value}
    monkeypatch.setattr(v12.ChallengerFits, 'cold', cold)
    children = [{**candidate(data[:6]), 'node_id': 'a', 'fit_sources': [r['source_group'] for r in data[:6]]},
                {**candidate(data[6:]), 'node_id': 'b', 'fit_sources': [r['source_group'] for r in data[6:]]}]
    bank, refs = v12.ChallengerFits(tmp_path).candidates(data, 'reuse', children)
    assert cold_calls == [(12, 'constrained', 'shallow'), (12, 'constrained', 'compact')]
    assert set(bank[0]['generation_families']) == set(v12.FAMILIES)
    assert 'cold-shallow' in refs and 'cold-compact' in refs
    assert warm['generation_families'] == ['reuse']


def test_foreign_child_knowledge_is_still_rejected(tmp_path):
    data = rows(24)
    child = candidate(data[:12]); child.update(node_id='foreign', fit_sources=[r['source_group'] for r in data[:12]])
    with pytest.raises(ValueError, match='outside'):
        v12.ChallengerFits(tmp_path).candidates(data[12:], 'reuse', [child])


def test_two_slot_retention_covers_both_families():
    a, b, c = [candidate(rows(12), family) for family in ('reuse', 'reuse', 'full_grammar')]
    for i, n in enumerate((a, b, c)):
        n['runtime']['artifact_ref'] = str(i)
        n['metrics']['correct'] = 12 - i
    kept = v12.retain([a, b, c])
    assert len(kept) == 2 and a in kept and c in kept and b not in kept


def test_full_training_folds_are_source_disjoint_stratified_and_complete():
    data = rows()
    fs = v12.folds(data)
    assert len(fs) == 4
    for f in fs:
        assert len(f['train']) == 36 and len(f['validation']) == 12
        assert not {r['source_group'] for r in f['train']} & {r['source_group'] for r in f['validation']}
        assert [sum(r['reference'] == k for r in f['train']) for k in range(3)] == [12, 12, 12]
        for method in v12.GROUPINGS:
            g = v12.grouping(f['train'], method)
            v12.validate_partition(g, f['train'])
            assert sorted(map(len, g)) == ([9] * 4 if method == 'original4' else [4] * 4 + [5] * 4)
    assert len({r['source_group'] for f in fs for r in f['validation']}) == 48
    assert [[r['source_group'] for r in f['validation']] for f in fs] == [[r['source_group'] for r in f['validation']] for f in v12.folds(list(reversed(data)))]


def test_semantic_inner_grouping_is_label_blind():
    data = v12.folds(rows())[0]['train']
    changed = [{**r, 'reference': (r['reference'] + 1) % 3} for r in reversed(data)]
    assert v12.semantic_inner(data) == v12.semantic_inner(changed)


def test_failed_inner_fold_keeps_every_validation_target():
    folds = []
    for i in range(4):
        ps, ys = ([-1] * 12 if i == 0 else [0, 1, 2] * 4), [0, 1, 2] * 4
        folds.append({'fold': i, 'available': i != 0, 'predictions': ps, 'references': ys, 'metrics': v12.metrics(ps, ys)})
    value = v12.cv_summary(folds)
    assert value['metrics']['total'] == 48 and value['metrics']['correct'] == 36
    assert value['metrics']['unresolved'] == 12 and value['feasible_folds'] == 3 and value['failed_folds'] == [0]


def test_validation_beats_a_better_training_fit_and_reuse_category():
    warm, full = candidate(rows(12)), candidate(rows(12), 'full_grammar')
    warm['node_id'], full['node_id'] = 'warm', 'full'
    warm['metrics']['correct'], full['metrics']['correct'] = 12, 11
    result = {'root_candidates': ['warm', 'full'], 'registry': {'warm': warm, 'full': full}}
    def cv(correct):
        return {'metrics': {'macro_f1': correct, 'worst_present_class_recall': correct, 'correct': round(correct * 48)}, 'fold_macro_f1_std': 0}
    chosen = v12.choose_root({'original4': result}, {'original4': {'reuse': cv(.3), 'full_grammar': cv(.6)}})
    assert chosen['family'] == 'full_grammar' and chosen['root']['node_id'] == 'full'


def test_small_hierarchy_replays_and_accepts_only_original_gate(tmp_path):
    data = rows(24); groups = v12.original(data)
    fits = v12.ChallengerFits(tmp_path)
    result = v12.learn(data, groups, 'reuse', fits, lambda *_: None)
    assert result['root']['metrics']['correct'] == 24
    for n in result['registry'].values():
        assert set(n['fit_sources']) <= {r['source_group'] for r in data}
        if n['children']:
            cohort = [r for r in data if r['source_group'] in n['fit_sources']]
            assert original.gate(n, [result['registry'][k] for k in n['children']], cohort)['status'] == 'accepted'
    replay = v12.learn(data, groups, 'reuse', v12.ChallengerFits(tmp_path, replay=True), lambda *_: None)
    assert replay == result
    assert PortableRuleExecutor(result['root']['runtime']).predict_records([r['features'] for r in data])[0]['prediction'] == data[0]['reference']


def test_outer_evaluation_requires_all_three_frozen_policies(tmp_path, monkeypatch):
    from run import calitree_challenger_validation as runner
    monkeypatch.setattr(runner, 'prepare', lambda out: {})
    with pytest.raises(ValueError, match='All three policies'):
        runner.evaluate(tmp_path)


def test_all_infeasible_cv_is_explicitly_uninformative():
    n = candidate(rows(12), 'full_grammar'); n['node_id'] = 'root'
    result = {'root_candidates': ['root'], 'registry': {'root': n}}
    cv = {'metrics': {'macro_f1': 0., 'worst_present_class_recall': 0., 'correct': 0}, 'fold_macro_f1_std': 0}
    chosen = v12.choose_root({'original4': result}, {'original4': {'reuse': cv, 'full_grammar': cv}})
    assert chosen['root'] is n and not chosen['validation_informative']


def test_rejected_parent_is_never_retained(tmp_path, monkeypatch):
    data = rows(24)
    monkeypatch.setattr(v12, 'gate', lambda *a: {'status': 'rejected', 'reasons': ['test_rejection']})
    result = v12.learn(data, v12.original(data), 'reuse', v12.ChallengerFits(tmp_path), lambda *_: None)
    assert not result['root_candidates']
    assert all(not n['children'] for n in result['registry'].values())


def test_every_inner_group_is_recomputed_from_inner_sources_only():
    data = rows(); original_ids = {r['source_group'] for r in data}
    for fold in v12.folds(data):
        fit_ids = {r['source_group'] for r in fold['train']}
        held_ids = {r['source_group'] for r in fold['validation']}
        for method in v12.GROUPINGS:
            groups = v12.grouping(fold['train'], method)
            flattened = {s for g in groups for s in g}
            assert flattened == fit_ids and not flattened & held_ids
            assert flattened < original_ids


def test_training_runner_rebuilds_fold_models_and_never_reads_outer_evaluation(tmp_path, monkeypatch):
    from run import calitree_challenger_validation as runner
    from critical.core.decision.artifacts import save_json
    data = rows(); save_json(tmp_path / 'split1/training_data.json', data)
    monkeypatch.setattr(runner, 'prepare', lambda out: {})
    monkeypatch.setattr(runner, 'verify', lambda *args: None)
    seen = []
    def fit(folder, selected, method, fits):
        seen.append((str(folder), {r['source_group'] for r in selected}))
        n = candidate(selected)
        n['generation_families'] = list(v12.FAMILIES)
        n['generation_alternatives']['full_grammar'] = {'initialization': 'test', 'reuse': {'kind': 'full_grammar'}}
        n = original._node(n, 15, [], selected)
        return {'root_candidates': [n['node_id']], 'registry': {n['node_id']: n}, 'stop': 'complete_root'}
    monkeypatch.setattr(runner, 'run_hierarchy', fit)
    real_read = runner.read
    def read_only_training(path):
        assert 'evaluation' not in str(path) and not str(path).endswith('results.json')
        return real_read(path)
    monkeypatch.setattr(runner, 'read', read_only_training)
    runner.train_split(tmp_path, 'split1')
    assert len(seen) == 15
    assert [len(ids) for folder, ids in seen].count(36) == 12
    assert [len(ids) for folder, ids in seen].count(48) == 3
    plan = v12.folds(data)
    for folder, ids in seen:
        if '/inner/' in folder:
            fold_id = int(Path(folder).parent.name.removeprefix('fold'))
            assert ids == {r['source_group'] for r in plan[fold_id]['train']}
            assert not ids & {r['source_group'] for r in plan[fold_id]['validation']}
    assert (tmp_path / 'split1/freeze.json').exists()
    summary = real_read(tmp_path / 'split1/validation_summary.json')
    assert all(value['metrics']['correct'] == 48 for families in summary.values() for value in families.values())
