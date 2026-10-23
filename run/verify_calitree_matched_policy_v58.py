"""Recount matched-editor comparisons and independently refit the winner."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.decision.artifacts import save_json, digest
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores, RESERVED
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_fallback_routing_v34 import old_examples, old_inputs, PREVIOUS
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

STUDY = ROOT / 'logs/exps/261021-matched-policy-v58'
COLLECTION = ROOT / 'logs/exps/261021-sibling-training-v57'


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    prep = read(STUDY / 'preparation.json')
    assert prep['prepared_before_collection_completed'] is True
    for p, expected in prep['code_hashes'].items():
        assert fingerprint(p) == expected
    assert prep['collection_manifest_sha256'] == fingerprint(COLLECTION / 'manifest.json')
    local, recent, experts, _ = examples_and_scores(True)
    extra = [{**e, 'cohort': 'matched540'} for e in read(COLLECTION / 'training_data.json')]
    examples = local + recent + extra
    by_case = {e['case']: e for e in examples}
    assert len(by_case) == 915
    assert not {e['source_group'] for e in examples} & {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    manifest = read(STUDY / 'manifest.json')
    assert manifest['primary_cases'] == [e['case'] for e in recent]
    assert manifest['protected_cases'] == [e['case'] for e in local]
    assert manifest['training_data_sha256'] == fingerprint(COLLECTION / 'training_data.json')
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    assert digest(X.tolist()) == manifest['features_ref'] and digest(y.tolist()) == manifest['targets_ref']
    assert names == manifest['features']
    protocol = read(STUDY / 'protocol.json')
    assert digest(protocol) == manifest['protocol_ref']
    # Rebuild half selection independently of the study's selection helper.
    selected = set()
    for uid in sorted({e['task_uid'] for e in extra}):
        siblings = [e for e in extra if e['task_uid'] == uid]
        assert len(siblings) == len({e['editor'] for e in siblings}) == 4
        ordered = sorted(siblings, key=lambda e: digest(['v58-half', uid, e['editor']]))
        selected.update(e['case'] for e in ordered[:2])
    assert len(selected) == 270 and sorted(selected) == manifest['half_cases']
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = [(list(range(99)) + [99 + int(i) for i in tr], [99 + int(i) for i in te])
              for tr, te in splitter.split(np.zeros(276), y[99:375], [e['source_group'] for e in recent])]
    results = read(STUDY / 'results.json')['candidates']
    predictions = read(STUDY / 'predictions.json')
    folds = read(STUDY / 'folds.json')
    assert len(results) == len(protocol['configs']) == 8 and len(folds) == 40
    arms = ['direct', 'routed'] + ['gate_' + str(t) for t in protocol['thresholds']]
    for candidate, entry in results.items():
        rows = [r for r in predictions if r['candidate'] == candidate]
        assert len(rows) == len({r['case'] for r in rows}) == 276
        assert {r['case'] for r in rows} == {e['case'] for e in recent}
        for r in rows:
            assert all(r[k] == by_case[r['case']][k] for k in ('reference', 'source_group', 'cohort', 'regular'))
        for cohort, metrics in entry['metrics'].items():
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            for arm in ['regular'] + arms:
                expected = metrics[arm]
                assert accuracy(rs, arm) == {k: v for k, v in expected.items() if k != 'class_recall'}
                if 'class_recall' in expected:
                    assert expected['class_recall'] == [sum(r[arm] == c == r['reference'] for r in rs) / sum(r['reference'] == c for r in rs) for c in (0, 1, 2)]
            assert metrics['coverage'] == {str(t): sum(r['accept_' + str(t)] for r in rs) for t in protocol['thresholds']}
        for fold, (base_train, held) in enumerate(splits):
            f = next(f for f in folds if f['candidate'] == candidate and f['fold'] == fold)
            held_sources = {examples[i]['source_group'] for i in held}
            cfg = entry['config']
            allowed = set() if cfg['coverage'] == 'zero' else selected if cfg['coverage'] == 'half' else {e['case'] for e in extra}
            train = base_train + [375 + i for i, e in enumerate(extra) if e['case'] in allowed and e['source_group'] not in held_sources]
            assert f['train_cases'] == [examples[i]['case'] for i in train]
            assert f['held_cases'] == [examples[i]['case'] for i in held]
            assert f['held_sources'] == sorted(held_sources)
            assert f['training_sources'] == sorted({examples[i]['source_group'] for i in train})
            assert not held_sources & set(f['training_sources'])
            cols = feature_columns(names, X, train, 'dedup_noexpert')
            assert f['selected_features'] == [names[i] for i in cols]
    winner = read(STUDY / 'selection.json')
    eligible = [(candidate, arm, entry) for candidate, entry in results.items() for arm in arms if entry['retention'][arm]['retains_training']]
    ordered = sorted(eligible, key=lambda item: (-item[2]['metrics']['all'][item[1]]['correct'],
                     -item[2]['metrics']['all'][item[1]]['macro_f1'], item[1] != 'routed',
                     {'zero': 0, 'half': 270, 'full': 540}[item[2]['config']['coverage']],
                     item[2]['config']['original_weight'], item[0], item[1]))
    assert (winner['candidate'], winner['arm']) == ordered[0][:2]
    assert winner['metrics'] == results[winner['candidate']]['metrics']['all'][winner['arm']]
    assert winner['original_retention'] == results[winner['candidate']]['retention'][winner['arm']]
    cfg = results[winner['candidate']]['config']
    selected_extra = set() if cfg['coverage'] == 'zero' else selected if cfg['coverage'] == 'half' else {e['case'] for e in extra}
    records = {r['case']: r for r in predictions if r['candidate'] == winner['candidate']}
    weights = np.ones(len(examples))
    weights[:99] = cfg['original_weight']
    def fit(train):
        cols = feature_columns(names, X, train, 'dedup_noexpert')
        if cfg['family'] == 'forest':
            model = RandomForestClassifier(n_estimators=128, bootstrap=False, min_samples_leaf=1,
                        max_features='sqrt', random_state=20261020, n_jobs=2)
        else:
            model = BoundaryExperts(balanced=True, max_features='sqrt')
        model.fit(X[train][:, cols], y[train], sample_weight=weights[train])
        return model, cols
    def decide(p, i):
        e = examples[i]
        available = sorted({a for a in actions[i] if a >= 0})
        label = max(available, key=lambda c: (float(p[c]), -c)) if available else -1
        support = float(p[label]) if label >= 0 else 0.
        covered = e['features'] is not None and label >= 0
        direct = int(np.argmax(p))
        if not covered:
            label = direct = e['regular']
        row = {'direct': direct, 'routed': label}
        for t in protocol['thresholds']:
            accepted = covered and support >= t
            row['gate_' + str(t)] = label if accepted else e['regular']
            row['accept_' + str(t)] = accepted
        return row
    def replay(model, cols, indices):
        matrix = X[indices][:, cols]
        ps = model.predict_proba(matrix) if cfg['family'] == 'forest' else model.predict_proba(matrix, 'minimum')
        return [decide(p, i) for i, p in zip(indices, ps)]
    retention = []
    for base_train, held in splits:
        held_sources = {examples[i]['source_group'] for i in held}
        train = base_train + [375 + i for i, e in enumerate(extra) if e['case'] in selected_extra and e['source_group'] not in held_sources]
        model, cols = fit(train)
        retention.append(sum(r[winner['arm']] == e['reference'] for r, e in zip(replay(model, cols, list(range(99))), local)))
        for i, row in zip(held, replay(model, cols, held)):
            for arm in arms + ['accept_' + str(t) for t in protocol['thresholds']]:
                assert row[arm] == records[examples[i]['case']][arm]
    full_train = list(range(375)) + [375 + i for i, e in enumerate(extra) if e['case'] in selected_extra]
    model, cols = fit(full_train)
    originals = replay(model, cols, list(range(99)))
    full_correct = sum(r[winner['arm']] == e['reference'] for r, e in zip(originals, local))
    assert min(retention + [full_correct]) == 99
    index = {e['case']: i for i, e in enumerate(local)}
    slot_correct = slots = broader_replays = 0
    for bank in (1, 2, 3):
        local_cases = {r['case'] for r in old_inputs(PREVIOUS, bank)[3]['local']}
        assert len(local_cases) == 48
        for e in old_examples(bank):
            i = index[e['case']]
            assert all(e[k] == local[i][k] for k in ('program', 'features', 'reference', 'regular'))
            assert originals[i][winner['arm']] == e['reference']
            broader_replays += 1
            if e['case'] in local_cases:
                slot_correct += originals[i][winner['arm']] == e['reference']
                slots += 1
    assert slot_correct == slots == 144
    result = {'passed': True, 'candidate': winner['candidate'], 'arm': winner['arm'], 'metrics': winner['metrics'],
              'primary_cases': 276, 'primary_sources': 84, 'pool_cases': 915, 'source_folds': 5,
              'original_correct_across_folds': retention, 'full_original_correct': full_correct,
              'original_training_slots_correct': slot_correct, 'original_training_slots': slots,
              'local_and_outside_training_route_replays': broader_replays,
              'request_refits_in_audit': 0, 'new_model_calls': 0, 'reserved_sources_used': 0,
              'strictly_over_85_requires': 235, 'development_target_exceeded': winner['metrics']['correct'] >= 235,
              'target_verified': False, 'fresh_validation_performed': False,
              'scope': 'Independent source-held development replay; no serving change or fresh validation claim.'}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', result)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'selection_sha256': fingerprint(STUDY / 'selection.json'),
              'study_manifest_sha256': fingerprint(STUDY / 'manifest.json')})
    (out / 'run.log').write_text('Recounted all eight configurations, rebuilt every fold and half-selection, refitted winning policy and replayed 144 original slots.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
