"""Compare frozen local-vision measurements on the unchanged source-held cases."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.ordinal_boost_v62 import OrdinalBoost
from critical.core.decision.artifacts import save_json, digest
from run.calitree_intent_policy_v60 import arrays
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_matched_policy_v58 import fixed_splits, model_for, probabilities, decisions, ARMS, THRESHOLDS
from run.calitree_simplified_policy_v44 import feature_columns
from run.paired_vision_features_v63 import SPECS, predicates, CONTRACT_REF
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VISION = ROOT / 'logs/exps/261021-paired-vision-v63'
CONFIGS = [dict(family=family, features='control') for family in ('forest', 'boundary', 'boost')]
CONFIGS += [dict(family=family, features=features) for features in ('full_vision', 'meaning_vision') for family in ('forest', 'boundary', 'boost')]
CONFIGS += [dict(family='forest', features='vision_context')]


def visual_arrays():
    local, recent, extra, experts, names, raw, actions, flags, sources = arrays()
    examples = local + recent + extra
    assert read(VISION / 'results.json')['cases'] == 915
    identity = digest(read(VISION / 'encoder_identity.json'))
    vision_names, values = list(SPECS), []
    for e in examples:
        path = VISION / 'cases' / (e['case'] + '.json')
        record = read(path)
        assert record['case'] == e['case'] and record['encoder_ref'] == identity
        assert predicates(record['measurements']) == record['features']
        values.append([int(record['features'][name]) for name in vision_names])
        sources[str(path)] = fingerprint(path)
    return local, recent, extra, experts, names + vision_names, np.concatenate([raw, np.asarray(values, dtype=np.float32)], axis=1), actions, sources


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, extra, _, names, X, actions, sources = visual_arrays()
    examples = local + recent + extra
    y, original = np.asarray([e['reference'] for e in examples]), np.arange(915) < 99
    splits = list(fixed_splits(local, recent, extra, 'full')) + [(list(range(915)), [])]
    out.mkdir(parents=True)
    protocol = {'version': 'paired-vision-semantic-policy-v64', 'configs': CONFIGS, 'vision_contract': CONTRACT_REF,
                'cases': 276, 'source_groups': 84, 'original_cases': 99, 'original_slots': 144,
                'splits': 'Same fixed five primary source folds; all held-source siblings excluded.',
                'features': 'Closed v60 predicates plus173 fixed scalar-comparison vision predicates. No image/text embeddings, IDs or raw coordinates enter fitting.',
                'models': 'Existing128-tree forest/boundary at original weight5, plus CatBoost1.2.10 multiclass depth8/1200 iterations with train-only original weight selection1,5,25.',
                'missing': 'Unchanged regular fallback for missing bound semantic evidence; failed cases included.',
                'new_paid_model_calls': 0, 'reserved_sources_used': 0, 'serving_change': False}
    save_json(out / 'protocol.json', protocol)
    results, records, folds = {}, [], []
    for config in CONFIGS:
        name = config['family'] + '_' + config['features']
        strategy = config['features']
        allowed = [i for i, n in enumerate(names) if
                   (strategy != 'control' or not n.startswith('vision_')) and
                   (strategy != 'meaning_vision' or n.startswith(('meaning_', 'task_', 'requires_', 'intent_', 'rationale_', 'vision_', 'judge_', 'evidence_'))) and
                   (strategy != 'vision_context' or n.startswith(('task_', 'intent_', 'rationale_', 'vision_', 'judge_', 'evidence_')))]
        base, base_names = X[:, allowed], [names[i] for i in allowed]
        rows, local_counts = [], []
        for fold, (train, held) in enumerate(splits):
            cols = feature_columns(base_names, base, train, 'dedup_noexpert')
            matrix = base[:, cols]
            if config['family'] == 'boost':
                model = OrdinalBoost(family='multiclass', depth=8).fit(matrix[train], y[train], original=original[train])
                weight, family = model.original_weight, 'forest'
            else:
                family = config['family']
                weights = np.where(original[train], 5., 1.)
                model = model_for({'family': family}).fit(matrix[train], y[train], sample_weight=weights)
                weight = 5.
            predict = lambda indices: probabilities(model, matrix[indices], family)
            originals = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(predict(list(range(99))), local))]
            local_counts.append({arm: sum(r[arm] == e['reference'] for r, e in zip(originals, local)) for arm in ARMS})
            if held:
                for i, p in zip(held, predict(held)):
                    e = examples[i]
                    rows.append({k: e[k] for k in ('case', 'source_group', 'cohort', 'reference', 'regular')} |
                                decisions(p, e, actions[i]) | {'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'train_cases': [examples[i]['case'] for i in train],
                          'held_cases': [examples[i]['case'] for i in held],
                          'training_sources': sorted({examples[i]['source_group'] for i in train}),
                          'held_sources': sorted({examples[i]['source_group'] for i in held}),
                          'selected_features': [base_names[i] for i in cols],
                          'original_weight': weight, 'original_actual_correct': local_counts[-1]})
        retention = {arm: {'fold_original_correct': [r[arm] for r in local_counts[:5]], 'full_original_correct': local_counts[-1][arm]} for arm in ARMS}
        for value in retention.values():
            value['retains_training'] = min(value['fold_original_correct'] + [value['full_original_correct']]) == 99
        metrics = {}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            metrics[cohort] = {arm: accuracy(rs, arm) for arm in ('regular',) + ARMS}
            metrics[cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rs) for t in THRESHOLDS}
        if strategy == 'control':
            p = ROOT / ('logs/exps/261021-ordinal-boost-v62/predictions.json' if config['family'] == 'boost' else 'logs/exps/261021-intent-policy-v60/predictions.json')
            candidate = 'multiclass_d8' if config['family'] == 'boost' else config['family'] + '_full_both'
            old = {r['case']: r for r in read(p) if r['candidate'] == candidate}
            assert all(r[arm] == old[r['case']][arm] for r in rows for arm in ARMS)
        results[name] = {'config': config, 'retention': retention, 'metrics': metrics}
        records.extend(rows)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        save_json(out / 'predictions.json', records)
        save_json(out / 'folds.json', folds)
        print({'candidate': name, 'correct': {arm: metrics['all'][arm]['correct'] for arm in ARMS},
               'eligible': {arm: value['retains_training'] for arm, value in retention.items()}}, flush=True)
    eligible = [(name, arm, e) for name, e in results.items() for arm in ARMS if e['retention'][arm]['retains_training']]
    eligible.sort(key=lambda item: (-item[2]['metrics']['all'][item[1]]['correct'], -item[2]['metrics']['all'][item[1]]['macro_f1'], item[1] != 'routed', item[0], item[1]))
    name, arm, winner = eligible[0]
    save_json(out / 'selection.json', {'candidate': name, 'arm': arm, 'metrics': winner['metrics']['all'][arm], 'retention': winner['retention'][arm],
              'development_target_exceeded': winner['metrics']['all'][arm]['correct'] >= 235, 'target_verified': False, 'new_model_calls': 0})
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'source_hashes': sources, 'encoder_identity_sha256': fingerprint(VISION / 'encoder_identity.json'),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, ROOT / 'run/paired_vision_features_v63.py',
                              ROOT / 'critical/core/calibration/ordinal_boost_v62.py', ROOT / 'run/calitree_intent_policy_v60.py')}})
    (out / 'run.log').write_text('Ten paired-vision classifier controls; all source siblings excluded; no raw embedding/identifier input; every original actual route checked.\n')
    (out / 'llm-histories.log').write_text('Zero model calls; local frozen vision measurements only.\n')
    print(read(out / 'selection.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
