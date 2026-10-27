"""Independently refit all bounded trees and verify their complete topology."""
import argparse
from pathlib import Path
import shutil

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from critical.core.calibration.single_tree_v173 import execute, render, ANCHOR_WEIGHTS
from critical.core.calibration.class_balance_v141 import training_weights, classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_single_tree_v173 import inputs, fold_inputs, CONFIGS, name_of, ROOT, SELECTION, STUDY
from run.calitree_semantic_rubric_v70 import read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS


def verify(study, out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    manifest, protocol = read(study/'manifest.json'), read(study/'protocol.json')
    assert manifest['protocol_ref'] == digest(protocol)
    assert manifest['folds_sha256'] == file_hash(STUDY/'folds.json')
    for path, sha in manifest['code_sha256'].items():
        assert file_hash(path) == sha == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT))
    assert manifest['selection_sha256'] == file_hash(SELECTION)
    examples, names, X, y, valid, regular, groups, pos, folds, descriptions = inputs()
    assert digest(X.tolist()) == manifest['matrix_ref'] and digest(y.tolist()) == manifest['target_ref']
    saved = {(r['candidate'], r['case']): r for r in read(study/'predictions.json')}
    retained = {(r['candidate'], r['fold']): r for r in read(study/'retention.json')}
    memberships = {r['fold']: r for r in read(study/'memberships.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True)
    (out/'run.log').write_text('Independent sklearn refits, full native/exported topology and source-held metrics audit started.\n')
    (out/'llm-histories.log').write_text('Zero API, encoder, observer or reserved-source calls.\n')
    snapshot = out/'source_snapshot'/Path(__file__).relative_to(ROOT); snapshot.parent.mkdir(parents=True); shutil.copyfile(__file__, snapshot)
    rows, baseline, retention, model_count, scalar_count, node_count, attempts_count = [], [], [], 0, 0, 0, 0
    for f in folds:
        train, held, folder, targets, columns = fold_inputs(f, names, y, valid, groups, pos)
        membership = memberships[f['fold']]
        assert membership['fit_cases'] == [examples[i]['case'] for i in train]
        assert membership['fit_sources'] == sorted(set(groups[train]))
        assert membership['held_cases'] == f['held_cases']
        assert not set(groups[train]) & set(groups[held])
        for i in held:
            baseline.append({**examples[i], 'fold': f['fold'], 'v112': int(targets['v112'][i]), 'v144': int(targets['v144'][i])})
        for config in CONFIGS:
            view, target, balanced, budget = config; cc = columns[view]; nn = [names[c] for c in cc]; name = name_of(config)
            assert membership['features'][view] == nn
            artifact = read(study/folder/(name+'.json'))
            assert artifact['standalone'] and artifact['balanced'] == balanced and artifact['leaf_budget'] == budget
            assert artifact['rubric'] == render(artifact) == (study/folder/(name+'.txt')).read_text()
            attempts = []
            for anchor in ANCHOR_WEIGHTS:
                weights = training_weights(targets[target][train], original=train < 99, original_weight=anchor, balanced=balanced)
                native = DecisionTreeClassifier(criterion='log_loss', max_leaf_nodes=budget, min_samples_leaf=1, random_state=20261026)
                native.fit(X[train][:, cc], targets[target][train], sample_weight=weights*len(train))
                correct = int(np.sum(native.predict(X[:99, cc]) == y[:99]))
                attempts.append({'original_weight': anchor, 'protected_correct': correct,
                    'class_weight_mass': [float(weights[targets[target][train] == k].sum()) for k in range(3)]})
                if correct == 99: break
            attempts_count += len(attempts)
            assert artifact['metadata']['attempts'] == attempts
            assert artifact['metadata']['retained'] == (correct == 99)
            tree = native.tree_; assignments = native.apply(X[train][:, cc]); used = set(); source_counts = []
            def walk(i, node):
                nonlocal node_count
                node_count += 1
                if tree.children_left[i] == tree.children_right[i]:
                    assert set(node) == {'grade', 'class_support', 'fitting_rows', 'fitting_sources'}
                    v = tree.value[i][0]
                    assert node['grade'] == int(native.classes_[int(np.argmax(v))])
                    assert np.array_equal(node['class_support'], v/v.sum())
                    assert node['fitting_rows'] == int(np.sum(assignments == i))
                    support = len(set(groups[train][assignments == i])); source_counts.append(support)
                    assert node['fitting_sources'] == support
                else:
                    assert set(node) == {'feature', 'if_false', 'if_true'} and tree.threshold[i] == .5
                    feature = nn[tree.feature[i]]; assert node['feature'] == feature; used.add(feature)
                    walk(tree.children_left[i], node['if_false']); walk(tree.children_right[i], node['if_true'])
            walk(0, artifact['tree'])
            assert artifact['feature_names'] == sorted(used)
            assert artifact['descriptions'] == {n: descriptions[n] for n in sorted(used)}
            assert artifact['metadata']['leaves'] == native.get_n_leaves() <= budget
            assert artifact['metadata']['depth'] == native.get_depth()
            prediction = native.predict(X[:, cc]).astype(int); prediction[~valid] = regular[~valid]
            assert prediction.tolist() == read(study/folder/(name+'-predictions.json'))
            for i in range(len(examples)):
                values = {n: bool(X[i, j]) for n, j in zip(nn, cc)}
                scalar = execute(artifact, values) if valid[i] else int(regular[i])
                assert scalar == prediction[i]
            scalar_count += len(examples); model_count += 1
            slot_correct = int(sum(prediction[pos[r['case']]] == r['reference'] for r in slots))
            old = retained[(name, f['fold'])]
            assert old['original_correct'] == correct and old['local_slots_correct'] == slot_correct
            assert old['eligible'] == (correct == 99) and old['single_source_leaves'] == sum(n == 1 for n in source_counts)
            retention.append(old)
            for i in held:
                row = {**examples[i], 'candidate': name, 'fold': f['fold'], 'prediction': int(prediction[i])}
                assert row == saved[(name, examples[i]['case'])]; rows.append(row)
        print({'fold': f['fold'], 'refitted_models': model_count, 'scalar_replays': scalar_count}, flush=True)
    baseline_metrics = {n: classification_metrics(baseline, n) for n in ('regular', 'v112', 'v144')}
    assert baseline_metrics == read(study/'baselines.json') and baseline == read(study/'baseline_predictions.json')
    results = read(study/'results.json')
    for config in CONFIGS:
        name = name_of(config); rr = [r for r in rows if r['candidate'] == name]; ret = [r for r in retention if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        assert results[name]['metrics'] == classification_metrics(rr)
        assert results[name]['eligible'] == all(r['eligible'] for r in ret)
        assert results[name]['coverage'] == sum(r['covered'] for r in rr) == 273
        for k in range(5): assert results[name]['fold_metrics'][str(k)] == classification_metrics([r for r in rr if r['fold'] == k])
    assert scalar_count == manifest['scalar_replays'] and model_count == manifest['models'] and attempts_count == manifest['fit_attempts']
    assert file_hash(SELECTION) == manifest['selection_sha256']
    eligible = [n for n in results if results[n]['eligible']]
    report = {'passed': True, 'refitted_models': model_count, 'native_fit_attempts': attempts_count,
        'full_domain_topology_nodes': node_count, 'scalar_native_rows': scalar_count, 'evaluation_cases_per_config': 276,
        'configurations': len(CONFIGS), 'eligible_configurations': len(eligible),
        'matches_v112_overall': [n for n in eligible if results[n]['metrics']['correct'] >= 227],
        'matches_v144_balanced': [n for n in eligible if results[n]['metrics']['balanced_accuracy'] >= baseline_metrics['v144']['balanced_accuracy']],
        'coverage': 273, 'new_api_calls': 0, 'new_neural_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    save_json(out/'verification.json', report)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'producer_manifest_sha256': file_hash(study/'manifest.json')})
    (out/'run.log').write_text('Complete: all refits, full native/portable topologies, scalar predictions, source splits and metrics agree.\n')
    print(report, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--study', type=Path, required=True); parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(); verify(args.study.resolve(), args.output_dir.resolve())
