"""Offline replay of the fixed-profile training-only v14/v15 comparison."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration import macro_pruning_v15 as macro
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as base
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as prior
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.union_validation_v12 import folds
from run.calitree_pruning_ablation_v15 import CONFIG, SOURCE
from run.calitree_regularized_v13 import ROOT, read, fingerprint, exact


def audit(out):
    manifest = read(out / 'manifest.json'); assert manifest['protocol_ref'] == digest(read(out / 'protocol.json'))
    for category in ('source_hashes', 'code_hashes'):
        for rel, expected in manifest[category].items():
            assert fingerprint(ROOT / rel) == expected
    all_cases = {}; checked = nodes_checked = 0
    results = read(out / 'results.json')
    for i in (1, 2, 3):
        rows = read(SOURCE / f'split{i}/training_data.json')
        for name in ('v14', 'v15'):
            for mode in ('direct', 'merge'):
                cases = []
                for fold in folds(rows):
                    directory = out / f'split{i}/{name}/{mode}/fold{fold["fold"]}'
                    scope = read(directory / 'scope.json'); model = read(directory / 'model.json')
                    assert scope['train'] == sorted(r['source_group'] for r in fold['train'])
                    assert scope['validation'] == sorted(r['source_group'] for r in fold['validation'])
                    assert not set(scope['train']) & set(scope['validation'])
                    assert scope['training_ref'] == digest(sorted(fold['train'], key=lambda r: r['source_group']))
                    registry = {n['node_id']: n for n in model['nodes']}
                    for node in list(registry.values()) or [model['root']]:
                        cohort = sorted((r for r in fold['train'] if r['source_group'] in node['fit_sources']), key=lambda r: r['source_group'])
                        policy = node['policy']; PortableSemanticTree.restore(policy)
                        assert PortableRuleExecutor.from_training_policy(policy).metadata() == node['runtime']
                        assert policy['training']['source_groups'] == [r['source_group'] for r in cohort]
                        assert policy['training']['feature_ref'] == digest([r['features'] for r in cohort])
                        assert policy['training']['target_ref'] == digest([r['reference'] for r in cohort])
                        ps = base.predict(node, cohort)
                        assert node['metrics'] == base.metrics([p['prediction'] for p in ps], [r['reference'] for r in cohort])
                        tree = prior.grown_tree(node, cohort); selected = [r for r in cohort if r['features'] is not None]
                        penalty = policy['search']['config']['leaf_penalty']
                        if name == 'v15':
                            expected, report = macro.prune_frontier(tree, selected, penalty,
                                target_support=[sum(r['reference'] == k for r in cohort) for k in range(3)])
                        else:
                            expected, report = prior.prune_frontier(tree, selected, penalty)
                        assert expected == policy['tree'] and report == policy['search']['pruning']
                        if node.get('children'):
                            assert node['acceptance'] == base.compression_gate(node, [registry[k] for k in node['children']], cohort, CONFIG)
                            assert node['acceptance']['status'] == 'accepted'
                        nodes_checked += 1
                    root = model['root']
                    if root:
                        assert set(root['fit_sources']) == set(scope['train'])
                    ps = base.predict(root, fold['validation']) if root else [{'prediction': -1, 'reason': 'no_complete_root', 'trace': []} for _ in fold['validation']]
                    expected = [{'case': r['case'], 'source_group': r['source_group'], 'reference': r['reference'], **p} for r, p in zip(fold['validation'], ps)]
                    assert read(directory / 'predictions.json') == expected
                    cases.extend(expected); checked += len(expected)
                key = name + '_' + mode
                assert results['splits'][i - 1]['arms'][key]['metrics'] == base.metrics([r['prediction'] for r in cases], [r['reference'] for r in cases])
                all_cases.setdefault(key, []).extend(cases)
    assert results['pooled'] == {key: base.metrics([r['prediction'] for r in cases], [r['reference'] for r in cases]) for key, cases in all_cases.items()}
    audit_result = {'passed': True, 'prediction_checks': checked, 'node_and_pruning_checks': nodes_checked,
        'source_scope_and_original_targets_verified': True, 'new_model_calls': 0, 'final_set_access': False, 'new_fits': 0}
    save_json(out / 'independent_verification.json', audit_result)
    files = sorted(p.relative_to(out).as_posix() for p in out.glob('**/*.json') if p.name != 'completion_seal.json')
    exact(out / 'completion_seal.json', {'files': {name: fingerprint(out / name) for name in files}})
    print(audit_result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
