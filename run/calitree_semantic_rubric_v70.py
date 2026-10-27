"""Reconstruct semantic rubrics and calibrate corrections to the v69 teacher."""
import argparse
from dataclasses import replace
from pathlib import Path
import time

import numpy as np
from catboost import CatBoostClassifier
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.calibration import visual_semantic_policy_v69 as policy
from critical.core.calibration.semantic_rubric_v70 import Config, SemanticRubric, VERSION
from critical.core.decision.artifacts import digest, save_json
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

FROZEN = ROOT / 'logs/exps/261021-frozen-visual-policy-v69'
STUDY = ROOT / 'logs/exps/261021-visual-policy-v64'
VISION = ROOT / 'logs/exps/261021-paired-vision-v63'


def data():
    raw = read(FROZEN / 'replay_inputs_without_references.json')
    references = {r['case']: r for r in read(FROZEN / 'fitting_replay.json')}
    inputs = {r['case']: r for r in read(VISION / 'inputs_without_labels.json')}
    names = sorted(policy.evidence.FEATURES) + ['evidence_missing']
    names += ['judge_predicts_' + n for n in ('unresolved', *policy.LABELS)]
    names += list(policy.language.SPECS) + list(policy.vision.SPECS)
    examples, rows = [], []
    for r in raw:
        pair = r['observation']['image_pair_ref'] if r['observation'] else None
        record = policy.shared.evidence.project(r['program'], r['observation'], pair, r['interpretation'])
        values = policy.evidence.feature_values(r['program'], record)
        regular = policy.regular_label(r['judgment'])
        flags = {**(values or dict.fromkeys(policy.evidence.FEATURES, False)), 'evidence_missing': values is None,
                 **{'judge_predicts_' + n: regular == k for k, n in zip((-1, 0, 1, 2), ('unresolved', *policy.LABELS))},
                 **policy.language.project(r['program'], r['judgment']), **r['expected_visual_flags']}
        rows.append([int(flags[n]) for n in names])
        examples.append({'case': r['case'], 'source_group': inputs[r['case']]['source_group'],
                         'reference': references[r['case']]['reference'], 'regular': regular,
                         'covered': references[r['case']]['covered']})
        assert (values is not None) == examples[-1]['covered']
    matrix = np.asarray(rows, dtype=np.float32)
    selected = feature_columns(names, matrix, list(range(915)), 'dedup_noexpert')
    assert [names[c] for c in selected] == read(FROZEN / 'policy.json')['feature_names']
    return examples, names, matrix


def teacher(names, X, y, train, directory, *, stored=None):
    """Fit or restore an immutable, split-bound teacher cache."""
    cols = ([names.index(n) for n in stored['selected_features']] if stored is not None
            else feature_columns(names, X, train, 'dedup_noexpert'))
    contract = {'rows': train, 'columns': [names[c] for c in cols], 'matrix_ref': digest(X[train][:, cols].tolist()),
                'targets_ref': digest(y[train].tolist()), 'depth': 8, 'iterations': 1200, 'seed': 20261021}
    directory.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    model = CatBoostClassifier()
    if (directory / 'teacher.cbm').exists():
        assert read(directory / 'teacher.json')['contract'] == contract
        model.load_model(str(directory / 'teacher.cbm'))
    else:
        for weight in (1., 5., 25.):
            model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=1200, learning_rate=.05,
                      l2_leaf_reg=3., random_seed=20261021, thread_count=2, verbose=False,
                      allow_writing_files=False, bootstrap_type='No', random_strength=0.)
            model.fit(X[train][:, cols], y[train], sample_weight=np.where(np.asarray(train) < 99, weight, 1.))
            originals = [i for i in train if i < 99]
            if not originals or np.all(model.predict(X[originals][:, cols]).reshape(-1) == y[originals]):
                break
        model.save_model(str(directory / 'teacher.cbm'))
        save_json(directory / 'teacher.json', {'contract': contract, 'original_weight': weight,
                                              'elapsed_seconds': time.monotonic() - start})
    support = model.predict_proba(X[:, cols])
    priority = dict(zip((names[c] for c in cols), model.get_feature_importance().tolist()))
    save_json(directory / 'predictions.json', {'support': support.tolist(), 'priority': priority})
    return support, priority


def run(out, correction=False):
    examples, names, X = data()
    y = np.asarray([e['reference'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples])
    valid = np.asarray([e['covered'] for e in examples])
    positions = {e['case']: i for i, e in enumerate(examples)}
    folds = [f for f in read(STUDY / 'folds.json') if f['candidate'] == 'boost_full_vision']
    baseline = {r['case']: r for r in read(STUDY / 'predictions.json') if r['candidate'] == 'boost_full_vision'}
    configs = [Config(family=family) for family in ('semantic', 'grounded', 'auxiliary')]
    configs += [replace(c, mode='reconstruct', minimum_precision=.98) for c in configs]
    if correction:
        configs += [Config(family=f, mode='correct', min_sources=2, minimum_precision=.67) for f in ('semantic', 'grounded', 'auxiliary')]
    labels = [c.family + '_' + c.mode + '_' + str(c.minimum_precision) for c in configs]
    protocol = {'version': VERSION, 'configs': [vars(c) for c in configs], 'primary_cases': 276,
                'folds': 'The fixed five v64 source folds; all held-source siblings excluded.',
                'reconstruction': 'Teacher feature priorities and fitting predictions guide bounded semantic clauses. Every clause has a positive semantic anchor and distinct-source support.',
                'correction': 'If enabled, source-excluded inner teacher predictions train correction rules. Outer held sources never enter those teachers or rules.',
                'local_protection': 'Every rule is vetoed if it changes any of the 99 correct actual teacher predictions. Unmatched cases retain teacher; missing evidence retains regular.',
                'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    if (out / 'protocol.json').exists():
        assert read(out / 'protocol.json') == protocol
    else:
        out.mkdir(parents=True, exist_ok=True)
        save_json(out / 'protocol.json', protocol)
    (out / 'llm-histories.log').write_text('Zero model API calls. Rubrics execute over cached label-blind LLM evidence; prose-only LLM execution is not claimed.\n')
    records, checks = [], []
    for f in folds:
        train, held = [positions[c] for c in f['train_cases']], [positions[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        folder = out / ('fold' + str(f['fold']))
        support, priority = teacher(names, X, y, train, folder, stored=f)
        proposed = np.argmax(support, axis=1)
        proposed[~valid] = regular[~valid]
        assert np.all(proposed[:99] == y[:99])
        for i in held:
            assert proposed[i] == baseline[examples[i]['case']]['direct']
        fit = [i for i in train if valid[i]]
        oof = proposed.copy()
        inner_trace = []
        if correction:
            originals = set(groups[:99])
            pool = [i for i in train if groups[i] not in originals]
            splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261023)
            for inner, (_, test) in enumerate(splitter.split(np.zeros(len(pool)), y[pool], groups[pool])):
                excluded = {groups[pool[int(i)]] for i in test}
                inner_train = [i for i in train if groups[i] not in excluded]
                inner_held = [i for i in train if groups[i] in excluded]
                ps, _ = teacher(names, X, y, inner_train, folder / ('inner' + str(inner)))
                oof[inner_held] = np.argmax(ps[inner_held], axis=1)
                oof[~valid] = regular[~valid]
                assert not set(groups[inner_train]) & (excluded | set(groups[held]))
                inner_trace.append({'train_sources': sorted(set(groups[inner_train])), 'held_sources': sorted(excluded),
                                    'held_cases': [examples[i]['case'] for i in inner_held]})
            save_json(folder / 'inner_folds.json', inner_trace)
        save_json(folder / 'memberships.json', {'train_cases': f['train_cases'], 'held_cases': f['held_cases'],
                  'inner_trace': inner_trace, 'oof_predictions': oof[train].tolist()})
        for name, config in zip(labels, configs):
            rubric = SemanticRubric(names, config)
            targets = proposed[fit] if config.mode == 'reconstruct' else y[fit]
            rubric.fit(X[fit], targets, groups=groups[fit].tolist(), priority=priority,
                       base_predictions=oof[fit] if config.mode == 'correct' else None,
                       protected_X=X[:99], protected_y=y[:99], protected_base=proposed[:99])
            local = rubric.predict(X[:99], base_predictions=proposed[:99])
            assert local == y[:99].tolist()
            output = np.asarray(rubric.predict(X, base_predictions=proposed))
            output[~valid] = regular[~valid]
            artifact = rubric.artifact(digest(read(folder / 'teacher.json')))
            save_json(folder / (name + '.json'), artifact)
            (folder / (name + '.txt')).write_text(rubric.render())
            for i in held:
                records.append({**examples[i], 'teacher': int(proposed[i]), 'prediction': int(output[i]),
                                'candidate': name, 'fold': f['fold']})
            checks.append({'fold': f['fold'], 'candidate': name, 'original_correct': int(sum(a == b for a, b in zip(local, y[:99]))),
                           'rules': len(rubric.rules), 'literals': sum(len(r['conditions']) for r in rubric.rules),
                           'training_teacher_agreement': int(np.sum(output[fit] == proposed[fit])), 'training_rows': len(fit)})
        save_json(out / 'predictions.json', records)
        save_json(out / 'retention.json', checks)
        print({'fold': f['fold'], 'held': len(held), 'rules': {c['candidate']: c['rules'] for c in checks if c['fold'] == f['fold']}}, flush=True)
    results = {}
    for name in labels:
        rows = [r for r in records if r['candidate'] == name]
        results[name] = {'accuracy': accuracy(rows, 'prediction'), 'teacher': accuracy(rows, 'teacher'),
                         'gains': sum(r['prediction'] == r['reference'] != r['teacher'] for r in rows),
                         'losses': sum(r['teacher'] == r['reference'] != r['prediction'] for r in rows),
                         'changed': sum(r['teacher'] != r['prediction'] for r in rows),
                         'coverage': sum(r['covered'] for r in rows),
                         'original_retained_in_all_fits': all(c['original_correct'] == 99 for c in checks if c['candidate'] == name)}
    save_json(out / 'results.json', results)
    save_json(out / 'manifest.json', {'source_sha256': {str(p): fingerprint(p) for p in
              (FROZEN / 'replay_inputs_without_references.json', FROZEN / 'fitting_replay.json', VISION / 'inputs_without_labels.json',
               STUDY / 'folds.json', STUDY / 'predictions.json')}, 'features_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()),
               'code_sha256': {str(p): fingerprint(p) for p in (Path(__file__), ROOT / 'critical/core/calibration/semantic_rubric_v70.py')}})
    (out / 'run.log').write_text('Source-held teacher control reproduced222/276. Bounded semantic rubrics, protected original predictions, unchanged missing-evidence fallback. No reserved data or API calls.\n')
    print(results, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--correction', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.correction)
