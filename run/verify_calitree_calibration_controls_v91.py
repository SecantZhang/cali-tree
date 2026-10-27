"""Replay class/semantic score and ordered-objective development controls."""
import argparse
from pathlib import Path

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from critical.core.calibration.source_excluded_calibration_v89 import BoundaryCalibration, source_excluded_views
from critical.core.calibration.ordinal_boost_v62 import ordered_probabilities, mean_support
from critical.core.decision.artifacts import digest, save_json
from run.calitree_source_excluded_calibration_v89 import CONFIGS as CALIBRATIONS, candidate_name as calibration_name, baseline_predictions, EXPERT
from run.calitree_ordered_visual_rubric_v90 import CONFIGS as ORDERED, candidate_name as ordered_name
from run.calitree_seeded_rubric_v73 import arrays, attach
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_semantic_rubric_v70 import data, ROOT, STUDY, read, fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy


def explicit_scores(artifact, values, support):
    """Independent reconstruction from the human-readable saved equation."""
    offset = np.log(np.clip(support, 1e-9, 1.))
    correction = np.tile(artifact['intercept_no_partial_yes'], (len(support), 1))
    for term in artifact['terms']:
        raw = np.asarray(values[term['feature']])
        z = np.clip((np.where(np.isfinite(raw), raw, term['mean'])-term['mean'])/term['scale'], -5, 5)
        correction += z[:, None]*np.asarray(term['coefficients_no_partial_yes'])
    return np.argmax(offset+artifact['strength']*((artifact['temperature']-1)*offset+correction), axis=1)


def audit(calibration, ordered, out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    out.mkdir(parents=True); (out/'run.log').write_text('Independent native/equation audit started.\n')
    (out/'llm-histories.log').write_text('Zero API calls or image/encoder inference. Cached native classifier predictions and explicit equations only.\n')
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(Path(__file__).read_bytes())
    examples, feature_names, X = data(); same, names, raw, semantic = arrays(); assert examples == same
    y = np.asarray([e['reference'] for e in examples]); regular = np.asarray([e['regular'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); sol, _ = cached(examples)
    pos = {e['case']: i for i, e in enumerate(examples)}; old_groups = set(groups[:99])
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in semantic], dtype=bool)
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    manifests = {str(path): read(path/'manifest.json') for path in (calibration, ordered)}
    for path in (calibration, ordered):
        manifest = manifests[str(path)]
        assert digest(read(path/'protocol.json')) == manifest['protocol_ref']
        for file, sha in manifest['code_sha256'].items():
            assert fingerprint(path/'source_snapshot'/Path(file).relative_to(ROOT)) == sha
        for file, sha in manifest.get('source_hashes', {}).items():
            assert fingerprint(file) == sha
        assert digest(y.tolist()) == manifest['targets_ref']
    assert fingerprint(catboost._catboost.__file__) == manifests[str(ordered)]['catboost_binary_sha256']
    saved_rows = {str(p): {(r['candidate'], r['case']): r for r in read(p/'predictions.json')} for p in (calibration, ordered)}
    baseline = {r['case']: r for r in read(EXPERT/'predictions.json')}
    rows = {str(p): [] for p in (calibration, ordered)}; retention = []; native_count = 0; equations = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        meta = read(TEACHERS/folder/'teacher.json')['contract']; cs = [feature_names.index(n) for n in meta['columns']]
        assert meta['rows'] == train and digest(X[train][:, cs].tolist()) == meta['matrix_ref'] and digest(y[train].tolist()) == meta['targets_ref']
        native = CatBoostClassifier(); native.load_model(str(TEACHERS/folder/'teacher.cbm'))
        ps = native.predict_proba(X[:, cs], thread_count=2); native_count += 1
        assert np.allclose(ps, read(TEACHERS/folder/'predictions.json')['support'], atol=1e-12, rtol=0)
        current, locked = baseline_predictions(folder, names, raw, semantic, ps, regular, sol, valid)
        assert all(current[i] == baseline[examples[i]['case']]['prediction'] for i in held)
        inner = [(read(INNER/folder/('inner'+str(i))/'membership.json'), read(INNER/folder/('inner'+str(i))/'predictions.json')['support']) for i in range(5)]
        mixed, excluded = source_excluded_views(ps, train, held, groups, inner)
        assert set(np.where(excluded)[0]) == {i for i in train if groups[i] not in old_groups}
        membership = read(calibration/folder/'memberships.json')
        assert membership['genuinely_source_excluded_cases'] == [examples[i]['case'] for i in np.where(excluded)[0]]
        full = attach(raw, semantic, ps, regular); values = {n: full[:, j] for j, n in enumerate(names)}

        def check(study, name, proposed, stored):
            p = proposed.copy(); p[locked] = current[locked]; p[~valid] = regular[~valid]
            assert p.tolist() == stored
            original = int(np.sum(p[:99] == y[:99])); retained_slots = int(sum(p[pos[r['case']]] == r['reference'] for r in slots))
            retention.append({'study': study.name, 'candidate': name, 'fold': f['fold'], 'original_correct': original, 'slots_correct': retained_slots})
            for i in held:
                saved = saved_rows[str(study)][name, examples[i]['case']]
                assert all(saved[key] == examples[i][key] for key in ('case', 'source_group', 'reference', 'regular', 'covered'))
                assert saved['prediction'] == int(p[i]) and saved['baseline'] == int(current[i]) and saved['fold'] == f['fold']
                rows[str(study)].append(saved)

        cal_predictions = read(calibration/folder/'all_predictions.json')
        for scope, kind, setting in CALIBRATIONS:
            name = calibration_name(scope, kind, setting); a = read(calibration/folder/(name+'.json'))
            fit = [i for i in train if valid[i] and (scope == 'mixed' or excluded[i])]
            assert a['fit_cases'] == [examples[i]['case'] for i in fit] and a['fit_sources'] == sorted(set(groups[fit])) and a['teacher_ref'] == digest(meta)
            if kind == 'boundary':
                model = BoundaryCalibration().fit(mixed[fit], y[fit], groups[fit], protected_support=ps[:99], protected_y=y[:99],
                        warrants=warrants[fit] if setting else None, protected_warrants=warrants[:99] if setting else None)
                assert model.bias.tolist() == a['bias_no_partial_yes']
                for rebuilt, recorded in zip(model.trials, a['trials'], strict=True):
                    assert rebuilt['bias'] == recorded['bias'] and rebuilt['retained'] == recorded['retained']
                    for key in ('source_weighted_accuracy', 'negative_log_likelihood', 'bias_norm'):
                        assert np.isclose(rebuilt[key], recorded[key], atol=1e-12, rtol=0)
                p = model.predict(ps, warrants=warrants if setting else None)
            else:
                p = explicit_scores(a, values, ps)
            check(calibration, name, p, cal_predictions[name]); equations += 1
        for family in ('ordinal', 'relative_mean'):
            path = ordered/folder/family; a = read(path/'model.json')
            assert a['train_cases'] == f['train_cases'] and a['held_cases'] == f['held_cases']
            assert a['training_sources'] == sorted(set(groups[train])) and a['held_sources'] == sorted(set(groups[held]))
            cols = [feature_names.index(n) for n in a['columns']]; matrix = X[:, cols]
            assert a['columns'] == f['selected_features'] and digest(matrix[train].tolist()) == a['matrix_ref'] and digest(y[train].tolist()) == a['targets_ref']
            if family == 'ordinal':
                boundary = []
                for j in range(2):
                    model = CatBoostClassifier(); model.load_model(str(path/('model'+str(j)+'.cbm')))
                    boundary.append(model.predict_proba(matrix, thread_count=2)[:, 1]); native_count += 1
                support = ordered_probabilities(*boundary)
                assert np.all(support >= 0) and np.allclose(support.sum(axis=1), 1.)
            else:
                model = CatBoostRegressor(); model.load_model(str(path/'model0.cbm'))
                support = mean_support(model.predict(matrix, thread_count=2)[:, 0]); native_count += 1
            assert np.allclose(support, a['support'], atol=1e-12, rtol=0)
            for _, alpha, warranted in [c for c in ORDERED if c[0] == family]:
                name = ordered_name(family, alpha, warranted); stored = read(path/(name+'.json'))
                assert stored['alpha'] == alpha and stored['requires_grading_warrant'] == warranted
                p = np.argmax((1-alpha)*ps+alpha*support, axis=1)
                if warranted:
                    veto = ~warrants[np.arange(len(p)), p]; p[veto] = np.argmax(ps[veto], axis=1)
                check(ordered, name, p, stored['predictions']); equations += 1
        print({'fold': f['fold'], 'native_models_checked': native_count, 'equations_replayed': equations}, flush=True)
    results, eligibility = {}, {}
    for study in (calibration, ordered):
        results[study.name] = {}
        eligibility[study.name] = {}
        declared = read(study/'results.json')
        for name in declared:
            selected = [r for r in rows[str(study)] if r['candidate'] == name]
            observed = accuracy(selected, 'prediction'); assert observed == declared[name]['accuracy']
            assert len(selected) == 276 and sum(r['covered'] for r in selected) == 273
            results[study.name][name] = observed
            controls = [r for r in retention if r['study'] == study.name and r['candidate'] == name]
            assert len(controls) == 6
            retained = all(r['original_correct'] == 99 and r['slots_correct'] == 144 for r in controls)
            key = 'all_original_fits_retained' if study == calibration else 'all_original_cases_and_slots_retained'
            assert declared[name][key] == retained
            eligibility[study.name][name] = retained
        save_json(out/(study.name+'-predictions.json'), rows[str(study)])
    verification = {'passed': True, 'native_models_checked': native_count, 'equations_replayed': equations,
                    'all_originals_retained': all(r['original_correct'] == 99 and r['slots_correct'] == 144 for r in retention),
                    'eligibility_matches_declarations': True, 'eligibility': eligibility,
                    'best_eligible_correct': max(results[s][n]['correct'] for s, values in eligibility.items() for n, eligible in values.items() if eligible),
                    'upstream_coverage': 273, 'results': results, 'new_api_calls': 0, 'reserved_sources_used': 0,
                    'scope': 'Replay of exploratory reviewed development controls, not fresh validation or a new deployed policy.'}
    save_json(out/'retention.json', retention); save_json(out/'verification.json', verification)
    save_json(out/'manifest.json', {'auditor_sha256': fingerprint(__file__), 'source_manifests': {str(p): fingerprint(p/'manifest.json') for p in (calibration, ordered)}})
    (out/'run.log').write_text('Native/equation, membership, original-slot and unchanged-coverage audit complete. See verification.json.\n')
    print(verification, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--calibration-study', type=Path, required=True); p.add_argument('--ordered-study', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.calibration_study.resolve(), a.ordered_study.resolve(), a.output_dir.resolve())
