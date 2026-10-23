"""Compare fixed policies as matched-editor fitting coverage increases.

The 276 scored cases and their five source-group folds never change. New
siblings of a scored source are removed together, even when they are not scored.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores, RESERVED
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'matched-editor-policy-v58'
COLLECTION = ROOT / 'logs/exps/261021-sibling-training-v57'
THRESHOLDS = (0., .5, .65, .8, .9)
CONFIGS = [dict(family=family, coverage=coverage, original_weight=1.)
           for family in ('forest', 'boundary') for coverage in ('zero', 'half', 'full')]
CONFIGS += [dict(family=family, coverage='full', original_weight=5.) for family in ('forest', 'boundary')]
ARMS = ('direct', 'routed') + tuple('gate_' + str(t) for t in THRESHOLDS)


def half_cases(additions):
    """Choose exactly two of four editor outputs per task, without labels."""
    by_task = defaultdict(list)
    for e in additions:
        by_task[e['task_uid']].append(e)
    selected = set()
    for uid, rows in by_task.items():
        if len(rows) != 4 or len({e['editor'] for e in rows}) != 4:
            raise ValueError('Expected four distinct missing editors per task')
        ordered = sorted(rows, key=lambda e: digest(['v58-half', uid, e['editor']]))
        selected.update(e['case'] for e in ordered[:2])
    return selected


def fixed_splits(local, recent, additions, coverage):
    if coverage not in ('zero', 'half', 'full'):
        raise ValueError('Unknown matched coverage')
    n, end = len(local), len(local) + len(recent)
    assert not {e['source_group'] for e in local} & {e['source_group'] for e in recent}
    chosen = half_cases(additions) if coverage == 'half' else {e['case'] for e in additions} if coverage == 'full' else set()
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    for tr, te in splitter.split(np.zeros(len(recent)), [e['reference'] for e in recent], [e['source_group'] for e in recent]):
        held = [n + int(i) for i in te]
        sources = {recent[int(i)]['source_group'] for i in te}
        extra = [end + i for i, e in enumerate(additions) if e['case'] in chosen and e['source_group'] not in sources]
        train = list(range(n)) + [n + int(i) for i in tr] + extra
        examples = local + recent + additions
        assert not sources & {examples[i]['source_group'] for i in train}
        assert set(range(n)) <= set(train)
        yield train, held


def model_for(config):
    return (Probe('forest', 'sqrt').model if config['family'] == 'forest'
            else BoundaryExperts(balanced=True, max_features='sqrt'))


def probabilities(model, matrix, family):
    return model.predict_proba(matrix) if family == 'forest' else model.predict_proba(matrix, 'minimum')


def decisions(probability, e, available):
    available = sorted({int(p) for p in available if p >= 0})
    direct = int(np.argmax(probability))
    routed = max(available, key=lambda c: (float(probability[c]), -c)) if available else -1
    confidence = float(probability[routed]) if routed >= 0 else 0.
    covered = e['features'] is not None and routed >= 0
    if not covered:
        direct = routed = e['regular']
    row = dict(direct=direct, routed=routed, confidence=confidence)
    for threshold in THRESHOLDS:
        accepted = covered and confidence >= threshold
        row['gate_' + str(threshold)] = routed if accepted else e['regular']
        row['accept_' + str(threshold)] = bool(accepted)
    return row


def protocol():
    return {'version': VERSION, 'configs': CONFIGS, 'thresholds': THRESHOLDS,
            'scored_cases': 276, 'scored_sources': 84, 'protected_cases': 99, 'protected_slots': 144,
            'folds': 'Same five StratifiedGroupKFold(20261020) folds built on the ORIGINAL 276 primary cases only.',
            'sibling_exclusion': 'Every additional output of a held decoded-pixel source is excluded, including unscored outputs.',
            'half_selection': 'For each task choose two of four outputs by digest(v58-half, task_uid, editor), independent of labels or predictions.',
            'features': 'Existing train-only deduplicated portable/task/regular Boolean vocabulary; no expert inputs, IDs, editors, objects, raw strings or image fingerprints.',
            'models': 'Existing 128-tree forest and balanced three-boundary/minimum expert policy, seed 20261020, no bootstrap, minimum leaf one.',
            'routing': 'Highest support among available regular/old expert labels; lower label wins exact ties. Direct arm may propose any label.',
            'coverage': 'Recompute each declared support threshold after fitting; reject missing evidence or unavailable labels and use unchanged regular fallback. Support is not calibrated confidence.',
            'eligibility': 'Actual deployed labels, including fallbacks, retain 99/99 originals in every fold and full fit; no case-specific override.',
            'selection': 'Eligible accuracy, then macro-F1, then routed over direct, then fewer added cases, then smaller original weight, then lexical candidate/arm.',
            'target': 'Strictly >85% overall requires 235/276; development only, no final generalization proof.',
            'new_model_calls': 0, 'reserved_sources_used': 0, 'fresh_v51_observations_used': False, 'serving_change': False}


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    save_json(out / 'protocol.json', protocol())
    hashes = {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'critical/core/calibration/boundary_experts_v55.py',
               ROOT / 'run/calitree_accuracy_headroom_v37.py', ROOT / 'run/calitree_simplified_policy_v44.py',
               ROOT / 'run/calitree_continuous_policy_v43.py')}
    save_json(out / 'preparation.json', {'code_hashes': hashes,
              'collection_manifest_sha256': fingerprint(COLLECTION / 'manifest.json'),
              'prepared_before_collection_completed': not (COLLECTION / 'results.json').exists()})
    (out / 'run.log').write_text('Prepared eight fixed coverage/model/weight comparisons before collection completion; no fitting yet.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')


def run(out):
    assert read(out / 'protocol.json') == {**protocol(), 'thresholds': list(THRESHOLDS)}
    for p, expected in read(out / 'preparation.json')['code_hashes'].items():
        assert fingerprint(p) == expected, p
    assert not (out / 'results.json').exists()
    assert fingerprint(COLLECTION / 'manifest.json') == read(out / 'preparation.json')['collection_manifest_sha256']
    local, recent, experts, _ = examples_and_scores(True)
    additions = [{**e, 'cohort': 'matched540'} for e in read(COLLECTION / 'training_data.json')]
    assert len(local) == 99 and len(recent) == 276 and len(additions) == 540
    examples = local + recent + additions
    reserved = {e['source_group'] for e in read(RESERVED / 'inputs_without_labels.json')}
    assert not reserved & {e['source_group'] for e in examples}
    assert len({e['case'] for e in examples}) == 915
    names, X, actions = encoded(examples, experts)
    y = np.asarray([e['reference'] for e in examples])
    weights = np.ones(len(examples))
    results, predictions, folds = {}, [], []
    for config in CONFIGS:
        name = config['family'] + '_' + config['coverage'] + '_w' + str(config['original_weight'])
        weights[:len(local)] = config['original_weight']
        records, local_rows = [], []
        for fold, (train, held) in enumerate(fixed_splits(local, recent, additions, config['coverage'])):
            cols = feature_columns(names, X, train, 'dedup_noexpert')
            matrix = X[:, cols]
            model = model_for(config).fit(matrix[train], y[train], sample_weight=weights[train])
            assert list(model.classes_) == [0, 1, 2]
            originals = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(probabilities(model, matrix[:99], config['family']), local))]
            local_rows.append({arm: sum(r[arm] == e['reference'] for r, e in zip(originals, local)) for arm in ARMS})
            for i, p in zip(held, probabilities(model, matrix[held], config['family'])):
                e = examples[i]
                records.append({k: e[k] for k in ('case', 'source_group', 'cohort', 'reference', 'regular')} |
                               decisions(p, e, actions[i]) | {'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'train_cases': [examples[i]['case'] for i in train],
                          'held_cases': [examples[i]['case'] for i in held],
                          'held_sources': sorted({examples[i]['source_group'] for i in held}),
                          'training_sources': sorted({examples[i]['source_group'] for i in train}),
                          'selected_features': [names[i] for i in cols], 'original_correct': local_rows[-1]})
        chosen = half_cases(additions) if config['coverage'] == 'half' else {e['case'] for e in additions} if config['coverage'] == 'full' else set()
        full_indices = list(range(375)) + [375 + i for i, e in enumerate(additions) if e['case'] in chosen]
        cols = feature_columns(names, X, full_indices, 'dedup_noexpert')
        full_model = model_for(config).fit(X[full_indices][:, cols], y[full_indices], sample_weight=weights[full_indices])
        full_original = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(probabilities(full_model, X[:99, cols], config['family']), local))]
        retention = {arm: {'fold_original_correct': [r[arm] for r in local_rows],
                           'full_fit_original_correct': sum(r[arm] == e['reference'] for r, e in zip(full_original, local))} for arm in ARMS}
        for entry in retention.values():
            entry['retains_training'] = min(entry['fold_original_correct'] + [entry['full_fit_original_correct']]) == 99
        entry = {'config': config, 'retention': retention, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in records if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rows, arm) for arm in ('regular',) + ARMS}
            entry['metrics'][cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rows) for t in THRESHOLDS}
        for arm in ARMS:
            entry['metrics']['all'][arm]['class_recall'] = [sum(r[arm] == c == r['reference'] for r in records) / sum(r['reference'] == c for r in records) for c in (0, 1, 2)]
        if config['coverage'] == 'zero':
            path = 'logs/exps/261020-expanded-simplified-v44/predictions.json' if config['family'] == 'forest' else 'logs/exps/261020-boundary-experts-v55/predictions.json'
            old_name, arm = ('dedup_noexpert_sqrt', 'routed') if config['family'] == 'forest' else ('boundary2', 'minimum_routed')
            prior = {r['case']: r[arm] for r in read(ROOT / path) if r['candidate'] == old_name}
            assert all(r['routed'] == prior[r['case']] for r in records), 'Changed zero-coverage control'
        results[name] = entry
        predictions.extend(records)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'routed_correct': entry['metrics']['all']['routed']['correct'],
               'direct_correct': entry['metrics']['all']['direct']['correct'],
               'retention': {arm: r['retains_training'] for arm, r in retention.items()}}, flush=True)
    eligible = [(c, arm, e) for c, e in results.items() for arm in ARMS if e['retention'][arm]['retains_training']]
    def rank(item):
        c, arm, e = item
        metrics, cfg = e['metrics']['all'][arm], e['config']
        return (-metrics['correct'], -metrics['macro_f1'], arm != 'routed',
                {'zero': 0, 'half': 270, 'full': 540}[cfg['coverage']], cfg['original_weight'], c, arm)
    winner, arm, result = sorted(eligible, key=rank)[0]
    summary = {'candidate': winner, 'arm': arm, 'metrics': result['metrics']['all'][arm],
               'original_retention': result['retention'][arm], 'development_target_exceeded': result['metrics']['all'][arm]['correct'] >= 235,
               'fresh_validation_performed': False, 'target_verified': False, 'new_model_calls': 0}
    save_json(out / 'selection.json', summary)
    save_json(out / 'predictions.json', predictions)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol()), 'features_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()),
              'training_data_sha256': fingerprint(COLLECTION / 'training_data.json'), 'features': names,
              'primary_cases': [e['case'] for e in recent], 'protected_cases': [e['case'] for e in local],
              'half_cases': sorted(half_cases(additions)), 'reference_counts': dict(Counter(int(v) for v in y))})
    with (out / 'run.log').open('a') as handle:
        handle.write('Completed eight declared comparisons; held source families excluded; all original-retention and post-fit gate decisions replayed.\n')
    print(summary, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    prepare(args.output_dir.resolve()) if args.prepare else run(args.output_dir.resolve())
