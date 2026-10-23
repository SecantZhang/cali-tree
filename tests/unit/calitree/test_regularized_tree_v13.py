from copy import deepcopy
from dataclasses import replace

import pytest

from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as v13
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.union_validation_v12 import folds
from run.calitree_regularized_v13 import inner_folds, score


def rows(n=48):
    result = []
    for i in range(n):
        label = i % 3
        progress = ('none', 'toward_requested_goal', 'requested_endpoint')[label]
        gap = ('core_endpoint_missing', 'minor_detail', 'none')[label]
        values = {'meaning_available': True}
        for quantifier in ('any', 'all'):
            values[f'meaning_progress_{progress}_{quantifier}'] = True
            values[f'meaning_endpoint_gap_{gap}_{quantifier}'] = True
        result.append({'source_group': f's{i:03}', 'case': f'c{i}', 'instruction': f'distinct request {i}',
            'batch': f'G{(i // 3) % 4}', 'reference': label, 'features': synthetic_record(**values)})
    return result


def test_explicit_quantifier_alternatives_preserve_fit_but_differ_off_support():
    data = rows(12); config = v13.Config(max_depth=2, min_sources=2, leaf_penalty=0)
    fits = v13.TreeFits()
    a, b = [fits.fit(data, replace(config, quantifier=q)) for q in ('all', 'any')]
    assert a['metrics']['correct'] == b['metrics']['correct'] == 12
    assert a['runtime'] != b['runtime']
    alternatives = a['policy']['search']['alternatives']
    assert any(g['training_equivalent_alternatives'] for g in alternatives)
    assert all(g['semantic_equivalence_claim'] is False for g in alternatives)
    probe = synthetic_record(meaning_available=True, meaning_progress_none_any=True)
    assert PortableRuleExecutor(a['runtime']).predict_records([probe])[0]['prediction'] != PortableRuleExecutor(b['runtime']).predict_records([probe])[0]['prediction']


def test_pruning_reduces_complexity_and_retains_complete_source_provenance():
    data = rows(24); fits = v13.TreeFits()
    detailed = fits.fit(data, v13.Config(min_sources=2, leaf_penalty=0))
    pruned = fits.fit(data, v13.Config(min_sources=2, leaf_penalty=48))
    assert detailed['complexity']['rules'] == 3 and pruned['complexity']['rules'] == 1
    assert pruned['metrics']['total'] == 24 and pruned['metrics']['correct'] == 8
    assert pruned['policy']['tree']['source_groups'] == sorted(r['source_group'] for r in data)
    PortableSemanticTree.restore(pruned['policy'])


def test_missing_evidence_is_never_removed_from_denominator():
    data = rows(24); data[0]['features'] = None
    model = v13.TreeFits().fit(data, v13.Config(min_sources=2, leaf_penalty=0))
    assert model['metrics']['total'] == 24 and model['metrics']['unresolved'] == 1
    assert model['policy']['conflicts']['missing_sources'] == ['s000']
    assert len(model['fit_sources']) == 24


def test_content_cache_is_bound_to_targets_configuration_and_exact_rows():
    data = rows(12); fits = v13.TreeFits(max_fits=2); config = v13.Config(min_sources=2)
    first = fits.fit(data, config)
    assert fits.fit(list(reversed(data)), config) == first
    assert fits.stats['fits'] == 1 and fits.stats['cache_hits'] == 1
    changed = deepcopy(data); changed[0]['reference'] = 1
    assert fits.fit(changed, config)['fit_ref'] != first['fit_ref']
    with pytest.raises(RuntimeError, match='budget exhausted'):
        fits.fit(data, replace(config, quantifier='any'))


def test_supported_sources_also_require_distinct_instructions():
    data = rows(12)
    for row in data:
        row['instruction'] = 'one repeated instruction'
    with pytest.raises(ValueError, match='distinct-source/instruction'):
        v13.TreeFits().fit(data, v13.Config())


def test_complete_hierarchy_has_measured_compression_at_every_merge():
    data = rows(); config = v13.Config(min_sources=2, leaf_penalty=0)
    result = v13.learn(data, config)
    assert result['complete'] and result['root']['metrics']['correct'] == 48
    registry = {n['node_id']: n for n in result['nodes']}
    visited = []
    def check(node):
        if not node['children']:
            return
        children = [registry[k] for k in node['children']]
        assert set(node['fit_sources']) == set().union(*(set(c['fit_sources']) for c in children))
        assert not set(children[0]['fit_sources']) & set(children[1]['fit_sources'])
        assert node['acceptance']['status'] == 'accepted'
        assert node['acceptance']['legacy_gate']['status'] == 'accepted'
        assert node['complexity']['rules'] <= .8 * sum(c['complexity']['rules'] for c in children)
        visited.append(node['node_id'])
        for child in children:
            check(child)
    check(result['root'])
    assert len(visited) == 3
    assert len(result['proposals']) <= 18 and result['work']['fits'] <= 58


def test_rejection_keeps_forest_without_substituting_direct_fit():
    result = v13.learn(rows(), v13.Config(min_sources=2, compression=.9))
    assert result['root'] is None and not result['complete']
    assert len(result['forest']) == 4
    assert all(not n['children'] for n in result['nodes'])
    value = {'source_groups': [r['source_group'] for r in rows()], 'fit_ref': 'test', 'result': result}
    held = rows(12)
    for r in held:
        r['source_group'] = 'held-' + r['source_group']
    measured = score(value, held)
    assert measured['metrics']['unresolved'] == measured['metrics']['total'] == 12


def test_smaller_nonperfect_parent_discloses_changed_gate():
    data = rows(24); data[0]['reference'] = 1; data[3]['reference'] = 1; data[6]['reference'] = 1
    fits = v13.TreeFits(); config = v13.Config(min_sources=2, leaf_penalty=2, gate_mode='regularized')
    children = []
    for i, cohort in enumerate((data[:12], data[12:])):
        c = fits.fit(cohort, replace(config, leaf_penalty=0)); c['node_id'] = str(i); children.append(c)
    parent = fits.fit(data, config)
    decision = v13.compression_gate(parent, children, data, config)
    assert decision['legacy_gate']['status'] == 'rejected'
    assert 'union_accuracy_not_strictly_above_90_percent' in decision['legacy_gate']['reasons']
    assert decision['gate_mode'] == 'regularized'
    # This does not certify generalization: the separate CV procedure must do so.


def test_nested_folds_hold_out_sources_before_learning():
    data = rows()
    outer = folds(data)
    for f in outer:
        fit_ids = {r['source_group'] for r in f['train']}
        held_ids = {r['source_group'] for r in f['validation']}
        inner = inner_folds(f['train'])
        assert len(inner) == 3
        for g in inner:
            assert len(g['train']) == 24 and len(g['validation']) == 12
            assert not {r['source_group'] for r in g['train']} & {r['source_group'] for r in g['validation']}
            assert {r['source_group'] for r in g['train'] + g['validation']} == fit_ids
            assert not {r['source_group'] for r in g['train'] + g['validation']} & held_ids


def test_score_refuses_training_overlap():
    data = rows(12); value = {'source_groups': ['s000'], 'result': {'root': None}}
    with pytest.raises(ValueError, match='overlaps'):
        score(value, data)


def test_runtime_roundtrip_and_reordered_training_are_identical():
    data = rows(24); config = v13.Config(min_sources=2)
    a = v13.TreeFits().fit(data, config); b = v13.TreeFits().fit(list(reversed(data)), config)
    assert a == b
    assert PortableRuleExecutor.from_training_policy(a['policy']).metadata() == a['runtime']
    assert v13.predict(a, data) == v13.predict(b, data)


def test_unknown_predicates_and_invalid_config_fail_before_fitting():
    with pytest.raises(ValueError, match='configuration'):
        v13.Config(min_sources=1)
    with pytest.raises(ValueError, match='vocabulary'):
        v13.TreeFits().fit(rows(12), v13.Config(), allowed=['case_id'])
