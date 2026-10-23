"""Repeat the pre-existing intent/completion boosting screen on enlarged data."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_expert_region_policy_v40 import regions, region_features, aware
from run.calitree_goal_progress_policy_v41 import ProgressPolicy
from run.calitree_aurora_pilot_v29 import ROOT, fingerprint


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, raw, actions = encoded(examples, experts)
    definitions = regions(experts)
    X = np.concatenate((raw, region_features(examples, definitions)), axis=1)
    names += ['region_' + ref for ref in definitions]
    core = [i for i, name in enumerate(names) if name in aware.NAMES or name.startswith(('region_', 'expert_')) or name == 'evidence_missing']
    sets = {'core': core, 'full': list(range(X.shape[1]))}
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = list(splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent]))
    configs = [{'features': f, 'ordinal': o, 'original_weight': 1.} for f in sets for o in (False, True)]
    configs += [{'features': f, 'ordinal': False, 'original_weight': .1} for f in sets]
    protocol = {'version': 'expanded-intent-completion-policy-v48', 'configs': configs, 'source_folds': 5,
                'iterations': 300, 'max_leaves': 15, 'l2': .1, 'minimum_leaf': 1, 'new_model_calls': 0,
                'scope': 'Enlarged-data development only. Same model definitions as v41; no reserved validation access.',
                'retention': 'Original 99 examples must remain correct in every fit; source siblings excluded together.'}
    save_json(out / 'protocol.json', protocol)
    results, records, memberships = {}, [], []
    for config in configs:
        name = config['features'] + '_' + str(config['ordinal']) + '_' + str(config['original_weight'])
        matrix = X[:, sets[config['features']]]
        weights = np.asarray([config['original_weight']] * n + [1.] * len(recent))
        selected, counts = [], []
        for fold, (tr, te) in enumerate(splits):
            train, held = list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te]
            held_groups = {examples[i]['source_group'] for i in held}
            assert not held_groups & {examples[i]['source_group'] for i in train}
            model = ProgressPolicy(config['ordinal']).fit(matrix[train], y[train], sample_weight=weights[train])
            local_correct = sum(int(p) == e['reference'] for p, e in zip(model.predict(matrix[:n]), local))
            counts.append(local_correct)
            for i, probability in zip(held, model.predict_proba(matrix[held])):
                scores = dict(zip(range(3), (float(p) for p in probability)))
                available = sorted({p for p in actions[i] if p >= 0})
                direct = max(scores, key=lambda c: (scores[c], -c))
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'candidate': name, 'fold': fold})
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': local_correct})
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == n, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': name, 'local_minimum': min(counts), 'direct': entry['metrics']['all']['direct']['correct'],
               'routed': entry['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(X.tolist()),
              'target_ref': digest(y.tolist()), 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'run/calitree_goal_progress_policy_v41.py', ROOT / 'run/calitree_continuous_policy_v43.py')}})
    (out / 'run.log').write_text('Six enlarged-data boosting/ordinal screens with original retention and source exclusion checks.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
