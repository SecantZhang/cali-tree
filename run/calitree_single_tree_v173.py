"""Replace the entire boosted stack with one tree, using cached evidence only."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.single_tree_v173 import SingleTree, execute, ANCHOR_WEIGHTS
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.calibration.semantic_rubric_v70 import DESCRIPTIONS
from critical.core.calibration import visual_semantic_policy_v69 as visual
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, data, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

BUDGETS = (8, 16, 32, 64, 128)
CONFIGS = [(view, target, balanced, leaves) for view in ('semantic', 'full')
           for target in ('human', 'v112', 'v144') for balanced in (False, True) for leaves in BUDGETS]
PRIMARY = ('full', 'human', True, 32)
V112 = ROOT/'logs/exps/261023-semantic-residual-v103-r1'
V144 = ROOT/'logs/exps/261025-balanced-patches-v144-r1'
PATCH = 'all_grades_loss1.0_guards2'
SELECTION = ROOT/'critical/core/calibration/artifacts/calitree_current.json'


def name_of(config):
    view, target, balanced, leaves = config
    return f'{view}_{target}_{"balanced" if balanced else "uniform"}_leaves{leaves}'


def inputs():
    examples, names, X = data()
    y = np.asarray([e['reference'] for e in examples])
    valid = np.asarray([e['covered'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples])
    pos = {e['case']: i for i, e in enumerate(examples)}
    folds = [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']
    descriptions = {**DESCRIPTIONS, 'evidence_missing': 'Bound semantic evidence is unavailable.',
                    **{'judge_predicts_'+n: 'The regular judge proposes '+n+'.' for n in ('unresolved', *visual.LABELS)}}
    return examples, names, X, y, valid, regular, groups, pos, folds, descriptions


def fold_inputs(f, names, y, valid, groups, pos):
    train = np.asarray([pos[c] for c in f['train_cases'] if valid[pos[c]]])
    held = np.asarray([pos[c] for c in f['held_cases']], dtype=int)
    assert not set(groups[train]) & set(groups[held])
    assert set(range(99)) <= set(train)
    folder = 'fold'+str(f['fold'])
    targets = {'human': y,
               'v112': np.asarray(read(V112/folder/'contextual_depth2_guarded-predictions.json')),
               'v144': np.asarray(read(V144/folder/(PATCH+'-predictions.json')))}
    assert all(np.array_equal(t[:99], y[:99]) for t in targets.values())
    columns = {view: [names.index(n) for n in f['selected_features']
                     if view == 'full' or n in visual.evidence.FEATURES] for view in ('semantic', 'full')}
    return train, held, folder, targets, columns


def run(out):
    if out.exists():
        raise ValueError('Fresh standalone-tree study required')
    selection_before = file_hash(SELECTION)
    protocol = {'version': 'single-tree-comparison-v173', 'configs': CONFIGS, 'primary': name_of(PRIMARY),
        'objective': 'Test whether one standalone Boolean CART tree matches V112/V144. Exploratory reviewed source-held development; no untouched-final claim.',
        'capacity': 'One log-loss CART, leaf budgets8/16/32/64/128, no depth limit, min leaf1, seed20261026. Report actual depth and singleton source leaves.',
        'features': 'Exact fold-specific primitive feature pool used by the visual booster; semantic arm restricts it to instruction-bound semantic/physical evidence. No teacher scores, local-review fields, IDs or example lookups at inference.',
        'targets': 'Human labels or distillation of the existing outer-fit V112/V144 labels on fitting rows only. Outer-held sources and every sibling are excluded from student and teacher fitting.',
        'weighting': 'Uniform or equal class mass after anchor multiplication; first anchor1/5/25/125/625 retaining99 originals wins. If none does, report the arm as locally ineligible, never repair it with a lookup or hidden ensemble.',
        'coverage': 'Same bound-evidence validity mask and exact regular fallback,273/276. All276 evaluation cases remain counted.',
        'selection': 'No held labels select anchors, features or pruning. Report every configuration; aggregate best is retrospective. Default V112 unchanged.',
        'new_api_calls': 0, 'new_observer_or_encoder_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
        'anchor_weights': ANCHOR_WEIGHTS}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Standalone tree comparison started. Cached primitive features only.\n')
    (out/'llm-histories.log').write_text('Zero API, local-observer, encoder or reserved-source calls.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/single_tree_v173.py',
               ROOT/'run/calitree_semantic_rubric_v70.py', ROOT/'critical/core/calibration/class_balance_v141.py']
    hashes = {str(p): file_hash(p) for p in sources}
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    examples, names, X, y, valid, regular, groups, pos, folds, descriptions = inputs()
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows, retention, baselines, memberships = [], [], [], []
    scalar_rows, fit_attempts = 0, 0
    for f in folds:
        train, held, folder, targets, columns = fold_inputs(f, names, y, valid, groups, pos)
        memberships.append({'fold': f['fold'], 'fit_cases': [examples[i]['case'] for i in train],
            'fit_sources': sorted(set(groups[train])), 'held_cases': f['held_cases'],
            'fit_class_counts': np.bincount(y[train], minlength=3).tolist(),
            'features': {v: [names[c] for c in cc] for v, cc in columns.items()}})
        for i in held:
            baselines.append({**examples[i], 'fold': f['fold'], 'v112': int(targets['v112'][i]), 'v144': int(targets['v144'][i])})
        for config in CONFIGS:
            view, target, balanced, leaves = config; cc = columns[view]; nn = [names[c] for c in cc]
            model = SingleTree(nn, leaves=leaves, balanced=balanced).fit(X[train][:, cc], targets[target][train],
                original=train < 99, groups=groups[train], protected_X=X[:99, cc], protected_y=y[:99])
            prediction = np.asarray(model.predict(X[:, cc])); prediction[~valid] = regular[~valid]
            artifact = model.artifact(descriptions); name = name_of(config)
            for i in range(len(examples)):
                values = {n: bool(X[i, j]) for n, j in zip(nn, cc)}
                expected = execute(artifact, values) if valid[i] else int(regular[i])
                assert expected == prediction[i]
            scalar_rows += len(examples); fit_attempts += len(model.attempts)
            correct = int(np.sum(prediction[:99] == y[:99])); slot_correct = sum(prediction[pos[r['case']]] == r['reference'] for r in slots)
            assert model.retained == (correct == 99)
            leaves_support = []
            def collect(node):
                if 'feature' not in node: leaves_support.append(node['fitting_sources'])
                else: collect(node['if_false']); collect(node['if_true'])
            collect(artifact['tree'])
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': correct,
                'local_slots_correct': int(slot_correct), 'eligible': model.retained, **model.metadata(),
                'used_features': len(artifact['feature_names']), 'single_source_leaves': sum(n == 1 for n in leaves_support),
                'min_leaf_sources': min(leaves_support), 'feature_count': len(nn)})
            save_json(out/folder/(name+'.json'), artifact)
            save_json(out/folder/(name+'-predictions.json'), prediction.tolist())
            (out/folder/(name+'.txt')).write_text(artifact['rubric'])
            for i in held:
                rows.append({**examples[i], 'candidate': name, 'fold': f['fold'], 'prediction': int(prediction[i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention); save_json(out/'memberships.json', memberships)
        print({'fold': f['fold'], 'configs': len(CONFIGS), 'fit_rows': len(train), 'fit_attempts_so_far': fit_attempts}, flush=True)
    assert len(baselines) == 276
    baseline_metrics = {n: classification_metrics(baselines, n) for n in ('regular', 'v112', 'v144')}
    assert baseline_metrics['v112']['correct'] == 227 and baseline_metrics['v144']['correct'] == 226
    results = {}
    for config in CONFIGS:
        name = name_of(config); rr = [r for r in rows if r['candidate'] == name]; ret = [r for r in retention if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276 and len(ret) == 6
        results[name] = {'metrics': classification_metrics(rr), 'eligible': all(r['eligible'] for r in ret),
            'min_original_correct': min(r['original_correct'] for r in ret), 'min_slots_correct': min(r['local_slots_correct'] for r in ret),
            'max_leaves': max(r['leaves'] for r in ret), 'max_depth': max(r['depth'] for r in ret),
            'full_fit': next(r for r in ret if r['fold'] == 5), 'coverage': sum(r['covered'] for r in rr),
            'fold_metrics': {str(k): classification_metrics([r for r in rr if r['fold'] == k]) for k in range(5)}}
        assert results[name]['coverage'] == 273
    save_json(out/'baselines.json', baseline_metrics); save_json(out/'baseline_predictions.json', baselines); save_json(out/'results.json', results)
    assert all(file_hash(path) == sha for path, sha in hashes.items()) and file_hash(SELECTION) == selection_before
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': hashes,
        'matrix_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()), 'folds_sha256': file_hash(STUDY/'folds.json'),
        'selection_sha256': selection_before, 'scalar_replays': scalar_rows, 'fit_attempts': fit_attempts,
        'models': len(retention), 'sklearn_version': __import__('sklearn').__version__})
    (out/'run.log').write_text(f'Completed {len(retention)} standalone models/{fit_attempts} fits/{scalar_rows} scalar/native rows. Default unchanged.\n')
    eligible = [(n, r) for n, r in results.items() if r['eligible']]
    for criterion in ('accuracy', 'balanced_accuracy'):
        ranked = sorted(eligible, key=lambda item: (-item[1]['metrics'][criterion], item[1]['max_leaves'], item[0]))
        print(criterion, [(n, r['metrics']['correct'], r['metrics']['balanced_accuracy'], r['max_leaves']) for n, r in ranked[:5]], flush=True)
    print({'eligible_configurations': len(eligible), 'total': len(CONFIGS)}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output-dir', type=Path, required=True)
    run(parser.parse_args().output_dir.resolve())
