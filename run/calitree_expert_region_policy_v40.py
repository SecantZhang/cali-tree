"""Protected source-held-out expert-region and domain-weight calibration.

Region features are conjunctions along frozen expert paths, not case-signature
lookups. All original local examples remain in each fit; their exact accuracy
is measured rather than assumed. No new model calls or expert-tree refits.
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import dataset, encoded, Probe, accuracy, VERSION as PARENT_VERSION
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint
from critical.core.calibration import regular_aware_gate_v35 as aware

VERSION = 'protected-expert-region-policy-v40'


def regions(experts):
    result = {}
    for ref, executor in experts.items():
        def visit(node, path):
            if 'prediction' in node:
                key = digest(path)
                if key not in result:
                    result[key] = {'conditions': path, 'contributing_experts': []}
                result[key]['contributing_experts'].append({'expert_ref': ref, 'prediction': node['prediction']})
                return
            for value, side in ((True, 'true'), (False, 'false')):
                visit(node[side], path + [{'feature': node['feature'], 'value': value}])
        visit(executor.artifact['tree'], [])
    return dict(sorted(result.items()))


def region_features(examples, definitions):
    values = []
    for e in examples:
        f = e['features']['features'] if e['features'] is not None else None
        values.append([int(f is not None and all(f[c['feature']] == c['value'] for c in d['conditions'])) for d in definitions.values()])
    return np.asarray(values, dtype=np.float32)


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts = dataset()
    examples = local + recent
    n = len(local)
    names, raw, actions = encoded(examples, experts)
    definitions = regions(experts)
    matrix = np.concatenate((raw, region_features(examples, definitions)), axis=1)
    full_names = names + ['region_' + ref for ref in definitions]
    core = [i for i, name in enumerate(full_names) if name in aware.NAMES or name.startswith(('expert_', 'region_')) or name == 'evidence_missing']
    sets = {'core_regions': core, 'full_regions': list(range(matrix.shape[1]))}
    configs = [{'features': features, 'old_weight': weight, 'max_features': maximum}
               for features in sets for weight in (.1, 1.0) for maximum in ('sqrt', .5)]
    groups = sorted({e['source_group'] for e in recent})
    y = np.asarray([e['reference'] for e in examples], dtype=np.int64)
    protocol = {'version': VERSION, 'parent': PARENT_VERSION, 'configs': configs, 'new_model_calls': 0,
                'region_count': len(definitions), 'expert_refits': 0, 'source_folds': len(groups),
                'training_retention': 'All 99 original cases must remain correct in every fold; original training slots 144.',
                'weighting': 'Original cases receive 0.1 or 1 loss weight. They are never removed; exact retained accuracy is mandatory.',
                'scope': 'Exploratory development on the same reviewed 116 cases. No fresh validation claim.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'region_definitions.json', definitions)
    outcomes, records, folds = {}, [], []
    for number, config in enumerate(configs, 1):
        name = config['features'] + '_' + str(config['old_weight']) + '_' + str(config['max_features'])
        columns = sets[config['features']]
        X = matrix[:, columns]
        weights = np.asarray([config['old_weight']] * n + [1.0] * len(recent))
        local_counts, predictions = [], []
        for fold, group in enumerate(groups):
            train = [i for i, e in enumerate(examples) if e['source_group'] != group]
            held = [i for i, e in enumerate(examples) if i >= n and e['source_group'] == group]
            assert set(range(n)) <= set(train)
            model = Probe('forest', config['max_features']).fit(X[train], y[train], sample_weight=weights[train])
            local_correct = sum(p == e['reference'] for p, e in zip(model.predict(X[:n]), local))
            local_counts.append(local_correct)
            for i, probability in zip(held, model.model.predict_proba(X[held])):
                scores = {int(c): float(p) for c, p in zip(model.model.classes_, probability)}
                direct = max(scores, key=lambda c: (scores[c], -c))
                available = sorted({p for p in actions[i] if p >= 0})
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                predictions.append({'case': e['case'], 'source_group': group, 'cohort': e['cohort'], 'reference': e['reference'],
                                    'regular': e['regular'], 'direct': direct, 'routed': routed, 'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'held_source': group, 'local_correct': local_correct,
                          'training_sources': sorted({examples[i]['source_group'] for i in train})})
        outcomes[name] = {'config': config, 'retains_training': min(local_counts) == 99,
                          'minimum_local_correct': min(local_counts), 'metrics': {}}
        for cohort in ('all', 'pilot80', 'forward36'):
            selected = [r for r in predictions if cohort == 'all' or r['cohort'] == cohort]
            outcomes[name]['metrics'][cohort] = {arm: accuracy(selected, arm) for arm in ('regular', 'direct', 'routed')}
        records.extend(predictions)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': outcomes, 'target_verified': False,
                  'fresh_validation': False, 'new_model_calls': 0})
        print({'candidate': number, 'total': len(configs), 'name': name, 'local_minimum': min(local_counts),
               'direct_correct': outcomes[name]['metrics']['all']['direct']['correct'],
               'routed_correct': outcomes[name]['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(matrix.tolist()),
              'target_ref': digest(y.tolist()), 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__,
                                      ROOT / 'run/calitree_accuracy_headroom_v37.py')},
              'training_sources': sorted({e['source_group'] for e in examples})})
    (out / 'run.log').write_text('Eight bounded expert-region/domain-weight candidates tested source-held-out; retained local accuracy measured in every fit.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
