from copy import deepcopy
from itertools import product

import pytest

from critical.core.calibration import local_compression_v18 as local
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from tests.unit.calitree.test_regularized_tree_v13 import rows


def requirement(data, correct):
    return {'sources': [r['source_group'] for r in data], 'correct': correct}


def fitted(data):
    model, _ = local.fit(data, [requirement(data, len(data))], max_rules=12)
    assert model is not None
    return model


def test_full_hierarchy_compresses_without_any_local_accuracy_loss():
    data = rows()
    seeds = [fitted([r for r in data if r['batch'] == f'G{i}']) for i in range(4)]
    result = local.learn(data, seeds)
    assert result['root']['metrics']['correct'] == 48
    assert result['summary']['original_rules'] == 12
    assert result['summary']['forest_rules'] == 3
    for event in result['events']:
        assert event['status'] == 'accepted'
        assert event['decision']['rules'] < event['separate_rules']
        assert all(r['after'] >= r['correct'] for r in event['decision']['retention'])
    assert result['summary']['searches'] == 13
    assert result['new_model_calls'] == result['reserved_test_predictions'] == 0


def test_aggregate_improvement_cannot_hide_local_regression():
    data = rows(12)
    parent = fitted(data)
    # Swap two original labels in one scope. This parent still meets the total
    # floor but misses the stricter local floor; aggregate accuracy is insufficient.
    changed = deepcopy(data); changed[0]['reference'] = 1; changed[1]['reference'] = 0
    decision = local.gate(parent, changed, [requirement(changed, 10), requirement(changed[:3], 3)], max_rules=3)
    assert 'local_accuracy_regression' in decision['reasons']
    assert 'changed_training_evidence_or_references' in decision['reasons']


def test_identical_features_with_conflicting_local_floors_retain_forest():
    data = rows(16)
    for i, r in enumerate(data):
        r['features'] = synthetic_record(meaning_available=True)
        r['reference'] = (i // 4) % 3
    seeds = [fitted(data[i:i+4]) for i in range(0, 16, 4)]
    result = local.learn(data, seeds)
    assert result['root'] is None and result['summary']['forest_local_correct'] == 16
    assert result['summary']['forest_size'] == 3  # The two label-zero children can merge.
    assert any(s['stop'] == 'feature_equality_proves_infeasible' for s in result['searches'])
    assert 'None.' in result['forest_routing']


def test_tiny_budget_keeps_incumbents_instead_of_returning_a_lossy_root():
    data = rows(); seeds = [fitted([r for r in data if r['batch'] == f'G{i}']) for i in range(4)]
    result = local.learn(data, seeds, config=local.Config(max_states=1))
    assert result['root'] is None
    assert result['summary']['forest_local_correct'] == 48
    assert result['summary']['budget_exhausted_searches'] == result['summary']['searches']


def test_missing_evidence_is_counted_and_search_defers_without_dropping_it():
    data = rows(12); data[0]['features'] = None
    model, report = local.fit(data, [requirement(data, 11)], max_rules=4)
    assert model is None and report['stop'] == 'new_search_requires_complete_evidence_keep_incumbents'
    assert report['requirements'][0]['correct'] == 11 and len(report['requirements'][0]['sources']) == 12
    assert not local.equality_certificate(data, [requirement(data, 12)])['feasible']


def test_missing_interpretation_is_not_treated_as_a_false_semantic_feature():
    data = rows(12); data[0]['features'] = synthetic_record(meaning_available=False)
    _, report = local.fit(data, [requirement(data, 10)], max_rules=4)
    assert report['stop'] == 'new_search_requires_complete_evidence_keep_incumbents'


def test_reordering_and_renaming_source_ids_do_not_change_runtime():
    data = rows(12); a = fitted(data)
    changed = deepcopy(list(reversed(data)))
    for i, r in enumerate(changed):
        r['source_group'] = f'renamed{i:03}'; r['case'] = 'unusable as a predicate'; r['batch'] = 'renamed'
    assert fitted(changed)['runtime'] == a['runtime']


def test_search_preserves_alias_metadata_without_semantic_equivalence_claim():
    model, report = local.fit(rows(12), [requirement(rows(12), 12)], max_rules=3)
    assert model and any(len(g['alternatives']) > 1 for g in report['partition_aliases'])
    assert all(set(g['alternatives']) <= set(local.FEATURES) for g in report['partition_aliases'])
    assert not report['global_optimality_claim']


def test_outside_scope_cached_policy_is_not_reused():
    data = rows(); seeds = [fitted([r for r in data if r['batch'] == f'G{i}']) for i in range(4)]
    outside = deepcopy(rows(12))
    for r in outside:
        r['source_group'] = 'outside-' + r['source_group']
    result = local.learn(data, seeds, cached=[fitted(outside)], config=local.Config(max_states=1))
    assert result['summary']['forest_rules'] == 12 and result['root'] is None


def test_runtime_contains_only_generic_predicates_and_labels():
    model = fitted(rows(12))
    def visit(node):
        assert set(node) in ({'prediction'}, {'feature', 'true', 'false'})
        if 'feature' in node:
            assert node['feature'] in local.FEATURES
            visit(node['true']); visit(node['false'])
    visit(model['runtime']['tree'])


@pytest.mark.parametrize('floors', [(0, 0), (4, 4), (6, 6), (8, 8)])
def test_bounded_pareto_search_matches_exhaustive_small_problem(floors):
    features = ['meaning_identity_evidence_same_instance_all', 'meaning_evidence_consistency_coherent_all']
    data = []
    for bits, labels in zip(product((False, True), repeat=2), ((0,0,1,1), (0,0,1,1), (1,1,2,2), (2,2,2,2))):
        for j, label in enumerate(labels):
            i = len(data)
            data.append({'case': str(i), 'source_group': f'{i:03}', 'instruction': f'request {i}', 'batch': str(j//2),
                         'reference': label, 'features': synthetic_record(meaning_available=True, **dict(zip(features, bits)))})
    reqs = [requirement([r for r in data if r['batch'] == str(i)], floor) for i, floor in enumerate(floors)]
    def trees(cohort, depth):
        leaf = local._leaf(cohort)
        yield {r['source_group']: leaf['prediction'] for r in cohort}, 1
        if depth:
            for f in features:
                a, b = [[r for r in cohort if r['features']['features'][f] == v] for v in (True, False)]
                if min(len(a), len(b)) < 2:
                    continue
                for (ap, an), (bp, bn) in product(trees(a, depth-1), trees(b, depth-1)):
                    yield {**ap, **bp}, an+bn
    expected = []
    for ps, rules_count in trees(data, 2):
        if all(sum(ps[r['source_group']] == r['reference'] for r in data if r['source_group'] in q['sources']) >= q['correct'] for q in reqs):
            expected.append((sum(ps[r['source_group']] != r['reference'] for r in data), rules_count))
    model, _ = local.fit(data, reqs, max_rules=4, config=local.Config(max_depth=2))
    assert bool(model) == bool(expected)
    if model:
        assert (len(data) - model['metrics']['correct'], model['complexity']['rules']) == min(expected)
