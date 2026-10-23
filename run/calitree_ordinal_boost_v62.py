"""Test ordinal/relative-grade learning on the same source-held 276 cases."""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import catboost

from critical.core.calibration.ordinal_boost_v62 import OrdinalBoost
from critical.core.decision.artifacts import save_json, digest
from critical.database.dl_aurora.loader import score_to_label
from run.calitree_intent_policy_v60 import arrays
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_matched_policy_v58 import COLLECTION, fixed_splits, THRESHOLDS, ARMS, decisions
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

CONFIGS = [dict(family=f, depth=d) for f in ('multiclass', 'ordinal', 'relative_mean') for d in (4, 6, 8)]


def fitting_metadata(examples):
    _, _, _, old_means = examples_and_scores(True)
    parents = {entry['parent_case']: uid for uid, entry in read(COLLECTION / 'programs.json').items()}
    means, tasks = [], []
    for e in examples:
        case = e['case']
        mean = float(e['human_score']) if case.startswith('S') else old_means[case]
        assert score_to_label(mean)[0] == e['reference']
        task = e['task_uid'] if case.startswith('S') else parents[case] if case.startswith('N') else 'source_' + e['source_group']
        means.append(mean); tasks.append(task)
    assert len(set(tasks)) == 183 and set(Counter(tasks).values()) == {5}
    return np.asarray(means), np.asarray(tasks)


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    assert catboost.__version__ == '1.2.10'
    local, recent, extra, _, names, X, actions, _, sources = arrays()
    examples = local + recent + extra
    y = np.asarray([e['reference'] for e in examples])
    means, tasks = fitting_metadata(examples)
    original = np.arange(915) < 99
    splits = list(fixed_splits(local, recent, extra, 'full'))
    out.mkdir(parents=True)
    protocol = {'version': OrdinalBoost.version, 'configs': CONFIGS, 'iterations': 1200, 'learning_rate': .05,
                'l2_leaf_reg': 3., 'bootstrap': False, 'random_strength': 0., 'threads': 2, 'seed': 20261021,
                'catboost_version': catboost.__version__, 'features': 'Closed v60 Boolean vocabulary, train-only duplicate/constant removal; no IDs or learned text/image vectors.',
                'objectives': {'multiclass': 'Three-label multiclass cross entropy.',
                               'ordinal': 'Two binary boundaries y>0 and y>1 using all fitting rows; project completion<=progress and derive three class masses.',
                               'relative_mean': 'Shared splits predict released human mean and mean minus SAME-TASK five-editor average. Only fitting task labels used; inference uses the global-mean output with unchanged .5/1.5 bins.'},
                'weight_constraint': 'First protected-original weight 1,5,25 retaining actual original argmax. No held-source labels or early stopping.',
                'folds': 'Unchanged five v58 source folds on primary276; every held-source sibling excluded.',
                'target': 'Strict >85% overall needs235/276, with original99 and144 slots retained.',
                'new_model_calls': 0, 'reserved_sources_used': 0, 'serving_change': False}
    save_json(out / 'protocol.json', protocol)
    results, records, folds = {}, [], []
    for config in CONFIGS:
        name = config['family'] + '_d' + str(config['depth'])
        rows, local_counts = [], []
        for fold, (train, held) in enumerate(splits + [(list(range(915)), [])]):
            cols = feature_columns(names, X, train, 'dedup_noexpert')
            matrix = X[:, cols]
            model = OrdinalBoost(**config).fit(matrix[train], y[train], original=original[train], means=means[train], tasks=tasks[train])
            originals = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(model.predict_proba(matrix[:99]), local))]
            local_counts.append({arm: sum(r[arm] == e['reference'] for r, e in zip(originals, local)) for arm in ARMS})
            if held:
                for i, p in zip(held, model.predict_proba(matrix[held])):
                    e = examples[i]
                    rows.append({k: e[k] for k in ('case', 'source_group', 'cohort', 'reference', 'regular')} |
                                decisions(p, e, actions[i]) | {'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'train_cases': [examples[i]['case'] for i in train],
                          'held_cases': [examples[i]['case'] for i in held],
                          'training_sources': sorted({examples[i]['source_group'] for i in train}),
                          'held_sources': sorted({examples[i]['source_group'] for i in held}),
                          'task_group_sizes': dict(Counter(str(t) for t in tasks[train])),
                          'features': [names[i] for i in cols], 'original_actual_correct': local_counts[-1], 'weight_trials': model.weight_trials})
        retention = {arm: {'fold_original_correct': [r[arm] for r in local_counts[:5]], 'full_original_correct': local_counts[-1][arm]} for arm in ARMS}
        for entry in retention.values():
            entry['retains_training'] = min(entry['fold_original_correct'] + [entry['full_original_correct']]) == 99
        metrics = {}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            metrics[cohort] = {arm: accuracy(rs, arm) for arm in ('regular',) + ARMS}
            metrics[cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rs) for t in THRESHOLDS}
        results[name] = {'config': config, 'retention': retention, 'metrics': metrics}
        records.extend(rows)
        save_json(out / 'results.json', {'candidates': results, 'new_model_calls': 0, 'target_verified': False})
        save_json(out / 'predictions.json', records)
        save_json(out / 'folds.json', folds)
        print({'candidate': name, 'correct': {arm: metrics['all'][arm]['correct'] for arm in ARMS},
               'eligible': {arm: entry['retains_training'] for arm, entry in retention.items()}}, flush=True)
    eligible = [(name, arm, e) for name, e in results.items() for arm in ARMS if e['retention'][arm]['retains_training']]
    eligible.sort(key=lambda item: (-item[2]['metrics']['all'][item[1]]['correct'], -item[2]['metrics']['all'][item[1]]['macro_f1'], item[1] != 'routed', item[0], item[1]))
    name, arm, winner = eligible[0]
    save_json(out / 'selection.json', {'candidate': name, 'arm': arm, 'metrics': winner['metrics']['all'][arm], 'retention': winner['retention'][arm],
              'development_target_exceeded': winner['metrics']['all'][arm]['correct'] >= 235, 'target_verified': False, 'new_model_calls': 0})
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'human_means_ref': digest(means.tolist()), 'task_groups_ref': digest(tasks.tolist()), 'source_hashes': sources,
              'catboost_binary_sha256': fingerprint(catboost._catboost.__file__),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'critical/core/calibration/ordinal_boost_v62.py',
                              ROOT / 'run/calitree_intent_policy_v60.py', ROOT / 'critical/core/calibration/judge_semantics_v60.py')}})
    (out / 'run.log').write_text('Nine fixed shallow symmetric-tree objectives; same276-case source folds, complete five-editor task groups, no evaluation-set fitting/early stopping. Original actual labels checked in every fold/full fit.\n')
    (out / 'llm-histories.log').write_text('Zero model calls. CatBoost1.2.10 installed in an isolated temporary dependency directory.\n')
    print(read(out / 'selection.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
