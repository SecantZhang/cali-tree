"""Optimize final balanced accuracy using two compact calibration parameters."""
import argparse
from pathlib import Path
import shutil

from catboost import CatBoostRegressor
import numpy as np

from critical.core.calibration.compact_balance_v143 import CompactBalance, BIAS_GRID, ORDINAL_GRID
from critical.core.calibration.semantic_residual_v103 import corrected_support
from critical.core.calibration.semantic_residual_runtime_v104 import admissible
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_source_excluded_calibration_v89 import baseline_predictions
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

CACHE = ROOT/'logs/exps/261023-local-review-cache-v96-r1'
CACHE_AUDIT = ROOT/'logs/exps/261023-local-review-cache-v98-complete-r1'
SOURCE = ROOT/'logs/exps/261023-semantic-residual-v103-r1'
VERIFIED = ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2'
CONFIGS = [(family, guard, pareto) for family in ('bias', 'ordinal')
           for guard in (True, False) for pareto in (False, True)]


def name_of(family, guard, pareto):
    return family+('_warrant' if guard else '_score')+('_pareto' if pareto else '_balanced')


def contexts(d, f):
    a = fold_arrays(d, f); folder = a['folder']
    metadata = read(SOURCE/folder/'contextual_depth2.json')
    columns = [d['names'].index(n) for n in metadata['features']]
    model = CatBoostRegressor(); model.load_model(str(SOURCE/folder/'contextual_depth2.cbm'))
    result = {}
    for key, support, matrix in (('actual', a['ps'], a['full']), ('fitting', a['oof'], a['T'])):
        if key == 'actual':
            current, locked = a['current'].copy(), a['locked'].copy()
        else:
            current, locked = baseline_predictions(folder, d['old_names'], d['raw'], d['semantic'],
                support, d['regular'], d['sol'], d['valid'])
        review = d['valid'] & ~locked & (support.max(axis=1) < .8) & d['available']
        masses = corrected_support(support, model.predict(matrix[:, columns]), metadata['strength'])
        proposal = np.argmax(masses, axis=1)
        for i in np.flatnonzero(review):
            if proposal[i] != current[i] and admissible(d['flags_by_row'][i], int(np.argmax(support[i])),
                                                       int(d['regular'][i]), int(proposal[i])):
                current[i] = proposal[i]; locked[i] = True
        locked |= ~d['valid']
        result[key] = {'support': support, 'base': current, 'locked': locked}
    assert result['actual']['base'].tolist() == read(SOURCE/folder/'contextual_depth2_guarded-predictions.json')
    genuine = a['genuine'] if 'genuine' in a else None
    # fold_arrays exposes the genuine mask as a local variable from its
    # source-excluded view builder; fitting is a narrower low-support subset.
    if genuine is None:
        raise ValueError('Full genuine-source mask required')
    fit = [i for i in a['train'] if genuine[i] and d['valid'][i]]
    assert set(fit) <= set(a['train']) and not set(d['groups'][fit]) & set(d['groups'][a['held']])
    return a, result, fit


def run(out):
    if out.exists():
        raise ValueError('Fresh compact-balanced experiment required')
    protocol = {'version': 'compact-balanced-v143', 'configs': CONFIGS,
        'primary': 'bias_warrant_balanced', 'bias_grid': BIAS_GRID, 'ordinal_grid': ORDINAL_GRID,
        'objective': 'Maximize final fitting balanced accuracy, then worst-class recall, accuracy and smaller parameter norm. Pareto arms also veto any fitting per-class recall decrease. Identity is always a candidate.',
        'capacity': 'Two class-score offsets or two ordered grade-index thresholds. Existing three same-requirement grade warrants optionally veto changes. Existing v112 semantic/expert overrides keep priority.',
        'fitting': 'All valid genuinely source-excluded fitting rows, not only the local-review region. No original or outer-held-source row selects boundaries. All99 actual original predictions veto harmful settings.',
        'head': 'Reuse the fixed outer-fit v112 contextual residual and its existing fitting views. It is not independently inner-cross-fitted for calibration. All outer-held source groups remain excluded from every component.',
        'evaluation': 'Same276 reviewed development cases and five source-held folds; full-fit fold5 supplies only local/artifact checks. Report overall/balanced accuracy and each recall. No selection based on outer-held labels.',
        'new_api_calls': 0, 'new_observer_or_encoder_calls': 0, 'new_booster_fits': 0,
        'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Direct final balanced-accuracy calibration started; fixed eight arms.\n')
    (out/'llm-histories.log').write_text('Zero API/observer/encoder calls; existing cached evidence only.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/compact_balance_v143.py',
        ROOT/'run/verify_calitree_semantic_residual_v105.py', ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    d = load(CACHE, CACHE_AUDIT)
    warrants = np.asarray([[s['rubric_'+label+'_ready'] for label in ('no', 'partial', 'yes')] for s in d['semantic']], dtype=bool)
    reference = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows = []; retention = []; memberships = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); folder = a['folder']; full = c['actual']; fitting = c['fitting']
        membership = {'fold': f['fold'], 'fit_cases': [d['examples'][i]['case'] for i in fit],
            'fit_source_groups': sorted(set(d['groups'][fit])), 'held_cases': f['held_cases'],
            'fit_class_counts': [int(np.sum(d['y'][fit] == k)) for k in range(3)]}
        memberships.append(membership)
        for family, guard, pareto in CONFIGS:
            name = name_of(family, guard, pareto)
            model = CompactBalance(family=family, warranted=guard, pareto=pareto).fit(
                fitting['support'][fit], d['y'][fit], fitting['base'][fit], fitting['locked'][fit], warrants[fit],
                protected_support=full['support'][:99], protected_y=d['y'][:99],
                protected_base=full['base'][:99], protected_locked=full['locked'][:99], protected_warrants=warrants[:99])
            p = model.predict(full['support'], full['base'], full['locked'], warrants)
            assert np.all(p[:99] == d['y'][:99])
            assert np.array_equal(p[full['locked']], full['base'][full['locked']])
            count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots)); assert count == 144
            artifact = {**model.artifact(), 'fit_cases': membership['fit_cases'],
                'fit_support_ref': digest(fitting['support'][fit].tolist()),
                'fit_base_ref': digest(fitting['base'][fit].tolist()), 'fit_locks_ref': digest(fitting['locked'][fit].tolist())}
            save_json(out/folder/(name+'.json'), artifact)
            save_json(out/folder/(name+'-predictions.json'), p.tolist())
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': 99,
                'slots_correct': count, 'selected': model.selected})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == reference[e['case']]['prediction']
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                             'baseline': int(full['base'][i]), 'changed': bool(p[i] != full['base'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention)
        save_json(out/'memberships.json', memberships)
        print({'fold': f['fold'], 'fit_rows': len(fit), 'calibrations': len(CONFIGS)}, flush=True)
    results = {}
    for family, guard, pareto in CONFIGS:
        name = name_of(family, guard, pareto); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == 276 and len({r['case'] for r in rr}) == 276
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'changes': sum(r['changed'] for r in rr), 'coverage': sum(r['covered'] for r in rr),
            'all_original_cases_and_slots_retained': True}
        assert results[name]['coverage'] == 273 and results[name]['baseline']['correct'] == 227
    save_json(out/'results.json', results)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources},
        'protocol_ref': digest(protocol), 'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json'),
        'targets_ref': digest(d['y'].tolist())})
    (out/'run.log').write_text('Completed48 compact calibration fits, all99/144 retained and273 coverage unchanged. No default change.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy']) for k, v in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
