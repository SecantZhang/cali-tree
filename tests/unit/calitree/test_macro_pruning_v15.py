from copy import deepcopy
from itertools import product

import pytest

from critical.core.calibration import macro_pruning_v15 as macro
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as base
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as prior
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from tests.unit.calitree.test_regularized_tree_v13 import rows


def fixture():
    features = ['meaning_identity_materiality_no_shortfall_all', 'meaning_collateral_materiality_none_all',
                'meaning_identity_evidence_same_instance_all', 'meaning_evidence_consistency_coherent_all']
    groups = []; data = []
    for counts, bits in [([3, 1, 0], [1, 1, 0, 0]), ([1, 2, 0], [1, 0, 1, 0]),
                         ([2, 0, 0], [1, 0, 0, 0]), ([0, 2, 0], [0, 0, 0, 1]), ([0, 0, 20], [0, 0, 0, 0])]:
        cohort = []
        for k, count in enumerate(counts):
            for _ in range(count):
                i = len(data)
                r = {'source_group': str(i), 'case': str(i), 'instruction': f'request {i}', 'batch': 'G1', 'reference': k,
                     'features': synthetic_record(meaning_available=True, **dict(zip(features, map(bool, bits))))}
                data.append(r); cohort.append(r)
        groups.append(base._leaf(cohort))
    def branch(name, a, b):
        return {'type': 'split', 'feature': name, 'true': a, 'false': b, 'support': a['support'] + b['support']}
    tree = branch(features[0], branch(features[1], groups[0], branch(features[2], groups[1], groups[2])),
                  branch(features[3], groups[3], groups[4]))
    return tree, data


def predictions(tree, data):
    ps = []
    for row in data:
        node = tree
        while 'feature' in node:
            node = node['true' if row['features']['features'][node['feature']] else 'false']
        ps.append(node['prediction'])
    return ps


def all_prunings(tree, data):
    yield base._leaf(data)
    if 'feature' in tree:
        a, b = [[r for r in data if r['features']['features'][tree['feature']] == value] for value in (True, False)]
        for left, right in product(all_prunings(tree['true'], a), all_prunings(tree['false'], b)):
            yield {'type': 'split', 'feature': tree['feature'], 'true': left, 'false': right, 'support': len(data)}


def test_macro_objective_preserves_partial_where_error_objective_prunes_it():
    tree, data = fixture()
    old, _ = prior.prune_frontier(tree, data, 1)
    new, report = macro.prune_frontier(tree, data, 1)
    targets = [r['reference'] for r in data]
    old_metrics = base.metrics(predictions(old, data), targets)
    new_metrics = base.metrics(predictions(new, data), targets)
    assert old_metrics['per_class']['partial']['correct'] == 2
    assert new_metrics['per_class']['partial']['correct'] == 4
    assert new_metrics['macro_f1'] > old_metrics['macro_f1']
    assert report['all_supported_classes_preserved']


@pytest.mark.parametrize('penalty', [0, .5, 1, 2])
def test_frontier_matches_exhaustive_supported_fixed_shape_objective(penalty):
    tree, data = fixture(); targets = [r['reference'] for r in data]
    choices = []
    for candidate in all_prunings(tree, data):
        measured = base.metrics(predictions(candidate, data), targets)
        if measured['worst_present_class_recall'] > 0:
            choices.append(-measured['macro_f1'] + penalty * base.complexity(candidate)['rules'] / len(data))
    _, report = macro.prune_frontier(tree, data, penalty)
    assert report['selected']['objective'] == pytest.approx(min(choices))
    assert report['budget_exhausted'] is False


def test_state_and_transition_limits_fail_instead_of_silent_truncation():
    tree, data = fixture()
    with pytest.raises(RuntimeError, match='state budget'):
        macro.prune_frontier(tree, data, 1, max_states=1)
    with pytest.raises(RuntimeError, match='transition budget'):
        macro.prune_frontier(tree, data, 1, max_transitions=1)


def test_missing_evidence_and_interpretations_match_runtime_accounting():
    data = rows(24); data[0]['features'] = None
    data[1]['features'] = synthetic_record(meaning_available=False)
    model = macro.MacroFits().fit(data, base.Config(min_sources=2))
    actual = base.metrics([p['prediction'] for p in base.predict(model, data)], [r['reference'] for r in data])
    assert actual == model['metrics']
    assert actual['macro_f1'] == pytest.approx(model['policy']['search']['pruning']['selected']['macro_f1'])
    assert actual['unresolved'] == 2 and actual['total'] == 24


def test_cache_order_and_deepcopy_do_not_change_frozen_runtime():
    data = rows(24); fits = macro.MacroFits(); config = base.Config(min_sources=2)
    a = fits.fit(data, config); runtime = deepcopy(a['runtime'])
    a['runtime']['tree'] = {'prediction': 0}
    b = fits.fit(list(reversed(data)), config)
    assert b['runtime'] == runtime and fits.stats['fits'] == 1
    assert macro.PortableRuleExecutor.from_training_policy(b['policy']).metadata() == runtime


def test_merge_retains_compression_and_original_reference_targets():
    data = rows(); result = macro.learn(data, base.Config(min_sources=2, gate_mode='regularized'))
    assert result['root']['metrics']['correct'] == 48
    assert all(n['acceptance']['compression'] >= .2 for n in result['nodes'] if n['children'])
    assert result['root']['policy']['training']['target_ref'] == macro.digest([r['reference'] for r in data])
