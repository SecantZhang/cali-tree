"""Source-held-out policies with simpler semantic feature vocabularies.

Fold-local duplicate/constant feature removal learns no case signatures. The
confidence gate falls back to the regular judge. All failures remain counted.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'simplified-semantic-policy-v44'
THRESHOLDS = (0.0, .5, .65, .8, .9)


def feature_columns(names, matrix, train, strategy):
    eligible = [i for i, name in enumerate(names) if
                (strategy != 'meaning' or name.startswith(('meaning_', 'task_', 'requires_', 'judge_', 'expert_', 'evidence_')))
                and (strategy != 'dedup_noexpert' or not name.startswith('expert_'))]
    if strategy == 'meaning':
        return eligible
    columns, seen = [], set()
    for i in eligible:
        values = matrix[train, i]
        if np.all(values == values[0]):
            continue
        signature = values.tobytes()
        if signature not in seen:
            seen.add(signature)
            columns.append(i)
    if not columns:
        raise ValueError('No varying declared features')
    return columns


def run(out, expanded=False):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(expanded)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    groups = sorted({e['source_group'] for e in recent})
    if expanded:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
        splits = [(list(range(n)) + [n + int(i) for i in train], [n + int(i) for i in held])
                  for train, held in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    else:
        splits = [([i for i, e in enumerate(examples) if e['source_group'] != g],
                   [i for i, e in enumerate(examples) if i >= n and e['source_group'] == g]) for g in groups]
    configs = [{'features': strategy, 'max_features': mf} for strategy in ('dedup', 'meaning', 'dedup_noexpert') for mf in ('sqrt', .5)]
    protocol = {'version': VERSION, 'configs': configs, 'expanded': expanded, 'source_folds': len(splits),
                'confidence_thresholds': list(THRESHOLDS), 'trees': 128, 'new_model_calls': 0,
                'scope': 'Development screen; no reserved validation access or serving changes.',
                'feature_simplification': 'Remove constant/identical columns using training rows only, choose earliest declared name. No label-dependent or held-source column selection.',
                'predictors': 'Declared semantic/task predicates and frozen regular/expert labels; no source/case/editor identifiers, object names, or example-signature lookup.',
                'routing': 'Highest policy probability among available expert/regular labels, lower label on ties. Below confidence threshold use regular judge.',
                'retention': 'All 99 original examples remain correct for each proposed gate in every fit.'}
    save_json(out / 'protocol.json', protocol)
    results, records, memberships = {}, [], []
    for config in configs:
        name = config['features'] + '_' + str(config['max_features'])
        selected, counts = [], []
        for fold, (train, held) in enumerate(splits):
            held_sources = {examples[i]['source_group'] for i in held}
            assert not held_sources & {examples[i]['source_group'] for i in train}
            assert set(range(n)) <= set(train)
            columns = feature_columns(names, X, train, config['features'])
            model = Probe('forest', config['max_features']).fit(X[train][:, columns], y[train]).model
            local_probabilities = model.predict_proba(X[:n, columns])
            # With unbootstrapped pure leaves this should be one, but verify it.
            local_correct = sum(int(model.classes_[int(np.argmax(p))]) == e['reference'] and float(max(p)) >= max(THRESHOLDS)
                                for p, e in zip(local_probabilities, local))
            counts.append(local_correct)
            for i, probability in zip(held, model.predict_proba(X[held][:, columns])):
                scores = {int(c): float(p) for c, p in zip(model.classes_, probability)}
                direct = max(scores, key=lambda c: (scores[c], -c))
                available = sorted({p for p in actions[i] if p >= 0})
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                confidence = scores.get(routed, 0)
                covered = e['features'] is not None and routed >= 0
                if not covered:
                    direct = routed = e['regular']
                row = {'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                       'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                       'confidence': confidence, 'candidate': name, 'fold': fold}
                for threshold in THRESHOLDS:
                    row['gate_' + str(threshold)] = routed if covered and confidence >= threshold else e['regular']
                    row['accept_' + str(threshold)] = covered and confidence >= threshold
                selected.append(row)
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_sources),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}),
                                'local_correct_at_all_gate_thresholds': local_correct, 'selected_features': [names[i] for i in columns]})
        entry = {'config': config, 'retains_training': min(counts) == n, 'minimum_local_correct': min(counts), 'metrics': {}}
        arms = ['regular', 'direct', 'routed'] + ['gate_' + str(t) for t in THRESHOLDS]
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in arms}
            entry['metrics'][cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rows) for t in THRESHOLDS}
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': results, 'target_verified': False,
                  'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': name, 'local_minimum': min(counts), 'correct': {a: entry['metrics']['all'][a]['correct'] for a in arms},
               'total': len(recent)}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'run/calitree_accuracy_headroom_v37.py',
                                                                              ROOT / 'run/calitree_continuous_policy_v43.py')}})
    (out / 'run.log').write_text('Six simpler semantic vocabularies and declared confidence gates evaluated with source exclusion and original training protection.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expanded', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.expanded)
