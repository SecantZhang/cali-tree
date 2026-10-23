from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
from pathlib import Path

import pytest

from critical.core.decision.artifacts import digest

from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as v13
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as v14
from tests.unit.calitree.test_regularized_tree_v13 import rows


def imbalanced():
    templates = rows(12); data = []
    for label, count in ((0, 10), (1, 2), (2, 12)):
        for _ in range(count):
            row = deepcopy(templates[label]); i = len(data)
            row.update(source_group=f's{i:03}', instruction=f'unique instruction {i}', case=str(i))
            data.append(row)
    return data


def test_supported_pruning_does_not_erase_rare_partial_class_to_save_a_rule():
    data = imbalanced(); config = v13.Config(min_sources=2, leaf_penalty=3)
    old = v13.TreeFits().fit(data, config); new = v14.SupportedFits().fit(data, config)
    assert old['metrics']['per_class']['partial']['recall'] == 0
    assert new['metrics']['per_class']['partial']['recall'] == 1
    assert new['complexity']['rules'] == 3 and new['metrics']['correct'] == 24
    assert new['policy']['search']['pruning']['all_supported_classes_preserved']
    assert not v14.violations(new['policy']['tree'])


def test_frontier_matches_exhaustive_fixed_shape_prunings():
    data = imbalanced(); config = v13.Config(min_sources=2, leaf_penalty=0)
    model = v13.TreeFits().fit(data, config); shape = v14.grown_tree(model, data)
    def enumerate_prunings(tree, selected):
        yield v13._leaf(selected)
        if 'feature' in tree:
            feature = tree['feature']
            a, b = [[r for r in selected if r['features']['features'][feature] == v] for v in (True, False)]
            for left, right in product(enumerate_prunings(tree['true'], a), enumerate_prunings(tree['false'], b)):
                yield {'type': 'split', 'feature': feature, 'true': left, 'false': right, 'support': len(selected)}
    def labels(tree):
        return {tree['prediction']} if 'feature' not in tree else labels(tree['true']) | labels(tree['false'])
    alternatives = [t for t in enumerate_prunings(shape, data) if labels(t) == {0, 1, 2} and not v14.violations(t)]
    for penalty in (0, .5, 1, 3, 10):
        selected, report = v14.prune_frontier(shape, data, penalty)
        objective = lambda t: v13._errors(t) + penalty * v13.complexity(t)['rules']
        assert objective(selected) == min(map(objective, alternatives))
        assert report['all_supported_classes_preserved']


def test_unachievable_class_is_disclosed_instead_of_fabricating_labels():
    data = imbalanced(); shape = v13._leaf(data)
    tree, report = v14.prune_frontier(shape, data, 1)
    assert tree == shape
    assert not report['all_supported_classes_preserved']
    assert report['required_class_mask'] == 7


def test_growth_is_reused_across_pruning_penalties_and_cache_is_immutable():
    data = rows(24); fits = v14.SupportedFits(); config = v13.Config(min_sources=2, leaf_penalty=1)
    a = fits.fit(data, config); work = fits.stats['partition_scores']
    fits.fit(data, replace(config, leaf_penalty=2))
    assert fits.stats['partition_scores'] == work and fits.stats['fits'] == 1
    a['policy']['tree']['feature'] = 'broken'
    b = fits.fit(data, config)
    assert b['policy']['tree'].get('feature') != 'broken'
    assert fits.stats['pruning_states'] > 0


def test_class_preserving_hierarchy_still_passes_unchanged_compression_gates():
    data = rows(); config = v13.Config(min_sources=2, gate_mode='regularized')
    result = v14.learn(data, config)
    assert result['root'] and result['root']['metrics']['correct'] == 48
    for node in result['nodes']:
        if node['children']:
            assert node['acceptance']['status'] == 'accepted'
            assert node['acceptance']['compression'] >= .2
            assert node['policy']['search']['pruning']['all_supported_classes_preserved']


def test_supported_runtime_roundtrip_preserves_exact_behavior():
    data = imbalanced(); model = v14.SupportedFits().fit(data, v13.Config(min_sources=2))
    restored = v14.PortableRuleExecutor.from_training_policy(model['policy'])
    assert restored.metadata() == model['runtime']
    assert restored.predict_records([r['features'] for r in data]) == v13.predict(model, data)


@pytest.mark.parametrize('mode', ['direct', 'merge'])
@pytest.mark.parametrize('split', [1, 2, 3])
def test_portable_research_candidates_are_authenticated_without_training_metadata(mode, split):
    root = Path(__file__).resolve().parents[3]
    folder = root / 'examples/calitree_supported_children_v14'
    manifest = json.loads((folder / 'manifest.json').read_text())
    name = f'{mode}_split{split}.json'; artifact = json.loads((folder / name).read_text())
    assert manifest['policies'][name] == digest(artifact)
    executor = v14.PortableRuleExecutor(artifact)
    assert set(artifact) == {'version', 'feature_contract_ref', 'tree', 'predicate_descriptions', 'artifact_ref'}
    assert executor.predict_records([None])[0]['prediction'] == -1
    assert manifest['upstream']['physical_observation'] == 'bound-physical-evidence-v2'
