"""Measure the effect of new fitting sources with matched held-source folds.

Predeclared data-volume controls and one original-domain weighting comparison.
No new model calls or reserved validation access.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_aurora_pilot_v29 import ROOT, fingerprint

VERSION = 'matched-source-training-curve-v46'


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    additions = sorted({e['source_group'] for e in recent if e['cohort'] == 'expansion160'}, key=lambda g: digest([VERSION, g]))
    half = set(additions[:len(additions) // 2])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = list(splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent]))
    configs = [{'expansion_fraction': f, 'original_weight': 1.0} for f in (0.0, .5, 1.0)]
    configs += [{'expansion_fraction': 1.0, 'original_weight': .1}]
    protocol = {'version': VERSION, 'configs': configs, 'source_folds': 5, 'evaluation_cases': len(recent),
                'protected_original_cases': n, 'new_model_calls': 0, 'trees': 128,
                'volume_selection': 'Fixed hash-ranked 16-source subset for half-volume, selected without labels or predictions.',
                'comparison': 'Same evaluation rows, source folds, feature vocabulary, model family/seed and fallback policy in all arms.',
                'scope': 'Development learning curve. Reserved 80 sources are not used; no serving change.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'half_volume_sources.json', sorted(half))
    results, records, memberships = {}, [], []
    for config in configs:
        name = str(config['expansion_fraction']) + '_' + str(config['original_weight'])
        weights = np.asarray([config['original_weight']] * n + [1.] * len(recent))
        selected, retention = [], []
        for fold, (train_recent, held_recent) in enumerate(splits):
            train = list(range(n)) + [n + int(i) for i in train_recent if
                    recent[int(i)]['cohort'] != 'expansion160' or config['expansion_fraction'] == 1.0 or
                    (config['expansion_fraction'] == .5 and recent[int(i)]['source_group'] in half)]
            held = [n + int(i) for i in held_recent]
            held_groups = {examples[i]['source_group'] for i in held}
            assert not held_groups & {examples[i]['source_group'] for i in train}
            model = Probe('forest', 'sqrt').fit(X[train], y[train], sample_weight=weights[train]).model
            local_correct = sum(int(p) == e['reference'] for p, e in zip(model.predict(X[:n]), local))
            retention.append(local_correct)
            for i, probability in zip(held, model.predict_proba(X[held])):
                scores = {int(c): float(p) for c, p in zip(model.classes_, probability)}
                direct = max(scores, key=lambda c: (scores[c], -c))
                available = sorted({p for p in actions[i] if p >= 0})
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'candidate': name, 'fold': fold})
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}),
                                'training_cases': len(train), 'local_correct': local_correct})
        entry = {'config': config, 'minimum_local_correct': min(retention), 'retains_training': min(retention) == n, 'metrics': {}}
        for cohort in ('all', 'prior116', 'pilot80', 'forward36', 'expansion160'):
            rows = [r for r in selected if cohort == 'all' or (cohort == 'prior116' and r['cohort'] != 'expansion160') or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': results, 'target_verified': False,
                  'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': name, 'local_minimum': min(retention),
               'routed_correct': {c: m['routed']['correct'] for c, m in entry['metrics'].items()}}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'run/calitree_accuracy_headroom_v37.py', ROOT / 'run/calitree_continuous_policy_v43.py')}})
    (out / 'run.log').write_text('Matched source-group folds compare zero/half/full expansion volume and original-domain weight, preserving original training accuracy.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
