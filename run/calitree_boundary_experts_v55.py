"""Test specialized judge boundaries with explicit local-retention constraints."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def decisions(model, matrix, indices, examples, actions):
    proposals = model.proposals(matrix[indices])
    results = [{'new_proposals': p} for p in proposals]
    for aggregation in ('sum', 'product', 'minimum'):
        for row, i, probability in zip(results, indices, model.predict_proba(matrix[indices], aggregation)):
            old = sorted({p for p in actions[i] if p >= 0})
            extended = sorted(set(old) | set(row['new_proposals']))
            direct = int(np.argmax(probability))
            routed = max(old, key=lambda c: (float(probability[c]), -c)) if old else -1
            mixed = max(extended, key=lambda c: (float(probability[c]), -c)) if extended else -1
            if examples[i]['features'] is None:
                direct = routed = mixed = examples[i]['regular']
            row.update({aggregation + '_direct': direct, aggregation + '_routed': routed, aggregation + '_mixed': mixed})
    return results


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    configs = [{'balanced': False, 'max_features': mf, 'original_weight': 1., 'multiclass': False} for mf in ('sqrt', .5)]
    configs += [{'balanced': True, 'max_features': 'sqrt', 'original_weight': w, 'multiclass': m} for w in (1., 5.) for m in (False, True)]
    configs += [{'balanced': False, 'max_features': 'sqrt', 'original_weight': 1., 'multiclass': True}]
    protocol = {'version': BoundaryExperts.version, 'configs': configs, 'source_folds': 5, 'new_model_calls': 0,
                'boundaries': ['No/Partial: meaningful progress', 'Partial/Yes: completion', 'No/Yes: clear failure/full success'],
                'aggregation': ['sum of pairwise support', 'product of support', 'weakest relevant boundary'],
                'new_label_warrant': 'An additional available label must win both relevant pairwise comparisons strictly (>0.5). Cycles and ties propose no new label.',
                'features': 'Same training-only deduplicated semantic/task/regular features as the 215/276 forest; no IDs, object names or expert-label input columns.',
                'scope': 'Cached development study only; no fresh diagnostic fitting, reserved-source evaluation or serving changes.',
                'retention': 'Actual direct/routed/mixed labels measured separately for every original case in every fold.'}
    save_json(out / 'protocol.json', protocol)
    results, records, folds = {}, [], []
    arms = [a + '_' + mode for a in ('sum', 'product', 'minimum') for mode in ('direct', 'routed', 'mixed')]
    for number, config in enumerate(configs):
        name = 'boundary' + str(number)
        weights = np.asarray([config['original_weight']] * n + [1.] * len(recent))
        selected, counts = [], {arm: [] for arm in arms}
        for fold, (train, held) in enumerate(splits):
            columns = feature_columns(names, X, train, 'dedup_noexpert')
            matrix = X[:, columns]
            model = BoundaryExperts(balanced=config['balanced'], max_features=config['max_features'], multiclass=config['multiclass'])
            model.fit(matrix[train], y[train], sample_weight=weights[train])
            actual_local = decisions(model, matrix, list(range(n)), examples, actions)
            for arm in arms:
                counts[arm].append(sum(row[arm] == local[i]['reference'] for i, row in enumerate(actual_local)))
            for i, decision in zip(held, decisions(model, matrix, held, examples, actions)):
                e = examples[i]
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'], 'reference': e['reference'],
                                 'regular': e['regular'], **decision, 'candidate': name, 'fold': fold})
            held_sources = {examples[i]['source_group'] for i in held}
            assert not held_sources & {examples[i]['source_group'] for i in train}
            folds.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_sources),
                          'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': {arm: v[-1] for arm, v in counts.items()},
                          'features': [names[i] for i in columns]})
        entry = {'config': config, 'retention': {arm: {'minimum_original_correct': min(v), 'retains_training': min(v) == 99} for arm, v in counts.items()}, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ['regular'] + arms}
        if number == len(configs) - 1:
            prior = {r['case']: r for r in read(ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
            assert all(r['sum_routed'] == prior[r['case']]['routed'] for r in selected)
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'minimum_original_correct': {arm: min(counts[arm]) for arm in arms},
               'correct': {arm: entry['metrics']['all'][arm]['correct'] for arm in arms}}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'critical/core/calibration/boundary_experts_v55.py')}})
    (out / 'run.log').write_text('Seven boundary-expert/multiclass controls, three declared aggregation rules, actual per-arm original training retention and source exclusion.\n')
    (out / 'llm-histories.log').write_text('Zero model calls; old cached features only.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
