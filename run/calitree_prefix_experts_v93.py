"""Audit complementary early-stage predictions of the frozen boosted teacher.

All stages share the same trees and input vocabulary. They are correlated
model views, not independent visual evidence. Oracle counts describe available
headroom, not an executable selector or an achieved accuracy.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np
from catboost import CatBoostClassifier

from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_rubric_v70 import data, ROOT, STUDY, read, fingerprint
from run.calitree_seeded_rubric_v73 import arrays
from run.calitree_source_excluded_calibration_v89 import baseline_predictions, EXPERT
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_accuracy_headroom_v37 import accuracy

PREFIXES = (200, 400, 800)


def run(out):
    if out.exists():
        raise ValueError('Fresh experiment directory required')
    examples, feature_names, X = data(); same, names, raw, semantic = arrays(); assert examples == same
    y = np.asarray([e['reference'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); sol, _ = cached(examples)
    pos = {e['case']: i for i, e in enumerate(examples)}
    prior = {r['case']: r for r in read(EXPERT/'predictions.json')}
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in semantic], dtype=bool)
    protocol = {'version': 'shared-prefix-expert-headroom-v93', 'prefixes': list(PREFIXES),
                'hypothesis': 'Earlier stages may express a complementary, less specialized decision using shared trees. Test whether meaningful selection headroom exists before fitting another gate.',
                'scope': 'Same276 reviewed development cases and five source-held folds; all siblings excluded. Fold5 is the existing all-data fitting model only.',
                'views': 'Native predict_proba at200/400/800 of1200 trees. Correlated model views, not independent judges or new image evidence.',
                'priority': 'Existing v72/v87 rules retain their old full-teacher context and priority. Missing evidence retains regular fallback.',
                'warrants': 'Also measure a family that only changes a grade when its same-requirement affirmative v73 warrant holds.',
                'oracle': 'Reference labels may describe whether any allowed proposal is correct; never use that answer as a policy or fit selector on held labels.',
                'new_api_calls': 0, 'new_encoder_calls': 0, 'new_model_fits': 0, 'new_pilot_responses_used': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Shared early-stage teacher view audit started.\n')
    (out/'llm-histories.log').write_text('Zero calls, uploads, extraction or model fits; old generic expert cache only. No v75 pilot response reads.\n')
    files = [Path(__file__), ROOT/'run/calitree_source_excluded_calibration_v89.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    source_hashes = {}; records = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        meta = read(TEACHERS/folder/'teacher.json')['contract']; cols = [feature_names.index(n) for n in meta['columns']]
        assert meta['rows'] == train and digest(X[train][:, cols].tolist()) == meta['matrix_ref'] and digest(y[train].tolist()) == meta['targets_ref']
        model = CatBoostClassifier(); model.load_model(str(TEACHERS/folder/'teacher.cbm'))
        assert model.tree_count_ == 1200
        full = model.predict_proba(X[:, cols], thread_count=2)
        assert np.allclose(full, read(TEACHERS/folder/'predictions.json')['support'], atol=1e-12, rtol=0)
        current, locked = baseline_predictions(folder, names, raw, semantic, full, regular, sol, valid)
        assert np.all(current[:99] == y[:99]) and all(current[i] == prior[examples[i]['case']]['prediction'] for i in held)
        stored = {'full_support': full.tolist(), 'baseline': current.tolist(), 'locked': locked.tolist(), 'stages': {}}
        stage_predictions = {}
        for prefix in PREFIXES:
            support = model.predict_proba(X[:, cols], ntree_end=prefix, thread_count=2)
            plain = np.argmax(support, axis=1); plain[locked] = current[locked]; plain[~valid] = regular[~valid]
            warranted = plain.copy(); veto = ~warrants[np.arange(len(plain)), plain]; warranted[veto] = current[veto]
            stored['stages'][str(prefix)] = {'support': support.tolist(), 'prediction': plain.tolist(), 'warranted': warranted.tolist()}
            stage_predictions[prefix] = (plain, warranted)
            retention.append({'fold': f['fold'], 'prefix': prefix, 'plain_original_correct': int(np.sum(plain[:99] == y[:99])), 'warranted_original_correct': int(np.sum(warranted[:99] == y[:99]))})
        for i in held:
            records.append({**examples[i], 'fold': f['fold'], 'baseline': int(current[i]), 'prior_rule_priority': bool(locked[i]),
                            'stages': {str(p): {'prediction': int(stage_predictions[p][0][i]), 'warranted': int(stage_predictions[p][1][i])} for p in PREFIXES}})
        save_json(out/folder/'views.json', stored)
        save_json(out/folder/'membership.json', {'train_cases': f['train_cases'], 'held_cases': f['held_cases'], 'teacher_ref': digest(meta), 'columns': meta['columns']})
        for file in ('teacher.cbm', 'teacher.json', 'predictions.json'):
            path = TEACHERS/folder/file; source_hashes[str(path)] = fingerprint(path)
        print({'fold': f['fold'], 'held': len(held)}, flush=True)
    results = {'baseline': accuracy(records, 'baseline'), 'coverage': sum(r['covered'] for r in records), 'stages': {}}
    for prefix in PREFIXES:
        for arm in ('prediction', 'warranted'):
            rows = [{**r, 'proposed': r['stages'][str(prefix)][arm]} for r in records]
            results['stages'][str(prefix)+'_'+arm] = {'accuracy': accuracy(rows, 'proposed'),
                    'gains': sum(r['proposed'] == r['reference'] != r['baseline'] for r in rows),
                    'losses': sum(r['baseline'] == r['reference'] != r['proposed'] for r in rows)}
    results['headroom'] = {arm: {'oracle_max_correct': sum(r['baseline'] == r['reference'] or any(r['stages'][str(p)][arm] == r['reference'] for p in PREFIXES) for r in records),
                               'not_an_achieved_policy': True} for arm in ('prediction', 'warranted')}
    assert results['baseline']['correct'] == 225 and results['coverage'] == 273
    save_json(out/'results.json', results); save_json(out/'predictions.json', records); save_json(out/'retention.json', retention)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': {str(p): fingerprint(p) for p in files}, 'source_hashes': source_hashes,
                                  'matrix_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()), 'folds_sha256': fingerprint(STUDY/'folds.json')})
    (out/'run.log').write_text('Completed native prefix-view headroom audit. Oracle counts are descriptive only; no policy, fitting or serving change.\n')
    print(results, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
