"""Test learned intent/completion policies and boosting with protected training.

Five fixed source-group folds and one forest control. This is development
screening, not fresh validation; original 99 training cases stay in every fit.
"""
import argparse
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.base import Calibrator
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import dataset, encoded, Probe, accuracy
from run.calitree_expert_region_policy_v40 import regions, region_features, aware
from run.calitree_aurora_pilot_v29 import read, fingerprint

VERSION = 'goal-progress-completion-policy-v41'


def booster():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=.07, max_leaf_nodes=15,
                                         min_samples_leaf=1, l2_regularization=.1, max_bins=2,
                                         early_stopping=False, random_state=20261020)


class ProgressPolicy(Calibrator):
    version = VERSION

    def __init__(self, ordinal):
        self.ordinal = ordinal
        self.intent = booster()
        self.completion = booster() if ordinal else None
        self.classes_ = np.asarray([0, 1, 2])

    def fit(self, X, y, *, sample_weight=None):
        if self.ordinal:
            self.intent.fit(X, y > 0, sample_weight=sample_weight)
            mask = y > 0
            self.completion.fit(X[mask], y[mask] == 2,
                                sample_weight=sample_weight[mask] if sample_weight is not None else None)
        else:
            self.intent.fit(X, y, sample_weight=sample_weight)
        return self

    def predict_proba(self, X):
        if not self.ordinal:
            return self.intent.predict_proba(X)
        progress = self.intent.predict_proba(X)[:, 1]
        complete = self.completion.predict_proba(X)[:, 1]
        return np.stack((1 - progress, progress * (1 - complete), progress * complete), axis=1)

    def predict(self, X):
        return [int(v) for v in np.argmax(self.predict_proba(X), axis=1)]


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts = dataset()
    examples = local + recent
    names, raw, actions = encoded(examples, experts)
    definitions = regions(experts)
    X = np.concatenate((raw, region_features(examples, definitions)), axis=1)
    names += ['region_' + ref for ref in definitions]
    core = [i for i, name in enumerate(names) if name in aware.NAMES or name.startswith(('region_', 'expert_')) or name == 'evidence_missing']
    sets = {'core_regions': core, 'full_regions': list(range(X.shape[1]))}
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    folds = list(splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent]))
    configs = [{'family': family, 'features': features} for features in sets for family in ('flat_boost', 'intent_completion')]
    configs += [{'family': 'forest_control', 'features': 'full_regions'}]
    protocol = {'version': VERSION, 'configs': configs, 'source_group_folds': 5, 'new_model_calls': 0,
                'heads': 'Intent: No versus meaningful fulfillment. Conditional completion: Partial versus Yes among meaningful-fulfillment training cases.',
                'boosting': {'iterations': 300, 'leaves': 15, 'min_samples_leaf': 1, 'l2': .1},
                'retention': 'Require 99/99 original cases in all folds. Do not trade training accuracy for validation accuracy.',
                'scope': 'Development screen on previously reviewed cases. The reserved 80 sources are not read.'}
    save_json(out / 'protocol.json', protocol)
    records, result, membership = [], {}, []
    for config in configs:
        name = config['family'] + '_' + config['features']
        matrix = X[:, sets[config['features']]]
        selected, counts = [], []
        for fold, (train_recent, held_recent) in enumerate(folds):
            train = list(range(n)) + [int(i) + n for i in train_recent]
            held = [int(i) + n for i in held_recent]
            held_groups = {examples[i]['source_group'] for i in held}
            assert not held_groups & {examples[i]['source_group'] for i in train}
            if config['family'] == 'forest_control':
                estimator = Probe('forest', 'sqrt').fit(matrix[train], y[train])
                predictor = estimator.model
            else:
                predictor = ProgressPolicy(config['family'] == 'intent_completion').fit(matrix[train], y[train])
            local_correct = sum(int(p) == e['reference'] for p, e in zip(predictor.predict(matrix[:n]), local))
            counts.append(local_correct)
            for i, probability in zip(held, predictor.predict_proba(matrix[held])):
                scores = {int(c): float(p) for c, p in zip(predictor.classes_, probability)}
                direct = max(scores, key=lambda c: (scores[c], -c))
                available = sorted({p for p in actions[i] if p >= 0})
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'candidate': name, 'fold': fold})
            membership.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_groups),
                               'training_sources': sorted({examples[i]['source_group'] for i in train}), 'local_correct': local_correct})
            print({'candidate': name, 'fold_complete': fold + 1, 'local_correct': local_correct}, flush=True)
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == 99, 'metrics': {}}
        for cohort in ('all', 'pilot80', 'forward36'):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {a: accuracy(rows, a) for a in ('regular', 'direct', 'routed')}
        result[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': result, 'target_verified': False,
                  'fresh_validation': False, 'new_model_calls': 0})
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', membership)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'feature_ref': digest(X.tolist()),
              'target_ref': digest(y.tolist()), 'code_hashes': {str(Path(__file__).resolve()): fingerprint(__file__)}})
    (out / 'run.log').write_text('Fixed five-fold source-group screen; training retention checked for every candidate and fold.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
