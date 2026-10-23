"""Test continuous input-relative vision and spatial scores without embeddings."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.numeric_semantics_v66 import NumericSemanticPolicy
from critical.core.decision.artifacts import save_json, digest
from run.calitree_intent_policy_v60 import arrays
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_matched_policy_v58 import fixed_splits, decisions, ARMS, THRESHOLDS
from run.calitree_simplified_policy_v44 import feature_columns
from run.paired_vision_features_v63 import BOUNDS
from run.spatial_vision_features_v65 import SCORES, TYPES, CONTRACT_REF as SPATIAL_REF
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VISION = ROOT / 'logs/exps/261021-paired-vision-v63'
SPATIAL = ROOT / 'logs/exps/261021-spatial-vision-v65'
CONFIGS = [dict(family=f, features=features) for features in ('control', 'numeric_vision', 'numeric_geometry') for f in ('forest', 'boundary', 'boost')]
CONFIGS += [dict(family='boost', features='meaning_geometry')]


def numeric_arrays():
    local, recent, extra, experts, names, raw, actions, _, sources = arrays()
    examples = local + recent + extra
    image_names = ['vision_available', 'vision_property_probe_available'] + ['score_' + name for name in BOUNDS]
    spatial_names = ['spatial_' + kind + '_available' for kind in TYPES] + ['score_' + name for name in SCORES]
    encoder_ref = digest(read(VISION / 'encoder_identity.json'))
    image_values, spatial_values = [], []
    for e in examples:
        p = VISION / 'cases' / (e['case'] + '.json')
        q = SPATIAL / 'cases' / (e['case'] + '.json')
        image, spatial = read(p), read(q)
        assert image['encoder_ref'] == spatial['parent_encoder_ref'] == encoder_ref and spatial['contract_ref'] == SPATIAL_REF
        m, s = image['measurements'], spatial['scores']
        image_values.append([1., float(m['property_probe_available'])] + [m[name] for name in BOUNDS])
        spatial_values.append([float(s['spatial_' + kind + '_available']) for kind in TYPES] + [s[name] for name in SCORES])
        sources[str(p)] = fingerprint(p); sources[str(q)] = fingerprint(q)
    X = np.concatenate([raw, np.asarray(image_values, dtype=np.float32), np.asarray(spatial_values, dtype=np.float32)], axis=1)
    return local, recent, extra, experts, names + image_names + spatial_names, X, actions, sources


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, extra, _, names, X, actions, sources = numeric_arrays()
    examples = local + recent + extra
    y, original = np.asarray([e['reference'] for e in examples]), np.arange(915) < 99
    splits = list(fixed_splits(local, recent, extra, 'full')) + [(list(range(915)), [])]
    out.mkdir(parents=True)
    protocol = {'version': NumericSemanticPolicy.version, 'configs': CONFIGS,
                'continuous_inputs': '19 declared global/target/property comparisons plus14 goal-relative geometry scores. No raw coordinates, object identities or image/text embeddings.',
                'thresholds': 'Learn numeric split thresholds from fitting rows only, instead of fixed coarse bins. Non-numeric semantic fields must remain Boolean.',
                'geometry': 'Target/reference localizations from frozen3x3 patch/caption similarity, transformed into requested direction/proximity margins. No certified boxes/depth claim.',
                'local_constraint': 'First original weight1,5,25 retaining actual original argmax; no held-label choice.',
                'evaluation': 'Same276 primary cases,84 sources,5 folds, all held-source siblings excluded. Missing bound semantics keep regular fallback.',
                'models': '128-tree forest/boundary and CatBoost1.2.10 multiclass depth8/1200iterations.',
                'new_paid_model_calls': 0, 'reserved_sources_used': 0, 'serving_change': False}
    save_json(out / 'protocol.json', protocol)
    records, folds, results = [], [], {}
    for config in CONFIGS:
        name, strategy = config['family'] + '_' + config['features'], config['features']
        allowed = [i for i, n in enumerate(names) if
                   (strategy != 'control' or not n.startswith(('vision_', 'score_', 'spatial_'))) and
                   (strategy not in ('control', 'numeric_vision') or not n.startswith(('spatial_', 'score_spatial_'))) and
                   (strategy != 'meaning_geometry' or n.startswith(('meaning_', 'task_', 'requires_', 'intent_', 'rationale_', 'judge_', 'evidence_', 'vision_', 'spatial_', 'score_')))]
        base, base_names = X[:, allowed], [names[i] for i in allowed]
        rows, local_counts = [], []
        for fold, (train, held) in enumerate(splits):
            cols = feature_columns(base_names, base, train, 'dedup_noexpert')
            matrix, features = base[:, cols], [base_names[i] for i in cols]
            model = NumericSemanticPolicy(features, family=config['family']).fit(matrix[train], y[train], original=original[train])
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
                          'features': features, 'weight_trials': model.weight_trials, 'original_actual_correct': local_counts[-1]})
        retention = {arm: {'fold_original_correct': [r[arm] for r in local_counts[:5]], 'full_original_correct': local_counts[-1][arm]} for arm in ARMS}
        for value in retention.values():
            value['retains_training'] = min(value['fold_original_correct'] + [value['full_original_correct']]) == 99
        metrics = {}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            metrics[cohort] = {arm: accuracy(rs, arm) for arm in ('regular',) + ARMS}
            metrics[cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rs) for t in THRESHOLDS}
        if strategy == 'control' and config['family'] == 'boost':
            prior_dir = '261021-ordinal-boost-v62'
            prior_name = 'multiclass_d8'
            old = {r['case']: r for r in read(ROOT / 'logs/exps' / prior_dir / 'predictions.json') if r['candidate'] == prior_name}
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
              'source_hashes': sources, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__,
               ROOT / 'critical/core/calibration/numeric_semantics_v66.py', ROOT / 'run/paired_vision_features_v63.py', ROOT / 'run/spatial_vision_features_v65.py')}})
    (out / 'run.log').write_text('Ten continuous-score/relative-geometry controls with protected original labels; no raw vector, coordinate or identifier inputs. All held-source siblings excluded.\n')
    (out / 'llm-histories.log').write_text('Zero model API requests; existing local-encoder caches reused.\n')
    print(read(out / 'selection.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
