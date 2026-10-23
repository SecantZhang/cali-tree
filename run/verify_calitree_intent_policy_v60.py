"""Independently recount and refit the finer-intent/explanation candidate."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.decision.artifacts import save_json, digest
from sklearn.ensemble import RandomForestClassifier
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_intent_policy_v60 import arrays
from run.calitree_matched_policy_v58 import fixed_splits, THRESHOLDS, ARMS
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDY = ROOT / 'logs/exps/261021-intent-policy-v60'


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    manifest = read(STUDY / 'manifest.json')
    for path, expected in {**manifest['code_hashes'], **manifest['source_hashes']}.items():
        assert fingerprint(path) == expected
    protocol = read(STUDY / 'protocol.json')
    assert digest(protocol) == manifest['protocol_ref'] and len(protocol['configs']) == 10
    local, recent, extra, _, names, X, actions, flags, _ = arrays()
    examples = local + recent + extra
    y = np.asarray([e['reference'] for e in examples])
    assert names == manifest['names'] and digest(X.tolist()) == manifest['features_ref'] and digest(y.tolist()) == manifest['target_ref']
    assert flags == read(STUDY / 'projected_features.json')
    records = read(STUDY / 'predictions.json')
    results = read(STUDY / 'results.json')['candidates']
    folds = read(STUDY / 'folds.json')
    by_case = {e['case']: e for e in recent}
    for candidate, result in results.items():
        rows = [r for r in records if r['candidate'] == candidate]
        assert len(rows) == len({r['case'] for r in rows}) == 276
        assert all(all(r[k] == by_case[r['case']][k] for k in ('source_group', 'reference', 'regular', 'cohort')) for r in rows)
        for cohort, metrics in result['metrics'].items():
            selected = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            for arm in ('regular',) + ARMS:
                assert accuracy(selected, arm) == metrics[arm]
            assert metrics['coverage'] == {str(t): sum(r['accept_' + str(t)] for r in selected) for t in THRESHOLDS}
        for fold, (train, held) in enumerate(fixed_splits(local, recent, extra, result['config']['coverage'])):
            saved = next(f for f in folds if f['candidate'] == candidate and f['fold'] == fold)
            assert saved['train_cases'] == [examples[i]['case'] for i in train] and saved['held_cases'] == [examples[i]['case'] for i in held]
            assert not set(saved['training_sources']) & set(saved['held_sources'])
    selected = read(STUDY / 'selection.json')
    config = results[selected['candidate']]['config']
    allowed = [i for i, name in enumerate(names) if not name.startswith(('intent_', 'rationale_')) or
               (config['features'] != 'control' and name.startswith('intent_')) or (config['features'] == 'both' and name.startswith('rationale_'))]
    base, base_names = X[:, allowed], [names[i] for i in allowed]
    weights = np.ones(len(examples)); weights[:99] = config['original_weight']
    stored = {r['case']: r for r in records if r['candidate'] == selected['candidate']}
    def fit(train):
        cols = feature_columns(base_names, base, train, 'dedup_noexpert')
        model = (RandomForestClassifier(n_estimators=128, bootstrap=False, min_samples_leaf=1, max_features='sqrt', random_state=20261020, n_jobs=2)
                 if config['family'] == 'forest' else BoundaryExperts(balanced=True, max_features='sqrt'))
        return model.fit(base[train][:, cols], y[train], sample_weight=weights[train]), cols
    def replay(model, cols, indices):
        m = base[indices][:, cols]
        ps = model.predict_proba(m) if config['family'] == 'forest' else model.predict_proba(m, 'minimum')
        rows = []
        for i, p in zip(indices, ps):
            e = examples[i]
            available = sorted({a for a in actions[i] if a >= 0})
            label = max(available, key=lambda c: (float(p[c]), -c)) if available else -1
            support = float(p[label]) if label >= 0 else 0.
            covered = e['features'] is not None and label >= 0
            row = {'routed': label if covered else e['regular'], 'direct': int(np.argmax(p)) if covered else e['regular']}
            for t in THRESHOLDS:
                row['gate_' + str(t)] = label if covered and support >= t else e['regular']
            rows.append(row)
        return rows
    retained = []
    for train, held in fixed_splits(local, recent, extra, config['coverage']):
        model, cols = fit(train)
        retained.append(sum(r[selected['arm']] == e['reference'] for r, e in zip(replay(model, cols, list(range(99))), local)))
        for i, row in zip(held, replay(model, cols, held)):
            assert all(row[arm] == stored[examples[i]['case']][arm] for arm in ARMS)
    full = list(range(375 if config['coverage'] == 'zero' else 915))
    model, cols = fit(full)
    originals = replay(model, cols, list(range(99)))
    assert retained == [99] * 5 and all(r[selected['arm']] == e['reference'] for r, e in zip(originals, local))
    original_index = {e['case']: i for i, e in enumerate(local)}
    slots = 0
    for bank in (1, 2, 3):
        for r in old_inputs(PREVIOUS, bank)[3]['local']:
            assert originals[original_index[r['case']]][selected['arm']] == r['reference']
            slots += 1
    assert slots == 144
    result = {'passed': True, 'candidate': selected['candidate'], 'arm': selected['arm'], 'metrics': selected['metrics'],
              'fold_original_correct': retained, 'full_original_correct': 99, 'original_slots_correct': slots,
              'tree_accepted': results[selected['candidate']]['metrics']['all']['coverage'][selected['arm'][5:] if selected['arm'].startswith('gate_') else '0.0'],
              'strictly_over_85_requires': 235, 'target_verified': False, 'fresh_validation_performed': False,
              'new_model_calls': 0, 'reserved_sources_used': 0}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', result)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'study_manifest_sha256': fingerprint(STUDY / 'manifest.json')})
    (out / 'run.log').write_text('Recounted ten screens and source exclusions; independently refitted winner in all folds/full fit; original99 and actual144 slots retained.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
