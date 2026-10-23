"""Recount enlarged screens and independently verify actual routing retention.

Regression's fixed label thresholds differ from its nearest-action tie rule.
The v44 screen conservatively required confidence >=.9 instead of checking the
actual fallback label. This audit resolves eligibility using executed decisions.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores, fixed_label
from run.calitree_simplified_policy_v44 import feature_columns, THRESHOLDS
from run.calitree_evidence_augmentation_v45 import augment
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDIES = {'continuous': '261020-expanded-continuous-v43', 'simplified': '261020-expanded-simplified-v44',
           'augmentation': '261020-expanded-augmentation-v45', 'curve': '261020-training-curve-v46',
           'boost': '261020-expanded-boost-policy-v48'}


def route(probability, classes, available):
    scores = dict(zip((int(c) for c in classes), (float(p) for p in probability)))
    valid = sorted({p for p in available if p >= 0})
    label = max(valid, key=lambda c: (scores[c], -c)) if valid else -1
    return label, scores.get(label, 0.)


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    local, recent, experts, means = examples_and_scores(True)
    primary = local + recent
    n = len(local)
    names, X, actions = encoded(primary, experts)
    y = np.asarray([e['reference'] for e in primary])
    by_case = {e['case']: e for e in recent}
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    results, predictions, counted = {}, {}, 0
    for kind, name in STUDIES.items():
        root = ROOT / 'logs/exps' / name
        manifest = read(root / 'manifest.json')
        for path, sha in manifest['code_hashes'].items():
            assert fingerprint(path) == sha, path
        results[kind] = read(root / 'results.json')['candidates']
        predictions[kind] = read(root / 'predictions.json')
        for candidate, expected in results[kind].items():
            rows = [r for r in predictions[kind] if r['candidate'] == candidate]
            assert len(rows) == len({r['case'] for r in rows}) == 276
            for r in rows:
                assert all(r[k] == by_case[r['case']][k] for k in ('source_group', 'reference', 'regular', 'cohort'))
            for cohort, metrics in expected['metrics'].items():
                selected = [r for r in rows if cohort == 'all' or r['cohort'] == cohort or
                            (cohort == 'prior116' and r['cohort'] != 'expansion160')]
                for arm, expected_metric in metrics.items():
                    if arm != 'coverage':
                        assert accuracy(selected, arm) == expected_metric
            counted += 1
        for fold in read(root / 'folds.json'):
            assert not set(fold['held_sources']) & set(fold['training_sources'])

    # Execute all simplified-policy training/fallback decisions; don't equate
    # lower confidence with a wrong fallback or with a wrong routed prediction.
    simplified = {}
    for name, expected in results['simplified'].items():
        config = expected['config']
        stored = {r['case']: r for r in predictions['simplified'] if r['candidate'] == name}
        counts = {arm: [] for arm in ['routed'] + ['gate_' + str(t) for t in THRESHOLDS]}
        for fold, (train, held) in enumerate(splits):
            columns = feature_columns(names, X, train, config['features'])
            model = Probe('forest', config['max_features']).fit(X[train][:, columns], y[train]).model
            local_rows = []
            for i, p in enumerate(model.predict_proba(X[:n, columns])):
                label, confidence = route(p, model.classes_, actions[i])
                local_rows.append({'routed': label, **{'gate_' + str(t): label if confidence >= t else local[i]['regular'] for t in THRESHOLDS}})
            for arm in counts:
                counts[arm].append(sum(r[arm] == e['reference'] for r, e in zip(local_rows, local)))
            for i, p in zip(held, model.predict_proba(X[held][:, columns])):
                label, confidence = route(p, model.classes_, actions[i])
                if primary[i]['features'] is None:
                    label = primary[i]['regular']
                assert label == stored[primary[i]['case']]['routed']
        simplified[name] = {arm: {'minimum_local_correct': min(values), 'retains_training': min(values) == 99}
                            for arm, values in counts.items()}

    # A single replicated fold with a failing original case disproves the
    # all-fold routing-retention claim. Direct regression retention is separate.
    regression = {}
    for expanded, directory in ((False, '261020-continuous-policy-v43'), (True, STUDIES['continuous'])):
        loc, rec, ex, ms = examples_and_scores(expanded)
        es = loc + rec
        _, matrix, available = encoded(es, ex)
        target = np.asarray([ms[e['case']] for e in es])
        root = ROOT / 'logs/exps' / directory
        folds = read(root / 'folds.json')
        for name, expected in read(root / 'results.json')['candidates'].items():
            config = expected['config']
            if not config['family'].startswith('regression_'):
                continue
            f = next(f for f in folds if f['candidate'] == name and f['fold'] == 0)
            train = [i for i, e in enumerate(es) if e['source_group'] in f['training_sources']]
            cls = RandomForestRegressor if config['family'] == 'regression_forest' else ExtraTreesRegressor
            model = cls(n_estimators=128, bootstrap=False, min_samples_leaf=1, max_features=config['max_features'],
                        random_state=20261020, n_jobs=2).fit(matrix[train], target[train])
            failures, direct_correct = [], 0
            for i, value in enumerate(model.predict(matrix[:len(loc)])):
                direct_correct += fixed_label(value) == loc[i]['reference']
                options = sorted({p for p in available[i] if p >= 0})
                selected = min(options, key=lambda c: (abs(c - float(value)), c)) if options else -1
                if selected != loc[i]['reference']:
                    failures.append({'case': loc[i]['case'], 'predicted_mean': float(value), 'routed': selected,
                                     'reference': loc[i]['reference']})
            assert direct_correct == 99 and failures
            regression[directory + '/' + name] = {'direct_correct_in_reproduced_fold': direct_correct,
                'routed_correct_in_reproduced_fold': 99 - len(failures), 'routed_retains_training': False,
                'routing_failures': failures, 'note': 'One failing fold suffices to reject the all-fold guarantee; not a claimed minimum across every fold.'}

    eligible = []
    for kind, candidates in results.items():
        for name, expected in candidates.items():
            if kind == 'continuous' and expected['config']['family'].startswith('regression_'):
                continue
            arms = ['routed'] + (['gate_' + str(t) for t in THRESHOLDS] if kind == 'simplified' else [])
            for arm in arms:
                retained = simplified[name][arm]['retains_training'] if kind == 'simplified' else expected['minimum_local_correct'] == 99
                if retained:
                    eligible.append({'study': kind, 'candidate': name, 'arm': arm,
                                     **expected['metrics']['all'][arm]})
    best = sorted(eligible, key=lambda r: (-r['correct'], -r['macro_f1'], r['study'], r['candidate'], r['arm']))[0]
    if best['study'] == 'augmentation':
        views, _, _ = augment(primary)
        es = primary + views
        _, matrix, available = encoded(es, experts)
        target = np.asarray([e['reference'] for e in es])
        config = results['augmentation'][best['candidate']]['config']
        weights = np.asarray([1.] * len(primary) + [config['view_weight']] * len(views))
        stored = {r['case']: r for r in predictions['augmentation'] if r['candidate'] == best['candidate']}
        for train_primary, held in splits:
            held_groups = {es[i]['source_group'] for i in held}
            train = [i for i, e in enumerate(es) if e['source_group'] not in held_groups and weights[i] > 0]
            model = Probe('forest', config['max_features']).fit(matrix[train], target[train], sample_weight=weights[train]).model
            assert list(model.predict(matrix[:n])) == [e['reference'] for e in local]
            for i, p in zip(held, model.predict_proba(matrix[held])):
                label, _ = route(p, model.classes_, available[i])
                if es[i]['features'] is None:
                    label = es[i]['regular']
                assert label == stored[es[i]['case']]['routed']
    else:
        assert best['study'] == 'simplified', 'Add independent replay for a new winning family before claiming verified selection'
    prior = read(ROOT / 'logs/exps/261020-accuracy-development-audit-v37-r1/verification.json')
    assert prior['original_training_slots_verified'] == 144
    result = {'passed': True, 'configurations_recounted': counted, 'development_cases': 276, 'development_sources': 84,
              'original_training_cases': 99, 'original_training_slots': 144, 'best_verified_routed_policy': best,
              'target_strictly_over_85_requires': 235, 'target_met': best['correct'] >= 235,
              'fresh_validation_performed': False, 'reserved_sources_used': 0, 'new_model_calls': 0,
              'eligibility_corrections': 'Regression nearest-action ties fail original routing retention; simplified-policy eligibility now follows actual fallback decisions.'}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', result)
    save_json(out / 'simplified_actual_retention.json', simplified)
    save_json(out / 'regression_routing_counterexamples.json', regression)
    save_json(out / 'eligible_policies.json', eligible)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__),
              'source_results': {name: fingerprint(ROOT / 'logs/exps' / name / 'results.json') for name in STUDIES.values()}})
    (out / 'run.log').write_text('Recounted all enlarged screens; replayed simplified routes and actual fallback retention; disproved regression routing retention with counterexamples; independently reproduced the strongest eligible router.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
