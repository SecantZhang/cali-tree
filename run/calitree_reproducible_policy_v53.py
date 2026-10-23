"""Prefer reproducible predicates without using evaluation sources for priors.

Only alternate views of the original 99 fitting cases estimate reproducibility.
The fresh v51 diagnostic is not used for fitting or selection of feature weights.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.predicate_reproducibility_v53 import reproducibility, representative_columns, prior_columns
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_evidence_augmentation_v45 import augment
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    views, provenance, rejected = augment(local)
    local_by_case = {e['case']: e for e in local}
    paired = [local_by_case[e['original_case']] for e in views]
    _, A, _ = encoded(paired, experts)
    _, B, _ = encoded(views, experts)
    scores = reproducibility(A, B, [e['source_group'] for e in views])
    for i, name in enumerate(names):
        if name.startswith(('judge_', 'expert_', 'evidence_')):
            scores[i]['score'] = None
    n = len(local)
    assert not {e['source_group'] for e in views} & {e['source_group'] for e in recent}
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    configs = [{'reliable_representative': False, 'strength': 0, 'scope': 'all', 'uniform': 1},
               {'reliable_representative': True, 'strength': 0, 'scope': 'all', 'uniform': 1},
               {'reliable_representative': False, 'strength': 4, 'scope': 'all', 'uniform': 1},
               {'reliable_representative': True, 'strength': 4, 'scope': 'all', 'uniform': 1},
               {'reliable_representative': True, 'strength': 8, 'scope': 'all', 'uniform': 1},
               {'reliable_representative': True, 'strength': 4, 'scope': 'meaning', 'uniform': 1},
               {'reliable_representative': False, 'strength': 0, 'scope': 'all', 'uniform': 2}]
    protocol = {'version': 'reproducible-semantic-policy-v53', 'configs': configs, 'source_folds': 5, 'new_model_calls': 0,
                'reproducibility_pairs': len(views), 'reproducibility_sources': len({e['source_group'] for e in views}),
                'minimum_positive_and_negative_source_witnesses': 3, 'view_rejections': rejected,
                'prior_estimation': 'Original fitting sources only, without targets or evaluation observations. Regular/expert label reproducibility is unknown, not treated as measured stability.',
                'score': 'Average positive and negative Jaccard agreement; constant/insufficiently witnessed features receive neutral unknown priors.',
                'representatives': 'For columns equal on training rows, optionally choose higher-reproducibility semantic alternatives; maintain the original group order.',
                'prior_sampling': 'Repeat stable feature columns in forest candidate sampling; keep sqrt(original unique column count) candidates per split. No repeated-check counts or case lookups become predictors.',
                'scope': 'Reviewed development only. No fresh diagnostic data or reserved sources are used.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'reproducibility.json', {name: value for name, value in zip(names, scores)})
    results, records, folds = {}, [], []
    for number, config in enumerate(configs):
        name = f'prior{number}'
        selected, counts = [], []
        for fold, (train, held) in enumerate(splits):
            base_columns = representative_columns(names, X, train, scores, config['reliable_representative'])
            base_names = [names[i] for i in base_columns]
            base_scores = [scores[i] for i in base_columns]
            replication = prior_columns(base_names, base_scores, config['strength'], config['scope'], config['uniform'])
            columns = [base_columns[i] for i in replication]
            matrix = X[:, columns]
            maximum = max(1, int(np.sqrt(len(base_columns))))
            model = Probe('forest', maximum).fit(matrix[train], y[train]).model
            local_correct = 0
            for i, probability in enumerate(model.predict_proba(matrix[:n])):
                available = sorted({p for p in actions[i] if p >= 0})
                prediction = max(available, key=lambda c: (float(probability[c]), -c)) if available else -1
                local_correct += prediction == local[i]['reference']
            counts.append(local_correct)
            for i, probability in zip(held, model.predict_proba(matrix[held])):
                available = sorted({p for p in actions[i] if p >= 0})
                direct = int(np.argmax(probability))
                routed = max(available, key=lambda c: (float(probability[c]), -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'], 'reference': e['reference'],
                                 'regular': e['regular'], 'direct': direct, 'routed': routed, 'candidate': name, 'fold': fold})
            held_groups = {examples[i]['source_group'] for i in held}
            assert not held_groups & {examples[i]['source_group'] for i in train}
            folds.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                          'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': local_correct,
                          'base_features': base_names, 'expanded_feature_count': len(columns), 'candidates_per_split': maximum})
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == 99, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        if number == 0:
            prior = {r['case']: r for r in read(ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
            assert all(r['routed'] == prior[r['case']]['routed'] for r in selected)
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'minimum_original_correct': min(counts), 'routed_correct': entry['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'pair_primary_ref': digest(A.tolist()), 'pair_alternative_ref': digest(B.tolist()), 'source_hashes': provenance,
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'critical/core/calibration/predicate_reproducibility_v53.py')}})
    (out / 'run.log').write_text('Seven reproducibility-prior controls, using original-source alternative evidence only; executed original routing retention and source exclusions.\n')
    (out / 'llm-histories.log').write_text('Zero model calls. Fresh v51 diagnostic and reserved evaluation not accessed.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
