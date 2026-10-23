"""Compare continuous human-score learning with fixed-label classification.

Uses only declared semantic predicates and frozen judge/expert outputs. The
released half-point label thresholds are unchanged. Every held source and its
siblings are excluded together; all original 99 cases remain in every fit.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from critical.database.dl_aurora.loader import score_to_label
from run.calitree_accuracy_headroom_v37 import dataset, encoded, Probe, accuracy
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'continuous-human-score-policy-v43'
EXPANSION = ROOT / 'logs/exps/261020-training-expansion-v42'
RESERVED = ROOT / 'logs/exps/261020-validation-reservation-v39'


def examples_and_scores(expanded=False):
    local, recent, experts = dataset()
    meta = {e['case']: e for e in read(SOURCE / 'manifest.json')['cases']}
    pilot = read(ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/references.json')
    scores = {e['case']: float(meta[e['case']]['human_score']) for e in local + recent if e['case'].startswith('N')}
    scores.update({e['case']: float(pilot[e['case']]['human_score']) for e in recent if e['case'].startswith('P')})
    if expanded:
        additions = read(EXPANSION / 'training_data.json')
        selected = {e['source_group'] for e in additions}
        # Access targets only for the selected fitting sources, never reserved sources.
        catalog = read(ROOT / 'logs/exps/261020-aurora-pilot80-v29/exposure/original/exposure_ledger.json')['tasks']
        lookup = {}
        for source in catalog:
            if source['source_group'] in selected:
                for output in source['outputs']:
                    lookup[(source['source_group'], output['edited_sha256'])] = float(output['human_score'])
        for e in additions:
            scores[e['case']] = lookup[(e['source_group'], fingerprint(e['evidence']['edited_image']))]
        assert not selected & {e['source_group'] for e in local + recent}
        recent += [{**e, 'cohort': 'expansion160'} for e in additions]
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    assert not reserved & {e['source_group'] for e in local + recent}
    assert len({e['case'] for e in local + recent}) == len(local + recent)
    for e in local + recent:
        assert score_to_label(scores[e['case']])[0] == e['reference']
    return local, recent, experts, scores


def fixed_label(score):
    # Remove arithmetic noise at the predeclared boundaries; never tune them.
    return score_to_label(round(float(np.clip(score, 0, 2)), 12))[0]


def run(out, expanded=False):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, means = examples_and_scores(expanded)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    scores = np.asarray([means[e['case']] for e in examples])
    groups = sorted({e['source_group'] for e in recent})
    if expanded:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
        splits = [(list(range(n)) + [n + int(i) for i in train], [n + int(i) for i in held])
                  for train, held in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    else:
        splits = [([i for i, e in enumerate(examples) if e['source_group'] != g],
                   [i for i, e in enumerate(examples) if i >= n and e['source_group'] == g]) for g in groups]
    configs = [{'family': family, 'max_features': maximum} for family in ('regression_forest', 'regression_extra', 'classification_forest')
               for maximum in ('sqrt', .5)]
    protocol = {'version': VERSION, 'configs': configs, 'expanded': expanded, 'protected_training_cases': n,
                'evaluation_cases': len(recent), 'evaluation_sources': len(groups), 'source_group_folds': len(splits),
                'label_thresholds': [.5, 1.5], 'trees': 128, 'bootstrap': False, 'minimum_leaf': 1,
                'new_model_calls': 0, 'reserved_validation_access': False,
                'scope': 'Development comparison only; no fresh validation or serving change.',
                'regression': 'Learn released human means with squared error; convert using unchanged half-point thresholds.',
                'missing_evidence': 'Use regular fallback; count failures in denominator.',
                'routed_regression': 'Choose available expert/regular label nearest predicted mean, lower label on exact tie.',
                'predictors': 'Closed portable/task predicates and frozen expert/regular predictions only.'}
    save_json(out / 'protocol.json', protocol)
    results, records, memberships = {}, [], []
    for config in configs:
        name = config['family'] + '_' + str(config['max_features'])
        selected, retention = [], []
        for fold, (train, held) in enumerate(splits):
            held_groups = {examples[i]['source_group'] for i in held}
            assert not held_groups & {examples[i]['source_group'] for i in train}
            assert set(range(n)) <= set(train)
            if config['family'] == 'classification_forest':
                model = Probe('forest', config['max_features']).fit(X[train], y[train]).model
                local_predictions = model.predict(X[:n])
                probabilities = model.predict_proba(X[held])
            else:
                cls = RandomForestRegressor if config['family'] == 'regression_forest' else ExtraTreesRegressor
                model = cls(n_estimators=128, bootstrap=False, min_samples_leaf=1, max_features=config['max_features'],
                            random_state=20261020, n_jobs=2).fit(X[train], scores[train])
                local_predictions = [fixed_label(p) for p in model.predict(X[:n])]
                probabilities = model.predict(X[held])
            local_correct = sum(int(p) == e['reference'] for p, e in zip(local_predictions, local))
            retention.append(local_correct)
            for i, value in zip(held, probabilities):
                available = sorted({p for p in actions[i] if p >= 0})
                if config['family'] == 'classification_forest':
                    ps = dict(zip((int(v) for v in model.classes_), (float(p) for p in value)))
                    direct = max(ps, key=lambda c: (ps[c], -c))
                    routed = max(available, key=lambda c: (ps[c], -c)) if available else -1
                    predicted_mean = sum(c * p for c, p in ps.items())
                else:
                    predicted_mean = float(value)
                    direct = fixed_label(predicted_mean)
                    routed = min(available, key=lambda c: (abs(c - predicted_mean), c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'predicted_mean': predicted_mean, 'human_mean': means[e['case']], 'candidate': name, 'fold': fold})
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}),
                                'local_correct': local_correct})
        entry = {'config': config, 'retains_training': min(retention) == n, 'minimum_local_correct': min(retention), 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        entry['mean_absolute_error'] = float(np.mean([abs(r['predicted_mean'] - r['human_mean']) for r in selected]))
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': results, 'target_verified': False,
                  'fresh_validation_performed': False, 'new_model_calls': 0})
        print({'candidate': name, 'local_minimum': min(retention), 'direct': entry['metrics']['all']['direct']['correct'],
               'routed': entry['metrics']['all']['routed']['correct'], 'total': len(recent)}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'features.json', {'names': names, 'expert_refs': list(experts)})
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()),
              'means_ref': digest(scores.tolist()), 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'run/calitree_accuracy_headroom_v37.py')},
              'reserved_inputs_sha256': fingerprint(RESERVED / 'inputs_without_labels.json')})
    (out / 'run.log').write_text('Six source-held-out continuous versus categorical policies; original local retention checked in every fold.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expanded', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.expanded)
