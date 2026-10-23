"""Compare shared weighted semantic rules with the frozen forest control.

Eight predeclared unary/binary-rule configurations. Fixed five source-group
folds; original 99 cases protected. No source identifiers or raw text predictors.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.semantic_conjunction_policy_v50 import SemanticConjunctionPolicy
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def choices(model, matrix, actions, examples, indices):
    result = []
    for i, probabilities in zip(indices, model.predict_proba(matrix[indices])):
        direct = int(np.argmax(probabilities))
        available = sorted({p for p in actions[i] if p >= 0})
        routed = max(available, key=lambda c: (float(probabilities[c]), -c)) if available else -1
        if examples[i]['features'] is None:
            direct = routed = examples[i]['regular']
        result.append((i, direct, routed))
    return result


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
    configs = [{'degree': d, 'C': c, 'original_weight': w} for d in (1, 2) for c in (1., 10.) for w in (1., 10.)]
    configs += [{'family': 'forest_control', 'original_weight': 1.}]
    protocol = {'version': SemanticConjunctionPolicy.version, 'configs': configs, 'source_folds': 5,
                'new_model_calls': 0, 'source_held_out_cases': 276, 'protected_training_cases': 99,
                'features': 'Training-only deduplicated closed Boolean predicates and regular label indicators. No expert-label inputs, case/source/editor IDs, object names, counts or signature lookups.',
                'conjunctions': 'Explicit products of two different Boolean columns, hence logical AND. Sparse class weights share these conditions across tree paths.',
                'eligibility': 'Check actual routed original predictions, not direct labels alone; all 99 must be retained in every fold. Convergence required.',
                'scope': 'Development comparison only; reserved 80 sources remain untouched.'}
    save_json(out / 'protocol.json', protocol)
    results, records, folds = {}, [], []
    for config in configs:
        name = config.get('family') or f"degree{config['degree']}_C{config['C']}_old{config['original_weight']}"
        weights = np.asarray([config['original_weight']] * n + [1.] * len(recent))
        selected, retention, convergence = [], [], []
        for fold, (train, held) in enumerate(splits):
            columns = feature_columns(names, X, train, 'dedup_noexpert')
            matrix = X[:, columns]
            held_sources = {examples[i]['source_group'] for i in held}
            assert not held_sources & {examples[i]['source_group'] for i in train}
            if config.get('family') == 'forest_control':
                model = Probe('forest', 'sqrt').fit(matrix[train], y[train]).model
                metadata = {'family': 'forest', 'trees': 128, 'converged': True}
            else:
                model = SemanticConjunctionPolicy(config['degree'], config['C']).fit(matrix[train], y[train], sample_weight=weights[train])
                metadata = model.metadata()
            local_predictions = choices(model, matrix, actions, examples, list(range(n)))
            correct = sum(routed == examples[i]['reference'] for i, _, routed in local_predictions)
            retention.append(correct)
            convergence.append(metadata['converged'])
            for i, direct, routed in choices(model, matrix, actions, examples, held):
                e = examples[i]
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_sources),
                          'training_sources': sorted({examples[i]['source_group'] for i in train}),
                          'local_routed_correct': correct, 'features': [names[i] for i in columns], 'model': metadata})
        entry = {'config': config, 'minimum_local_correct': min(retention), 'retains_training': min(retention) == 99,
                 'converged': all(convergence), 'eligible': min(retention) == 99 and all(convergence), 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular', 'direct', 'routed')}
        if config.get('family') == 'forest_control':
            previous = {r['case']: r for r in read(ROOT / 'logs/exps/261020-expanded-simplified-v44/predictions.json') if r['candidate'] == 'dedup_noexpert_sqrt'}
            assert all(r['routed'] == previous[r['case']]['routed'] for r in selected)
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': name, 'minimum_original_correct': min(retention), 'converged': all(convergence),
               'routed_correct': entry['metrics']['all']['routed']['correct'], 'total': len(recent)}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in (__file__,
              ROOT / 'critical/core/calibration/semantic_conjunction_policy_v50.py', ROOT / 'run/calitree_simplified_policy_v44.py')}})
    (out / 'run.log').write_text('Eight sparse semantic-rule variants plus exact forest control, source-held evaluation and executed original-routing retention.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
