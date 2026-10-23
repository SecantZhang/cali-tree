"""Independent replay of the small boundary-expert improvement."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.decision.artifacts import save_json
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    root = ROOT / 'logs/exps/261020-boundary-experts-v55'
    for file, expected in read(root / 'manifest.json')['code_hashes'].items():
        assert fingerprint(file) == expected
    predictions = read(root / 'predictions.json')
    results = read(root / 'results.json')['candidates']
    for candidate, result in results.items():
        for cohort, metrics in result['metrics'].items():
            selected = [r for r in predictions if r['candidate'] == candidate and (cohort == 'all' or r['cohort'] == cohort)]
            assert len(selected) == len({r['case'] for r in selected})
            for arm, expected in metrics.items():
                assert accuracy(selected, arm) == expected
    for f in read(root / 'folds.json'):
        assert not set(f['held_sources']) & set(f['training_sources'])
    local, recent, experts, _ = examples_and_scores(True)
    examples = local + recent
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    n = len(local)
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    stored = {r['case']: r for r in predictions if r['candidate'] == 'boundary2'}
    rows, retained = [], []
    for tr, te in splitter.split(np.zeros(len(recent)), y[n:], [e['source_group'] for e in recent]):
        train, held = list(range(n)) + [n + int(i) for i in tr], [n + int(i) for i in te]
        columns = feature_columns(names, X, train, 'dedup_noexpert')
        matrix = X[:, columns]
        model = BoundaryExperts(balanced=True).fit(matrix[train], y[train], sample_weight=np.ones(len(train)))
        local_correct = 0
        for i, p in enumerate(model.predict_proba(matrix[:n], 'minimum')):
            available = sorted({v for v in actions[i] if v >= 0})
            label = max(available, key=lambda c: (float(p[c]), -c)) if available else -1
            local_correct += label == local[i]['reference']
        retained.append(local_correct)
        for i, p in zip(held, model.predict_proba(matrix[held], 'minimum')):
            e = examples[i]
            available = sorted({v for v in actions[i] if v >= 0})
            label = max(available, key=lambda c: (float(p[c]), -c)) if available else -1
            if e['features'] is None:
                label = e['regular']
            assert label == stored[e['case']]['minimum_routed']
            rows.append({'case': e['case'], 'prediction': label, 'reference': e['reference']})
    assert min(retained) == 99 and sum(r['prediction'] == r['reference'] for r in rows) == 216
    full_columns = feature_columns(names, X, list(range(len(examples))), 'dedup_noexpert')
    full = BoundaryExperts(balanced=True).fit(X[:, full_columns], y, sample_weight=np.ones(len(y)))
    full_local = []
    for i, p in enumerate(full.predict_proba(X[:n, full_columns], 'minimum')):
        available = sorted({v for v in actions[i] if v >= 0})
        full_local.append(max(available, key=lambda c: (float(p[c]), -c)))
    assert full_local == [e['reference'] for e in local]
    out.mkdir(parents=True)
    result = {'passed': True, 'candidate': 'boundary2/minimum_routed', 'correct': 216, 'total': 276,
              'accuracy': 216 / 276, 'original_training_minimum_across_folds': min(retained), 'full_fit_original_correct': 99,
              'prior_correct': 215, 'improvement_cases': 1, 'strictly_over_85_requires': 235,
              'target_met': False, 'fresh_validation_performed': False, 'reserved_sources_used': 0, 'new_model_calls': 0,
              'scope': 'Independently replayed development improvement only; serving unchanged.'}
    save_json(out / 'verification.json', result)
    save_json(out / 'predictions.json', rows)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'study_results_sha256': fingerprint(root / 'results.json')})
    (out / 'run.log').write_text('Recounted all boundary study arms, independently refitted all five source-held winning models and full-data original retention.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
