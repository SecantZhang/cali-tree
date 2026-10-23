"""Bound cached expert headroom and test source-held-out semantic policies.

Research probe, not a claimed >85% deployment. All 116 recent cases have been
reviewed and are development data. The 99 distinct original training cases stay
in every fit; each evaluation source and all siblings are excluded together.
No model calls, case-ID predictors, signature lookup, or expert-tree refits.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import sklearn
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

from critical.core.calibration.base import Calibrator
from critical.core.calibration import regular_aware_gate_v35 as aware
from critical.core.decision.artifacts import digest, save_json
from run.calitree_disagreement_coverage_v36r1 import inputs, parent_path, context
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'protected-semantic-policy-headroom-v37'
SEED = 20261020


class Probe(Calibrator):
    """Bounded sklearn policy with a closed, externally declared vocabulary."""
    version = VERSION

    def __init__(self, family, max_features):
        if family == 'tree':
            self.model = DecisionTreeClassifier(random_state=SEED, min_samples_leaf=1)
        else:
            cls = RandomForestClassifier if family == 'forest' else ExtraTreesClassifier
            self.model = cls(n_estimators=128, bootstrap=False, max_features=max_features,
                             min_samples_leaf=1, random_state=SEED, n_jobs=2)

    def fit(self, X, y, *, sample_weight=None):
        self.model.fit(X, y, sample_weight=sample_weight)
        return self

    def predict(self, X):
        return [int(v) for v in self.model.predict(X)]


def dataset():
    old = {}
    for bank in (1, 2, 3):
        for e in old_examples(bank):
            if e['case'] in old:
                assert old[e['case']]['features'] == e['features'] and old[e['case']]['reference'] == e['reference']
            old[e['case']] = e
    local = [old[k] for k in sorted(old)]
    recent = inputs()
    assert len(local) == 99 and len(recent) == 116
    assert not {e['source_group'] for e in local} & {e['source_group'] for e in recent}
    experts = {}
    for bank in (1, 2, 3):
        parent = aware.RegularAwareGate.restore(read(parent_path(bank)))
        experts.update(aware.utility.warrant.experts(parent.base))
    assert len(experts) == 9
    return local, recent, dict(sorted(experts.items()))


def encoded(examples, experts):
    names = sorted(aware.fixed.shared.evidence.feature_values(
        next(e['program'] for e in examples if e['features'] is not None),
        next(e['features'] for e in examples if e['features'] is not None)))
    extra = ['evidence_missing'] + [f'judge_predicts_{x}' for x in ('unresolved', 'no', 'partial', 'yes')]
    extra += [f'expert_{i}_predicts_{x}' for i in range(len(experts)) for x in ('unresolved', 'no', 'partial', 'yes')]
    rows, predictions = [], []
    for e in examples:
        values = aware.fixed.shared.evidence.feature_values(e['program'], e['features'])
        votes = [ex.predict_records([e['features']])[0]['prediction'] for ex in experts.values()]
        vector = [int(values[f]) if values is not None else 0 for f in names]
        vector += [int(values is None)]
        vector += [int(e['regular'] == label) for label in (-1, 0, 1, 2)]
        vector += [int(vote == label) for vote in votes for label in (-1, 0, 1, 2)]
        rows.append(vector)
        predictions.append([e['regular'], *votes])
    return names + extra, np.asarray(rows, dtype=np.float32), predictions


def accuracy(rows, key):
    correct = sum(r[key] == r['reference'] for r in rows)
    f1 = []
    for label in (0, 1, 2):
        support = sum(r['reference'] == label for r in rows)
        predicted = sum(r[key] == label for r in rows)
        tp = sum(r[key] == r['reference'] == label for r in rows)
        f1.append(2 * tp / (support + predicted) if support + predicted else 0)
    return {'correct': correct, 'total': len(rows), 'accuracy': correct / len(rows),
            'macro_f1': sum(f1) / 3, 'unresolved': sum(r[key] < 0 for r in rows)}


def headroom(examples, actions):
    result = {}
    for cohort in ('all', 'pilot80', 'forward36'):
        indices = [i for i, e in enumerate(examples) if cohort == 'all' or e['cohort'] == cohort]
        impossible = [examples[i]['case'] for i in indices if examples[i]['reference'] not in actions[i]]
        result[cohort] = {'total': len(indices), 'oracle_correct': len(indices) - len(impossible),
                          'oracle_accuracy': (len(indices) - len(impossible)) / len(indices),
                          'unavailable_correct_label_cases': impossible,
                          'strictly_over_85_percent_requires': int(.85 * len(indices)) + 1}
    return result


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts = dataset()
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples], dtype=np.int64)
    groups = sorted({e['source_group'] for e in recent})
    protected_n = len(local)
    core = [i for i, name in enumerate(names) if name in aware.NAMES or name.startswith('expert_') or name == 'evidence_missing']
    feature_sets = {'core': core, 'full': list(range(len(names)))}
    configs = [{'family': family, 'feature_set': features, 'max_features': mf}
               for features in ('core', 'full') for family in ('forest', 'extra') for mf in ('sqrt', .5)]
    configs += [{'family': 'tree', 'feature_set': 'core', 'max_features': None}]
    protocol = {'version': VERSION, 'seed': SEED, 'configs': configs, 'trees_per_ensemble': 128,
                'folds': len(groups), 'original_training_cases': 99, 'original_training_slots': 144,
                'evaluation_cases': 116, 'new_model_calls': 0, 'parent_tree_refits': 0,
                'criterion': 'Strictly >85% overall evaluated accuracy, including failures/fallbacks; preserve 99/99 distinct local cases underlying all 144 slots.',
                'scope': 'Source-held-out development probe on already reviewed data; not final proof of unseen generalization.',
                'predictors': 'Closed portable/task/evidence predicates, regular prediction and frozen expert predictions. No source/case/editor/dataset-category identifiers or raw text.',
                'missing_evidence': 'Retain regular fallback; no fitted missing-case label shortcut.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'headroom.json', headroom(recent, actions[protected_n:]))
    buckets = defaultdict(list)
    for e, vector in zip(examples, X):
        buckets[digest(vector.tolist())].append(e)
    save_json(out / 'identifiability.json', {'equality_upper_bound': sum(max(Counter(e['reference'] for e in es).values()) for es in buckets.values()),
              'cases': len(examples), 'conflicts': [[{'case': e['case'], 'reference': e['reference']} for e in es] for es in buckets.values() if len({e['reference'] for e in es}) > 1],
              'note': 'Uniqueness bound only. Does not establish learnability, correctness of evidence, or achievable generalization.'})
    candidate_results, predictions, memberships = {}, [], []
    for ci, config in enumerate(configs):
        columns = feature_sets[config['feature_set']]
        matrix = X[:, columns]
        name = f"{config['family']}_{config['feature_set']}_{config['max_features']}"
        retained = []
        records = []
        for fold, group in enumerate(groups):
            held = [i for i, e in enumerate(examples) if i >= protected_n and e['source_group'] == group]
            train = [i for i, e in enumerate(examples) if e['source_group'] != group]
            assert all(i in train for i in range(protected_n))
            model = Probe(config['family'], config['max_features']).fit(matrix[train], y[train])
            local_predictions = model.predict(matrix[:protected_n])
            local_correct = sum(p == e['reference'] for p, e in zip(local_predictions, local))
            retained.append(local_correct)
            probabilities = model.model.predict_proba(matrix[held])
            classes = [int(v) for v in model.model.classes_]
            for i, probability in zip(held, probabilities):
                e = examples[i]
                scores = dict(zip(classes, probability))
                direct = max(classes, key=lambda c: (scores[c], -c))
                available = sorted(set(p for p in actions[i] if p >= 0))
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                if e['features'] is None:
                    direct = routed = e['regular']
                records.append({'case': e['case'], 'source_group': group, 'cohort': e['cohort'],
                                'reference': e['reference'], 'regular': e['regular'], 'direct': direct,
                                'routed': routed, 'candidate': name, 'fold': fold})
            memberships.append({'candidate': name, 'fold': fold, 'held_source': group, 'held_cases': [examples[i]['case'] for i in held],
                                'training_case_count': len(train), 'training_sources': sorted({examples[i]['source_group'] for i in train}),
                                'protected_correct': local_correct})
        eligible = all(v == 99 for v in retained)
        result = {'config': config, 'feature_count': len(columns), 'retains_training_accuracy': eligible,
                  'minimum_local_correct_across_folds': min(retained), 'metrics': {}}
        for cohort in ('all', 'pilot80', 'forward36'):
            selected = [r for r in records if cohort == 'all' or r['cohort'] == cohort]
            result['metrics'][cohort] = {arm: accuracy(selected, arm) for arm in ('regular', 'direct', 'routed')}
        candidate_results[name] = result
        predictions.extend(records)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': candidate_results, 'target_verified': False,
                  'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': ci + 1, 'total': len(configs), 'name': name, 'retains_training': eligible,
               'direct_correct': result['metrics']['all']['direct']['correct'], 'routed_correct': result['metrics']['all']['routed']['correct']}, flush=True)
    save_json(out / 'predictions.json', predictions)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'features.json', {'names': names, 'core_indices': core, 'expert_refs': list(experts)})
    source_paths = [ROOT / 'logs/exps/261020-disagreement-coverage-v36-r1/completion_seal.json',
                    ROOT / 'logs/exps/261020-guarded-forward-v32-r1/completion_seal.json']
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'code_hashes': {str(Path(__file__).resolve()): fingerprint(__file__)},
              'source_hashes': {str(p): fingerprint(p) for p in source_paths}, 'sklearn_version': sklearn.__version__,
              'numpy_version': np.__version__, 'input_features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist())})
    (out / 'run.log').write_text('Nine bounded source-held-out semantic policy/router probes; original training retained check in every fold.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
