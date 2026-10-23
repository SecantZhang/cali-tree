"""Source-held experiment retaining cached anchoring/view confidence.

Uses only pre-existing Luna evidence. No access to the live v51 diagnostic and
no modification or fitting of its frozen controllers.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration import evidence_visibility_v52 as visibility
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores, EXPANSION
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def cached_visibility(examples):
    records, sources = [], {}
    for e in examples:
        value = None
        if e['features'] is not None:
            case = e['case']
            if case.startswith('N'):
                path = SOURCE / 'extraction/cases' / (case + '.json')
                c = read(path)
                observation = c['observation']['observation']
            else:
                root = EXPANSION / 'cases' if case.startswith('T') else ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/collection/cases'
                path = root / (case + '.json')
                c = read(path)
                observation = c['observation']
            sources[str(path)] = fingerprint(path)
            value = visibility.project(e['program'], observation, observation['image_pair_ref'])
        records.append(value)
    names = list(visibility.SPECS)
    matrix = np.asarray([[int(r['features'][name]) if r is not None else 0 for name in names] for r in records], dtype=np.float32)
    return names, matrix, sources


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, raw, actions = encoded(examples, experts)
    extra_names, extra, sources = cached_visibility(examples)
    X = np.concatenate((raw, extra), axis=1)
    names += extra_names
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent])]
    configs = [{'features': 'full_visibility', 'max_features': mf, 'original_weight': w} for mf in ('sqrt', .5) for w in (1., 10.)]
    configs += [{'features': 'meaning_visibility', 'max_features': mf, 'original_weight': 1.} for mf in ('sqrt', .5)]
    configs += [{'features': 'forest_control', 'max_features': 'sqrt', 'original_weight': 1.}]
    protocol = {'version': visibility.VERSION, 'configs': configs, 'source_folds': 5, 'cases': 276,
                'original_training_cases': 99, 'new_model_calls': 0, 'new_visibility_features': len(extra_names),
                'contract_ref': visibility.CONTRACT_REF, 'v51_teacher_data_access': False,
                'retention': 'Execute the routed label for all original examples in each fit; require 99/99.',
                'scope': 'Offline development using cached Luna observations only; no reserved sources or serving changes.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'visibility_predicates.json', visibility.SPECS)
    results, records, memberships = {}, [], []
    for config in configs:
        name = config['features'] + '_' + str(config['max_features']) + '_' + str(config['original_weight'])
        base_columns = [i for i, f in enumerate(names) if
                        (config['features'] != 'forest_control' or i < raw.shape[1]) and
                        (config['features'] != 'meaning_visibility' or f.startswith(('meaning_', 'task_', 'requires_', 'judge_', 'evidence_', 'visibility_')))]
        base_names, base_matrix = [names[i] for i in base_columns], X[:, base_columns]
        weights = np.asarray([config['original_weight']] * n + [1.] * len(recent))
        selected, counts = [], []
        for fold, (train, held) in enumerate(splits):
            columns = feature_columns(base_names, base_matrix, train, 'dedup_noexpert')
            matrix = base_matrix[:, columns]
            model = Probe('forest', config['max_features']).fit(matrix[train], y[train], sample_weight=weights[train]).model
            local_correct = 0
            for i, probability in enumerate(model.predict_proba(matrix[:n])):
                available = sorted({p for p in actions[i] if p >= 0})
                prediction = max(available, key=lambda c: (float(probability[c]), -c)) if available else -1
                local_correct += prediction == examples[i]['reference']
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
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': local_correct,
                                'selected_features': [base_names[i] for i in columns]})
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == 99, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        if config['features'] == 'forest_control':
            prior = {r['case']: r for r in read(ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
            assert all(r['routed'] == prior[r['case']]['routed'] for r in selected)
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'minimum_original_correct': min(counts), 'routed_correct': entry['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'source_hashes': sources, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__, visibility.__file__)}})
    (out / 'run.log').write_text('Seven cached-evidence visibility comparisons; all fitted source folds exclude held sources and execute original-route retention. Live paired-observer data not accessed.\n')
    (out / 'llm-histories.log').write_text('Zero model calls. Cached Luna evidence only.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
