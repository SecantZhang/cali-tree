"""Training-only matched v14/v15 pruning diagnostic; no final-set access.

The fixed compact/all profile isolates the pruning objective. This is an
exploratory diagnostic after initial training-only screening, not an additional
confirmatory benchmark or a comparison against v14's nested-selected score.
"""
import argparse
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration import macro_pruning_v15 as macro
from critical.core.calibration.semantic_hierarchy import supported_pruning_v14 as prior
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as base
from critical.core.calibration.semantic_hierarchy.union_validation_v12 import folds
from run.calitree_regularized_v13 import ROOT, read, exact, fingerprint

SOURCE = ROOT / 'logs/exps/261018-supported-child-compression-v14'
CONFIG = base.Config(max_depth=3, min_sources=2, leaf_penalty=1, grammar='meaning', quantifier='all', gate_mode='regularized')


def run(out):
    inherited = read(SOURCE / 'manifest.json')
    for group in ('source_hashes', 'code_hashes'):
        for rel, expected in inherited[group].items():
            assert fingerprint(ROOT / rel) == expected, rel
    code = deepcopy(inherited['code_hashes'])
    for p in (Path(__file__).resolve(), Path(macro.__file__).resolve()):
        code[str(p.relative_to(ROOT))] = fingerprint(p)
    protocol = {'version': 'macro-pruning-ablation-v15', 'config': base.asdict(CONFIG),
        'changed_component': 'Fixed-shape pruning objective: errors versus macro-F1, with matching normalized rule penalty.',
        'fixed_components': 'Same grower, majority labels, supported-class constraint, source folds, original references and compression/acceptance gates.',
        'scope': 'Exploratory fixed-profile training-fold diagnostic after initial screening. No nested profile selection or fresh generalization claim.',
        'new_model_calls': 0, 'final_set_access': False}
    manifest = {'protocol_ref': digest(protocol), 'code_hashes': code, 'source_hashes': inherited['source_hashes']}
    exact(out / 'protocol.json', protocol); exact(out / 'manifest.json', manifest)
    collected = {}; reports = []; prediction_checks = nodes_checked = 0
    for i in (1, 2, 3):
        rows = read(SOURCE / f'split{i}/training_data.json'); split_scores = {}
        for name, module in (('v14', prior), ('v15', macro)):
            for mode in ('direct', 'merge'):
                cases = []; available = 0; rule_counts = []; work = []
                for fold in folds(rows):
                    folder = out / f'split{i}/{name}/{mode}/fold{fold["fold"]}'
                    scope = {'train': sorted(r['source_group'] for r in fold['train']),
                             'validation': sorted(r['source_group'] for r in fold['validation']),
                             'training_ref': digest(sorted(fold['train'], key=lambda r: r['source_group']))}
                    assert not set(scope['train']) & set(scope['validation'])
                    exact(folder / 'scope.json', scope)
                    result = read(folder / 'model.json') if (folder / 'model.json').exists() else module.learn(fold['train'], CONFIG, mode=mode)
                    exact(folder / 'model.json', result)
                    root = result['root']; available += root is not None
                    registry = {n['node_id']: n for n in result['nodes']}
                    for n in list(registry.values()) or [root]:
                        assert set(n['fit_sources']) <= set(scope['train'])
                        cohort = sorted((r for r in fold['train'] if r['source_group'] in set(n['fit_sources'])), key=lambda r: r['source_group'])
                        assert n['policy']['training']['feature_ref'] == digest([r['features'] for r in cohort])
                        assert n['policy']['training']['target_ref'] == digest([r['reference'] for r in cohort])
                        if n.get('children'):
                            decision = base.compression_gate(n, [registry[k] for k in n['children']], cohort, CONFIG)
                            assert decision == n['acceptance'] and decision['status'] == 'accepted'
                        nodes_checked += 1
                    ps = base.predict(root, fold['validation']) if root else [{'prediction': -1, 'reason': 'no_complete_root', 'trace': []} for _ in fold['validation']]
                    saved = [{'case': r['case'], 'source_group': r['source_group'], 'reference': r['reference'], **p} for r, p in zip(fold['validation'], ps)]
                    exact(folder / 'predictions.json', saved); cases.extend(saved); prediction_checks += len(saved)
                    if root:
                        rule_counts.append(root['complexity']['rules'])
                    work.append(result['work'])
                key = name + '_' + mode
                m = base.metrics([r['prediction'] for r in cases], [r['reference'] for r in cases])
                split_scores[key] = {'metrics': m, 'feasible_folds': available, 'rules': rule_counts, 'work': work}
                collected.setdefault(key, []).extend(cases)
                print({'split': i, 'arm': key, 'correct': m['correct'], 'partial_correct': m['per_class']['partial']['correct']}, flush=True)
        reports.append({'split': i, 'arms': split_scores})
    results = {'splits': reports, 'pooled': {k: base.metrics([r['prediction'] for r in v], [r['reference'] for r in v]) for k, v in collected.items()},
        'unique_sources': len({r['source_group'] for r in collected['v14_direct']}), 'slots_per_arm': 144,
        'new_model_calls': 0, 'final_set_predictions': 0, 'promoted': False}
    exact(out / 'results.json', results)
    save_json(out / 'verification.json', {'passed': True, 'prediction_checks': prediction_checks, 'scoped_node_checks': nodes_checked,
        'original_targets_unchanged': True, 'source_disjoint_folds': True, 'new_model_calls': 0})
    lines = ['# Macro-F1 pruning diagnostic (v15)', '', protocol['scope'], '',
        '| Split | V14 direct | V15 direct | V14 merged | V15 merged |', '|---|---:|---:|---:|---:|']
    for r in reports:
        lines.append('| ' + str(r['split']) + ' | ' + ' | '.join(str(r['arms'][k]['metrics']['correct']) + '/48'
            for k in ('v14_direct', 'v15_direct', 'v14_merge', 'v15_merge')) + ' |')
    lines += ['', 'All arms use the same fixed compact/all profile, not their individually selected best profile. '
        'The 144 slots cover 98 overlapping training sources. This diagnostic isolates the pruning objective and '
        'does not touch the historical evaluation or consumed final set.', '',
        'Macro-F1 pruning is implemented and unit-tested against exhaustive supported prunings, but this diagnostic '
        'does not establish improved validation. It is not promoted. Detailed class metrics, every fitting scope, '
        'all model lineages and predictions are retained.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print(results['pooled'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    run(parser.parse_args().output_dir.resolve())
