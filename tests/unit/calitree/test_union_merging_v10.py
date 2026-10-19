from copy import deepcopy
import json

import pytest

from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import violations
from critical.core.calibration.semantic_hierarchy.union_groups_v10 import original, split_balanced, semantic, validate_partition
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import UnionFits
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import learn, gate
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import ReuseFits
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import export as export_union, load as load_union, UnionJudge
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import constrained_fit, describe, PROFILES
from critical.core.decision.artifacts import digest


def rows(n=48):
    return [{'case': f'C{i:03}', 'source_group': f'source-{i:03}', 'instruction': f'Logical instruction {i}',
             'batch': f'G{i // (n // 4)}', 'reference': i % 3,
             'features': synthetic_record(meaning_available=True,
                 meaning_progress_requested_endpoint_all=i % 3 == 2,
                 meaning_progress_toward_requested_goal_all=i % 3 == 1)} for i in range(n)]


def test_seed_partitions_keep_every_original_source_and_balanced_split():
    data = rows()
    for fn in (original, split_balanced, semantic):
        groups = fn(data); validate_partition(groups, data)
        assert sum(map(len, groups)) == 48
    assert [len(g) for g in split_balanced(data)] == [6] * 8
    by_source = {r['source_group']: r for r in data}
    assert all([sum(by_source[s]['reference'] == k for s in g) for k in range(3)] == [2, 2, 2]
               for g in split_balanced(data))
    with pytest.raises(ValueError):
        validate_partition(split_balanced(data)[:-1], data)


def test_semantic_grouping_is_label_blind_and_keeps_missing_evidence():
    data = rows(); data[2]['features'] = None
    before = semantic(data)
    shuffled_labels = [{**r, 'reference': (r['reference'] + 1) % 3} for r in reversed(data)]
    assert semantic(shuffled_labels) == before
    assert sum(data[2]['source_group'] in g for g in before) == 1


@pytest.mark.parametrize('n', [12, 24, 48, 96])
def test_union_hierarchy_learns_and_restores_without_m4(tmp_path, monkeypatch, n):
    from critical.core.calibration.semantic_hierarchy import hierarchy_training_v9, hierarchy_runtime_v9
    def forbidden(*args, **kwargs):
        raise AssertionError('M4 routing must not execute')
    monkeypatch.setattr(hierarchy_training_v9, 'fit_routes', forbidden)
    monkeypatch.setattr(hierarchy_training_v9, 'guarded_routes', forbidden)
    monkeypatch.setattr(hierarchy_runtime_v9.HierarchyExecutor, 'predict_records', forbidden)
    data = rows(n); groups = original(data); emitted = {}
    fits = UnionFits(tmp_path)
    result = learn(data, groups, 'constrained', fits, lambda key, value: emitted.update({key: deepcopy(value)}))
    assert result['root']['metrics']['correct'] == n
    assert result['selected_merge_count'] == 3 and result['root']['height'] == 2
    assert not result['m4_used']
    runtime = result['root']['runtime']
    assert [d['prediction'] for d in PortableRuleExecutor(json.loads(json.dumps(runtime))).predict_records(
        [r['features'] for r in data])] == [r['reference'] for r in data]
    assert all(r['source_group'] not in json.dumps(runtime) and r['instruction'] not in json.dumps(runtime) for r in data)
    assert not violations(result['root']['policy']['tree'])
    replay = learn(data, groups, 'constrained', UnionFits(tmp_path, replay=True), lambda *_: None)
    assert replay == result and emitted


def test_missing_evidence_remains_in_all_ancestor_denominators(tmp_path):
    data = rows(); data[4]['features'] = None
    result = learn(data, original(data), 'constrained', UnionFits(tmp_path), lambda *_: None)
    assert result['root']['metrics']['total'] == 48
    assert result['root']['metrics']['correct'] == 47 and result['root']['metrics']['unresolved'] == 1
    for node in result['registry'].values():
        assert node['metrics']['total'] == len(node['fit_sources'])
        if data[4]['source_group'] in node['fit_sources']:
            assert node['metrics']['unresolved'] == 1


def test_warm_start_rejects_knowledge_from_outside_union(tmp_path):
    data = rows(24); fits = UnionFits(tmp_path)
    bank, _ = fits.candidates(data[:12], 'constrained')
    with pytest.raises(ValueError, match='outside-union'):
        fits.candidates(data[12:], 'constrained', [bank[0]])


def test_merge_gate_checks_child_retention_even_when_union_accuracy_is_high(tmp_path):
    data = []
    # Two Partial examples in the first child collide with twenty No examples
    # in the other child. The union can fit 34/36, while losing two first-child
    # answers, exceeding its one-case retention allowance.
    for i in range(36):
        if i < 12:
            label = 0 if i < 4 else 1 if i < 8 else 2
            collision = i in (4, 5)
        else:
            label = 0 if i < 32 else 1 if i < 34 else 2
            collision = label == 0
        values = {'meaning_available': True, 'outcome_all_true_all': label == 2,
                  'intermediate_all_true_any': label == 1 and not collision,
                  'outcome_all_false_any': collision}
        data.append({'case': f'C{i}', 'source_group': f's{i:03}', 'batch': 'a' if i < 12 else 'b',
                     'reference': label, 'instruction': f'Logical example {i}', 'features': synthetic_record(**values)})
    fits = UnionFits(tmp_path)
    children = []
    for selected in (data[:12], data[12:]):
        bank, _ = fits.candidates(selected, 'constrained')
        child = max(bank, key=lambda m: m['metrics']['correct'])
        children.append({**child, 'node_id': selected[0]['batch'], 'fit_sources': [r['source_group'] for r in selected]})
    bank, _ = fits.candidates(data, 'constrained', children)
    parent = max(bank, key=lambda m: m['metrics']['correct'])
    decision = gate(parent, children, data)
    assert parent['metrics']['correct'] == 34
    assert decision['status'] == 'rejected'
    assert 'child_retention_regression:a' in decision['reasons']


def test_reuse_first_merges_use_child_predicates_and_no_router(tmp_path, monkeypatch):
    from critical.core.calibration.semantic_hierarchy import hierarchy_training_v9
    monkeypatch.setattr(hierarchy_training_v9, 'fit_routes', lambda *a, **k: pytest.fail('M4 was called'))
    data = rows(); fits = ReuseFits(tmp_path)
    result = learn(data, split_balanced(data), 'reuse', fits, lambda *_: None)
    assert result['root']['metrics']['correct'] == 48
    assert result['selected_merge_count'] == 7 and result['root']['height'] == 3
    for name in result['selected_merge_order']:
        node = result['registry'][name]
        assert node['reuse']['kind'] == 'child_only'
        assert not node['reuse']['new_used_predicates']
        assert node['reuse']['parent_union_only']
    replay = learn(data, split_balanced(data), 'reuse', ReuseFits(tmp_path, replay=True), lambda *_: None)
    assert replay == result


def test_reuse_fitter_rejects_parent_conditions_from_outside_union(tmp_path):
    data = rows(24); fits = ReuseFits(tmp_path)
    bank, _ = fits.candidates(data[:12], 'reuse')
    with pytest.raises(ValueError, match='outside'):
        fits.candidates(data[12:], 'reuse', [bank[0]])


def test_parallel_fit_workers_share_one_immutable_cache_entry(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    workers = [UnionFits(tmp_path), UnionFits(tmp_path)]
    data = rows(12)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(w.cold, data, 'constrained', 'compact') for w in workers]
        results = [f.result() for f in futures]
    assert results[0] == results[1]
    assert sum(w.new_fits for w in workers) == 1


def test_selection_prefers_a_qualified_reused_root_over_a_more_accurate_cold_root():
    from run.calitree_union_reuse import selection_key
    data = rows()
    for i in (0, 3):
        data[i]['features']['features'].update(meaning_progress_requested_endpoint_all=True,
                                             outcome_all_false_any=True)
    limited = constrained_fit(data, PROFILES['compact'], features=[
        'meaning_progress_requested_endpoint_all', 'meaning_progress_toward_requested_goal_all'])
    full = constrained_fit(data, PROFILES['compact'])
    reused = describe(limited, data, 'logical-reuse'); reused['reuse'] = {'kind': 'child_only'}
    cold = describe(full, data, 'logical-cold'); cold['reuse'] = {'kind': 'full_grammar_repair'}
    assert reused['metrics']['correct'] == 46 and cold['metrics']['correct'] == 48
    assert selection_key('reused', {'root': reused}) < selection_key('cold', {'root': cold})


def test_frozen_union_inference_has_no_fitting_router_or_training_membership(tmp_path, monkeypatch):
    data = rows(12); bank, _ = UnionFits(tmp_path / 'fits').candidates(data, 'constrained')
    model = max(bank, key=lambda c: c['metrics']['correct'])
    directory = tmp_path / 'package'; manifest = export_union(directory, model['runtime'])
    def forbidden(*args, **kwargs):
        raise AssertionError('Frozen inference attempted training')
    monkeypatch.setattr(UnionFits, 'cold', forbidden)
    monkeypatch.setattr(ReuseFits, 'restricted', forbidden)
    judge = load_union(directory)
    assert [p['prediction'] for p in judge.predict_records([r['features'] for r in data])] == [r['reference'] for r in data]
    assert manifest['router_present'] is False and manifest['inference_policies'] == 1
    assert all(r['source_group'] not in json.dumps(judge.export()) for r in data)
    bad = judge.export(); bad['routes'] = []
    bad['artifact_ref'] = digest({k: v for k, v in bad.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError):
        UnionJudge(bad)


def test_union_package_authenticates_prompts_and_cli_rejects_labels(tmp_path):
    from run.calitree_union_predict import predict
    data = rows(12); bank, _ = UnionFits(tmp_path / 'fits').candidates(data, 'constrained')
    directory = tmp_path / 'package'; export_union(directory, bank[0]['runtime'])
    with pytest.raises(ValueError, match='prohibited'):
        predict(directory, {'reference': 2})
    (directory / 'interpret.txt').write_text('changed semantics')
    with pytest.raises(ValueError):
        load_union(directory)

