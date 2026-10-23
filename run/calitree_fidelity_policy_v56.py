"""Test deterministic image-pair fidelity cues alongside cached semantic facts."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration import perceptual_fidelity_v56 as fidelity
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores, EXPANSION
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def evidence_metadata():
    result = {e['case']: e for e in read(SOURCE / 'manifest.json')['cases']}
    result.update({e['case']: e for e in read(ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/inputs.json')})
    result.update({e['case']: e for e in read(EXPANSION / 'inputs.json')})
    return result


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, raw, actions = encoded(examples, experts)
    metadata = evidence_metadata()
    rows, measurements, images = [], [], {}
    for e in examples:
        m = metadata[e['case']]
        assert m.get('source_group', m.get('group')) == e['source_group']
        evidence = m['evidence']
        for path in evidence.values():
            images[path] = fingerprint(path)
        values = fidelity.statistics(evidence['source_image'], evidence['edited_image'])
        measurements.append({'case': e['case'], 'values': values})
        flags = fidelity.predicates(values)
        rows.append([int(flags[name]) for name in fidelity.SPECS])
    X = np.concatenate((raw, np.asarray(rows, dtype=np.float32)), axis=1)
    names += list(fidelity.SPECS)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    configs = [{'features': f, 'max_features': mf} for f in ('full_fidelity', 'meaning_fidelity', 'context_fidelity') for mf in ('sqrt', .5)]
    configs += [{'features': 'forest_control', 'max_features': 'sqrt'}]
    protocol = {'version': fidelity.VERSION, 'configs': configs, 'source_folds': 5, 'new_model_calls': 0,
                'image_metrics_contract': fidelity.CONTRACT_REF, 'thresholds': fidelity.THRESHOLDS,
                'scope': 'Prior fitting/development image pairs only. No fresh diagnostic outputs, reserved images or serving changes.',
                'metrics': 'Global pixel/color/edge/structure/blur measurements at normalized resolution, with fixed Boolean thresholds. No pixel vectors, image IDs/hashes or coordinates as predictors.',
                'limits': 'These cues do not identify the requested target or claim geometric registration.',
                'retention': 'Actual routed original 99 cases must remain correct in every fit; missing semantic evidence still takes regular fallback.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'image_measurements.json', measurements)
    results, records, folds = {}, [], []
    for config in configs:
        name = config['features'] + '_' + str(config['max_features'])
        allowed = [i for i, f in enumerate(names) if
                   (config['features'] != 'forest_control' or i < raw.shape[1]) and
                   (config['features'] != 'meaning_fidelity' or f.startswith(('meaning_', 'task_', 'requires_', 'judge_', 'evidence_', 'fidelity_'))) and
                   (config['features'] != 'context_fidelity' or f.startswith(('task_', 'requires_', 'judge_', 'evidence_', 'fidelity_')))]
        base_names, base_X = [names[i] for i in allowed], X[:, allowed]
        selected, counts = [], []
        for fold, (train, held) in enumerate(splits):
            columns = feature_columns(base_names, base_X, train, 'dedup_noexpert')
            matrix = base_X[:, columns]
            model = Probe('forest', config['max_features']).fit(matrix[train], y[train]).model
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
            held_sources = {examples[i]['source_group'] for i in held}
            assert not held_sources & {examples[i]['source_group'] for i in train}
            folds.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_sources),
                          'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': local_correct,
                          'features': [base_names[i] for i in columns]})
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == 99, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            selected_rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(selected_rows, arm) for arm in ('regular', 'direct', 'routed')}
        if config['features'] == 'forest_control':
            prior = {r['case']: r for r in read(ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
            assert all(r['routed'] == prior[r['case']]['routed'] for r in selected)
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'minimum_original_correct': min(counts), 'routed_correct': entry['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'image_hashes': images, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, fidelity.__file__)}})
    (out / 'run.log').write_text('Seven deterministic image-cue controls with source-group held evaluation and executed original-case retention. No fresh observer data or paid calls.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
