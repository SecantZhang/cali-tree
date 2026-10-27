"""Test moderate class weighting with the frozen semantic correction."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil

from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from critical.core.calibration.tempered_weights_v147 import weights
from critical.core.calibration.class_balance_v141 import classification_metrics, weight_receipt
from critical.core.calibration.semantic_residual_runtime_v104 import admissible
from critical.core.calibration.semantic_residual_v103 import corrected_support
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, data, read
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_seeded_rubric_v73 import attach
from run.calitree_compact_balance_v143 import CACHE, CACHE_AUDIT, VERIFIED, SOURCE
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

EXPONENTS = (.25, .5, .75)


def fit_teacher(job, X, names, y, out):
    f, exponent = job; folder = 'fold'+str(f['fold'])
    contract = read(TEACHERS/folder/'teacher.json')['contract']; train = contract['rows']
    columns = [names.index(n) for n in contract['columns']]
    assert digest(X[train][:, columns].tolist()) == contract['matrix_ref']
    assert digest(y[train].tolist()) == contract['targets_ref']
    trials = []
    for multiplier in (1., 5., 25.):
        w = weights(y[train], exponent, np.asarray(train) < 99, multiplier)
        model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=1200,
            learning_rate=.05, l2_leaf_reg=3., random_seed=20261021, thread_count=2,
            verbose=False, allow_writing_files=False, bootstrap_type='No', random_strength=0.)
        model.fit(X[train][:, columns], y[train], sample_weight=w*len(w))
        retained = bool(np.all(model.predict(X[:99, columns]).reshape(-1) == y[:99]))
        trials.append({'original_multiplier': multiplier, 'retained': retained, **weight_receipt(y[train], w)})
        if retained:
            break
    directory = out/'teachers'/('eta'+str(exponent))/folder
    directory.mkdir(parents=True, exist_ok=True)
    model.save_model(str(directory/'model.cbm')); model.save_model(str(directory/'native.json'), format='json')
    support = np.asarray(model.predict_proba(X[:, columns]))
    save_json(directory/'support.json', support.tolist())
    save_json(directory/'metadata.json', {'contract': contract, 'exponent': exponent,
        'original_multiplier': multiplier, 'trials': trials, 'retained': retained,
        'weight_ref': digest(w.tolist()), 'weight_receipt': weight_receipt(y[train], w)})
    return {'fold': f['fold'], 'exponent': exponent, 'retained': retained}


def actual_predictions(d, a, support):
    current = np.argmax(support, axis=1)
    current[a['locked']] = a['current'][a['locked']]
    current[~d['valid']] = d['regular'][~d['valid']]
    review = d['valid'] & ~a['locked'] & (support.max(axis=1) < .8)
    local_matrix = d['extra']*review[:, None]
    for i in np.flatnonzero(review & d['available']):
        for key, value in local.view_flags(d['flags_by_row'][i], int(np.argmax(support[i])), int(d['regular'][i])).items():
            local_matrix[i, d['extra_names'].index(key)] = int(value)
    matrix = np.concatenate([attach(d['raw'], d['semantic'], support, d['regular']), local_matrix, support], axis=1)
    metadata = read(SOURCE/a['folder']/'contextual_depth2.json')
    columns = [d['names'].index(n) for n in metadata['features']]
    head = CatBoostRegressor(); head.load_model(str(SOURCE/a['folder']/'contextual_depth2.cbm'))
    delta = head.predict(matrix[:, columns])
    predictions = {}; trials = []
    for strength in (1., .75, .5, .25, 0.):
        if strength > metadata['strength']:
            continue
        proposal = np.argmax(corrected_support(support, delta, strength), axis=1)
        p = current.copy()
        for i in np.flatnonzero(review & d['available']):
            if admissible(d['flags_by_row'][i], int(np.argmax(support[i])), int(d['regular'][i]), int(proposal[i])):
                p[i] = proposal[i]
        predictions[strength] = p
        trials.append({'strength': strength, 'original_correct': int(np.sum(p[:99] == d['y'][:99]))})
    passing = [t for t in trials if t['original_correct'] == 99]
    if not passing:
        raise ValueError('Main teacher does not retain original cases even with the semantic head off')
    selected = passing[0]['strength']
    return {'main_prior': current, 'fixed_head': predictions[metadata['strength']],
            'protected_head': predictions[selected]}, review, {'selected_strength': selected, 'trials': trials}


def run(out, workers=3):
    if out.exists():
        raise ValueError('Fresh tempered-weight experiment directory required')
    protocol = {'version': 'tempered-class-balance-v147', 'exponents': EXPONENTS,
        'primary': 'eta0.5_protected_head', 'variants': ['main_prior', 'fixed_head', 'protected_head'],
        'weights': 'Original-anchor row weight divided by within-training-grade total anchor weight raised to exponent; normalize. Exponent0 is original weighting and1 is full class balance. New fits use only.25/.5/.75.',
        'architecture': 'Same1200 depth8 MultiClass main classifier and frozen128 depth2 semantic head. Existing earlier rule/expert contexts remain on the original teacher, as in v141. No new inner teachers or semantic-head fitting.',
        'protection': 'First original multiplier1/5/25 retaining99 correct. Protected-head arm keeps the greatest old-grid strength at or below its frozen strength retaining every actual original prediction. No held labels select it.',
        'routing': 'Recompute local review gate and view flags from the new teacher. Existing cached facts only; missing/failed records retain the new base. All276 cases remain scored.',
        'source_control': 'Same five source-held folds and full-fit fold5 for artifact/local checks only. Exact train-only selected columns and held-source sibling exclusion unchanged.',
        'new_api_calls': 0, 'new_encoder_or_observer_calls': 0, 'reserved_sources_used': 0,
        'serving_changed': False, 'workers': workers, 'threads_per_fit': 2}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Fixed moderate class-weight comparison started.\n')
    (out/'llm-histories.log').write_text('Zero API, encoder or observer calls; cached features and local CatBoost fitting only.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/tempered_weights_v147.py']
    hashes = {str(p): file_hash(p) for p in sources}
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'code_sha256': hashes, 'protocol_ref': digest(protocol),
        'selected_pipeline_sha256': file_hash(ROOT/'critical/core/calibration/artifacts/calitree_current.json')})
    examples, names, X = data(); y = np.asarray([e['reference'] for e in examples])
    folds = [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']
    pos = {e['case']: i for i, e in enumerate(examples)}
    for f in folds:
        train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        assert not {examples[i]['source_group'] for i in train} & {examples[i]['source_group'] for i in held}
    jobs = [(f, exponent) for f in folds for exponent in EXPONENTS]; completed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(fit_teacher, job, X, names, y, out) for job in jobs]
        for future in as_completed(pending):
            completed.append(future.result())
            save_json(out/'fit_progress.json', {'completed': completed, 'total': len(jobs)})
            print({'completed': len(completed), 'total': len(jobs), 'last': completed[-1]}, flush=True)
    d = load(CACHE, CACHE_AUDIT); assert d['examples'] == examples
    prior = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows = []; retention = []
    for f in folds:
        a = fold_arrays(d, f)
        for exponent in EXPONENTS:
            directory = out/'teachers'/('eta'+str(exponent))/a['folder']
            support = np.asarray(read(directory/'support.json'))
            predictions, review, strength = actual_predictions(d, a, support)
            save_json(directory/'head_strength.json', strength)
            for variant, p in predictions.items():
                name = 'eta'+str(exponent)+'_'+variant
                correct = int(np.sum(p[:99] == d['y'][:99]))
                count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots))
                retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': correct,
                    'slots_correct': count, 'eligible': correct == 99 and count == 144})
                if variant != 'fixed_head':
                    assert correct == 99 and count == 144
                assert np.array_equal(p[a['locked']], a['current'][a['locked']])
                assert np.array_equal(p[~d['valid']], d['regular'][~d['valid']])
                save_json(directory/(variant+'-predictions.json'), p.tolist())
                for i in a['held']:
                    e = examples[i]
                    rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                        'baseline': prior[e['case']]['prediction'], 'review': bool(review[i]),
                        'local_available': bool(review[i] and d['available'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention)
    results = {}
    for name in sorted({r['candidate'] for r in rows}):
        rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == 276 and len({r['case'] for r in rr}) == 276
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'coverage': sum(r['covered'] for r in rr),
            'all_original_cases_and_slots_retained': all(r['eligible'] for r in retention if r['candidate'] == name)}
        assert results[name]['coverage'] == 273
    save_json(out/'results.json', results)
    assert all(file_hash(p) == sha for p, sha in hashes.items())
    (out/'run.log').write_text('Completed18 moderate main-model fits and nine cached inference arms; selected default unchanged.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy'], v['all_original_cases_and_slots_retained']) for k, v in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--workers', type=int, default=3); args = p.parse_args()
    run(args.output_dir.resolve(), args.workers)
