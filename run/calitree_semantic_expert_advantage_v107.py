"""Learn when a warranted semantic/regular expert improves the base decision.

The target is the difference in correctness of two available decisions. No
expert can propose a grade without the existing affirmative/review guard.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, admissible
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

PROPOSAL = {'proposal_no': 'The candidate expert proposes No.', 'proposal_partial': 'The candidate expert proposes Partial.',
            'proposal_yes': 'The candidate expert proposes Yes.', 'proposal_regular': 'This proposal equals the existing independent regular visual judgment.',
            'proposal_local_warrant': 'This proposal has an affirmative single-requirement local-model warrant.'}


def proposals(d, a, i, matrix, teacher, columns):
    flags = {n: bool(matrix[i, d['names'].index(n)]) for n in d['extra_names']}
    rows = []
    for proposed in (0, 1, 2):
        if proposed == teacher or not admissible(flags, teacher, int(d['regular'][i]), proposed):
            continue
        extension = [int(proposed == k) for k in (0, 1, 2)]+[int(proposed == d['regular'][i]), int(flags['local_'+('no', 'partial', 'yes')[proposed]+'_ready'])]
        rows.append((proposed, np.concatenate([matrix[i, columns], extension])))
    return rows


def run(cache, cache_audit, out):
    if out.exists():
        raise ValueError('Fresh expert-advantage output required')
    from catboost import CatBoostRegressor
    d = load(cache, cache_audit); names = d['names']; y = d['y']; examples = d['examples']
    columns = [i for i, n in enumerate(names) if n in SUPPORT or n.startswith(('local_', 'view_', 'meaning_', 'task_', 'intent_', 'requires_', 'rationale_', 'rubric_'))]
    feature_names = [names[i] for i in columns]+list(PROPOSAL)
    protocol = {'version': 'semantic-expert-advantage-v107', 'configs': [(anchors, depth) for anchors in (False, True) for depth in (2, 3, 4)],
        'features': 'Same contextual semantic concepts and teacher supports plus candidate grade, regular-opinion agreement and positive local warrant. No raw vectors or identities.',
        'target': 'For each admissible alternative, 1[alternative matches human grade]-1[teacher matches human grade]. Learn expected gain with128 shallow regression trees, source-equal fitting weights.',
        'fitting': 'Only genuine inner-source-excluded review fitting rows with valid local observations. Optionally include actual original review inputs as labeled anchors. All original groups were already in fitting; no held-source siblings enter.',
        'selection': 'At inference, choose the admissible alternative with largest predicted gain only if strictly positive and larger than every protected original alternative gain. Ties use No/Partial/Yes order. Original veto determines a nonnegative margin, never held labels.',
        'flow': 'Same .8 review region after old v72/v87 priority. Missing/failing observations and all other cases keep the existing decision. Full276 development denominator, all99/144 veto checks and273 coverage.',
        'new_api_calls': 0, 'new_observer_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol); (out/'run.log').write_text('Source-held paired-expert advantage fits started.\n'); (out/'llm-histories.log').write_text('Offline cached evidence only; no API/observer/encoder calls.\n')
    files = [Path(__file__), ROOT/'run/verify_calitree_semantic_residual_v105.py', ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]; records = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a = fold_arrays(d, f); teacher = np.argmax(a['ps'], axis=1); inner_teacher = np.argmax(a['oof'], axis=1)
        fit_rows = []; fit_targets = []; fit_groups = []
        for i in a['fit']:
            for proposed, row in proposals(d, a, i, a['T'], int(inner_teacher[i]), columns):
                fit_rows.append(row); fit_targets.append(int(proposed == y[i])-int(inner_teacher[i] == y[i])); fit_groups.append(d['groups'][i])
        actual_proposals = {i: proposals(d, a, i, a['full'], int(teacher[i]), columns) for i in np.flatnonzero(a['actual'] & d['available'])}
        for anchors, depth in protocol['configs']:
            rows = fit_rows.copy(); targets = fit_targets.copy(); groups = fit_groups.copy()
            if anchors:
                for i in a['protected']:
                    for proposed, row in actual_proposals[i]:
                        rows.append(row); targets.append(int(proposed == y[i])-int(teacher[i] == y[i])); groups.append(d['groups'][i])
            assert not set(groups) & set(d['groups'][a['held']])
            unique, counts = np.unique(groups, return_counts=True); sizes = dict(zip(unique, counts)); weights = np.asarray([1./sizes[g] for g in groups]); weights *= len(weights)/weights.sum()
            model = CatBoostRegressor(loss_function='RMSE', iterations=128, depth=depth, learning_rate=.05, l2_leaf_reg=10., random_seed=20261023,
                verbose=False, thread_count=2, allow_writing_files=False, bootstrap_type='No', random_strength=0., allow_const_label=True)
            model.fit(np.asarray(rows), targets, sample_weight=weights)
            margin = 0.
            for i in a['protected']:
                options = actual_proposals[i]
                if options:
                    margin = max(margin, float(max(model.predict(np.asarray([row for _, row in options])))))
            p = a['current'].copy(); selected = {}
            for i, options in actual_proposals.items():
                if options:
                    scores = model.predict(np.asarray([row for _, row in options])); best = int(np.argmax(scores))
                    if scores[best] > margin:
                        p[i] = options[best][0]; selected[examples[i]['case']] = {'proposed': int(p[i]), 'predicted_gain': float(scores[best])}
            assert np.all(p[:99] == y[:99]) and np.array_equal(p[~(a['actual'] & d['available'])], a['current'][~(a['actual'] & d['available'])])
            slots = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in originals)); assert slots == 144
            candidate = ('anchors' if anchors else 'noanchors')+'_depth'+str(depth); folder = a['folder']
            metadata = {'features': feature_names, 'feature_descriptions': {n: {**DESCRIPTIONS, **SUPPORT, **PROPOSAL}[n] for n in feature_names},
                'margin': margin, 'depth': depth, 'anchors': anchors, 'fit_cases': [examples[i]['case'] for i in a['fit']], 'protected_review_cases': [examples[i]['case'] for i in a['protected']],
                'fitting_proposals': len(rows), 'teacher_support_ref': digest(a['ps'].tolist()), 'observer_identity_ref': digest(d['profile'])}
            save_json(out/folder/(candidate+'.json'), metadata); save_json(out/folder/(candidate+'-predictions.json'), p.tolist()); save_json(out/folder/(candidate+'-selected.json'), selected)
            model.save_model(str(out/folder/(candidate+'.cbm'))); model.save_model(str(out/folder/(candidate+'-native.json')), format='json')
            retention.append({'candidate': candidate, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': slots, 'margin': margin})
            for i in a['held']:
                records.append({**examples[i], 'candidate': candidate, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(a['current'][i]), 'review': bool(a['actual'][i]), 'local_available': bool(a['actual'][i] and d['available'][i])})
        save_json(out/'predictions.json', records); save_json(out/'retention.json', retention); print({'fold': f['fold'], 'fit_proposals': len(fit_rows)}, flush=True)
    results = {}
    for candidate in sorted({r['candidate'] for r in records}):
        rows = [r for r in records if r['candidate'] == candidate]
        results[candidate] = {'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
            'coverage': sum(r['covered'] for r in rows), 'original_cases_retained': 99, 'original_slots_retained': 144, 'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235}
    save_json(out/'results.json', results); save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in files}, 'protocol_ref': digest(protocol), 'targets_ref': digest(y.tolist()), 'cache_audit_manifest_sha256': file_hash(cache_audit/'manifest.json')})
    (out/'run.log').write_text('Completed six paired-expert policies under the unchanged semantic guard; no serving change.\n'); print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--cache-audit', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); run(a.cache.resolve(), a.cache_audit.resolve(), a.output_dir.resolve())
