"""Class-balance the existing visual booster and semantic correction offline.

Same capacity, evidence, source folds and original-case protection. The primary
comparison balances both learned layers; isolated arms identify the tradeoff.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil
import time

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from critical.core.calibration.class_balance_v141 import (
    ClassBalancedResidual, training_weights, weight_receipt, classification_metrics)
from critical.core.calibration.semantic_residual_v103 import SemanticResidual, corrected_support
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, ResidualExecutor, admissible
from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, data, read
from run.calitree_seeded_rubric_v73 import attach
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

CACHE = ROOT/'logs/exps/261023-local-review-cache-v96-r1'
CACHE_AUDIT = ROOT/'logs/exps/261023-local-review-cache-v98-complete-r1'
INCUMBENT = ROOT/'logs/exps/261023-verified-semantic-residual-v105-r1'
RESIDUAL_STUDY = ROOT/'logs/exps/261023-semantic-residual-v103-r1'
ARMS = ('current_control', 'balanced_head', 'balanced_base_raw', 'balanced_base',
        'balanced_base_frozen_head', 'balanced_base_source_head', 'balanced_base_balanced_head')


def teacher_jobs(examples):
    pos = {r['case']: i for i, r in enumerate(examples)}
    groups = np.asarray([r['source_group'] for r in examples])
    jobs = []
    for f in read(STUDY/'folds.json'):
        if f['candidate'] != 'boost_full_vision':
            continue
        folder = 'fold'+str(f['fold'])
        train = [pos[c] for c in f['train_cases']]
        held_sources = set(groups[[pos[c] for c in f['held_cases']]])
        for inner in (None, *range(5)):
            old = TEACHERS/folder if inner is None else INNER/folder/('inner'+str(inner))
            old_contract = read(old/'teacher.json')['contract']
            if inner is None:
                rows = train
            else:
                membership = read(old/'membership.json')
                rows = [i for i in train if groups[i] not in membership['held_sources']]
                assert membership['train'] == rows
                assert not set(groups[rows]) & set(membership['held_sources'])
            assert rows == old_contract['rows'] and not set(groups[rows]) & held_sources
            jobs.append({'key': folder+('/inner'+str(inner) if inner is not None else ''),
                         'old': str(old), 'rows': rows, 'outer': f['fold'], 'inner': inner})
    assert len(jobs) == 36
    return jobs


def fit_teacher(job, names, X, y, out):
    started = time.monotonic(); old = Path(job['old'])
    old_contract = read(old/'teacher.json')['contract']
    cols = [names.index(n) for n in old_contract['columns']]
    rows = job['rows']; original = np.asarray(rows) < 99
    assert digest(X[rows][:, cols].tolist()) == old_contract['matrix_ref']
    assert digest(y[rows].tolist()) == old_contract['targets_ref']
    trials = []
    for multiplier in (1., 5., 25.):
        weights = training_weights(y[rows], original=original, original_weight=multiplier)
        model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=1200, learning_rate=.05,
            l2_leaf_reg=3., random_seed=20261021, thread_count=2, verbose=False,
            allow_writing_files=False, bootstrap_type='No', random_strength=0.)
        model.fit(X[rows][:, cols], y[rows], sample_weight=weights*len(rows))
        retained = bool(np.all(model.predict(X[:99, cols]).reshape(-1) == y[:99]))
        trials.append({'original_multiplier': multiplier, 'retained': retained, **weight_receipt(y[rows], weights)})
        if retained:
            break
    directory = out/'teachers'/job['key']; directory.mkdir(parents=True, exist_ok=True)
    model.save_model(str(directory/'teacher.cbm'))
    model.save_model(str(directory/'native.json'), format='json')
    support = np.asarray(model.predict_proba(X[:, cols]))
    restored = CatBoostClassifier(); restored.load_model(str(directory/'teacher.cbm'))
    assert np.allclose(restored.predict_proba(X[:, cols]), support, atol=1e-12, rtol=0)
    metadata = {'version': 'equal-class-visual-teacher-v141', 'contract': old_contract,
        'old_contract_sha256': file_hash(old/'teacher.json'), 'trials': trials,
        'original_multiplier': multiplier, 'original_cases_retained': retained,
        'training_weights_ref': digest(weights.tolist()), 'training_weights': weight_receipt(y[rows], weights),
        'elapsed_seconds': time.monotonic()-started}
    save_json(directory/'teacher.json', metadata)
    save_json(directory/'predictions.json', {'support': support.tolist()})
    if job['inner'] is not None:
        shutil.copyfile(old/'membership.json', directory/'membership.json')
    return {'key': job['key'], 'retained': retained, 'elapsed_seconds': metadata['elapsed_seconds'], 'trials': len(trials)}


def reuse_teacher(job, names, X, y, out, previous):
    """Recover only complete exact fits from the stopped mkdir-race run."""
    origin = previous/'teachers'/job['key']
    files = ['teacher.cbm', 'native.json', 'teacher.json', 'predictions.json']
    if job['inner'] is not None:
        files.append('membership.json')
    if not all((origin/f).exists() for f in files):
        return None
    manifest = read(previous/'manifest.json')
    snapshot = previous/'source_snapshot/run'/Path(__file__).name
    assert manifest['code_sha256'][str(Path(__file__))] == file_hash(snapshot)
    old_tree = ast.parse(snapshot.read_text().replace('directory.mkdir(parents=True)',
                                                   'directory.mkdir(parents=True, exist_ok=True)'))
    new_tree = ast.parse(Path(__file__).read_text())
    function = lambda tree: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fit_teacher')
    assert ast.dump(function(old_tree)) == ast.dump(function(new_tree))
    metadata = read(origin/'teacher.json'); old = Path(job['old'])
    assert metadata['contract'] == read(old/'teacher.json')['contract']
    assert metadata['old_contract_sha256'] == file_hash(old/'teacher.json')
    rows = job['rows']; cols = [names.index(n) for n in metadata['contract']['columns']]
    assert rows == metadata['contract']['rows']
    assert digest(X[rows][:, cols].tolist()) == metadata['contract']['matrix_ref']
    assert digest(y[rows].tolist()) == metadata['contract']['targets_ref']
    weights = training_weights(y[rows], original=np.asarray(rows) < 99,
                               original_weight=metadata['original_multiplier'])
    assert metadata['training_weights_ref'] == digest(weights.tolist())
    assert metadata['training_weights'] == weight_receipt(y[rows], weights)
    model = CatBoostClassifier(); model.load_model(str(origin/'teacher.cbm'))
    support = np.asarray(model.predict_proba(X[:, cols]))
    assert np.allclose(support, read(origin/'predictions.json')['support'], atol=1e-12, rtol=0)
    assert metadata['original_cases_retained'] == bool(np.all(np.argmax(support[:99], axis=1) == y[:99]))
    if job['inner'] is not None:
        assert read(origin/'membership.json') == read(old/'membership.json')
    destination = out/'teachers'/job['key']; destination.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copyfile(origin/f, destination/f)
    save_json(destination/'reuse.json', {'origin': str(origin),
        'origin_manifest_sha256': file_hash(previous/'manifest.json'),
        'fit_function_unchanged_except_parent_mkdir': True,
        'files': {f: file_hash(origin/f) for f in files}})
    return {'key': job['key'], 'retained': metadata['original_cases_retained'],
            'elapsed_seconds': metadata['elapsed_seconds'], 'trials': len(metadata['trials']), 'reused': True}


def balanced_arrays(d, f, teachers):
    old = fold_arrays(d, f)
    ps = np.asarray(read(teachers/old['folder']/'predictions.json')['support'])
    inner = [(read(teachers/old['folder']/('inner'+str(k))/'membership.json'),
              read(teachers/old['folder']/('inner'+str(k))/'predictions.json')['support']) for k in range(5)]
    oof, genuine = source_excluded_views(ps, old['train'], old['held'], d['groups'], inner)
    current = np.argmax(ps, axis=1)
    # Frozen earlier experts retain their ORIGINAL teacher context and priority.
    # Reinterpreting their learned route on a different teacher would add a
    # second, uncontrolled treatment to this class-weight ablation.
    current[old['locked']] = old['current'][old['locked']]
    current[~d['valid']] = d['regular'][~d['valid']]
    actual = d['valid'] & ~old['locked'] & (ps.max(axis=1) < .8)
    fitting = d['valid'] & genuine & (oof.max(axis=1) < .8)
    fit = np.flatnonzero(fitting & d['available']).tolist()
    protected = [i for i in range(99) if actual[i] and d['available'][i]]
    assert set(fit) <= set(old['train'])
    assert not set(d['groups'][fit]) & set(d['groups'][old['held']])
    matrices = []
    for probabilities, mask in ((ps, actual), (oof, fitting)):
        local_matrix = d['extra']*mask[:, None]
        for i in np.flatnonzero(mask & d['available']):
            for key, value in local.view_flags(d['flags_by_row'][i], int(np.argmax(probabilities[i])), int(d['regular'][i])).items():
                local_matrix[i, d['extra_names'].index(key)] = int(value)
        matrices.append(np.concatenate([attach(d['raw'], d['semantic'], probabilities, d['regular']),
                                       local_matrix, probabilities], axis=1))
    return {**old, 'ps': ps, 'oof': oof, 'genuine': genuine, 'current': current,
            'actual': actual, 'fitting': fitting, 'fit': fit, 'protected': protected,
            'full': matrices[0], 'T': matrices[1]}


def apply_head(d, a, model, columns):
    proposal = np.argmax(corrected_support(a['ps'], model.model.predict(a['full'][:, columns]), model.strength), axis=1)
    result = a['current'].copy()
    for i in np.flatnonzero(a['actual'] & d['available']):
        if admissible(d['flags_by_row'][i], int(np.argmax(a['ps'][i])), int(d['regular'][i]), int(proposal[i])):
            result[i] = proposal[i]
    assert np.array_equal(result[~(a['actual'] & d['available'])], a['current'][~(a['actual'] & d['available'])])
    return result


def compare(out, *, head_only=False):
    d = load(CACHE, CACHE_AUDIT)
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    reference = {r['case']: r for r in read(INCUMBENT/'predictions.json')}
    rows = []; retention = []; head_receipts = []; errors = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        old = fold_arrays(d, f); folder = old['folder']
        metadata = read(RESIDUAL_STUDY/folder/'contextual_depth2.json')
        columns = [d['names'].index(n) for n in metadata['features']]
        scopes = [('original', old)]
        if not head_only:
            scopes.append(('balanced', balanced_arrays(d, f, out/'teachers')))
        predictions = {}; contexts = {}
        for scope, a in scopes:
            if scope == 'balanced':
                predictions['balanced_base'] = a['current'].copy()
                raw = np.argmax(a['ps'], axis=1); raw[~d['valid']] = d['regular'][~d['valid']]
                predictions['balanced_base_raw'] = raw
                stored = CatBoostRegressor(); stored.load_model(str(RESIDUAL_STUDY/folder/'contextual_depth2.cbm'))
                class FrozenHead:
                    pass
                frozen = FrozenHead(); frozen.model = stored; frozen.strength = metadata['strength']
                predictions['balanced_base_frozen_head'] = apply_head(d, a, frozen, columns)
                for name in ('balanced_base', 'balanced_base_raw', 'balanced_base_frozen_head'):
                    contexts[name] = a
            for balance in (False, True):
                if scope == 'original':
                    name = 'balanced_head' if balance else 'current_control'
                else:
                    name = 'balanced_base_balanced_head' if balance else 'balanced_base_source_head'
                cls = ClassBalancedResidual if balance else SemanticResidual
                fit, protected = a['fit'], a['protected']
                if not fit:
                    raise ValueError('Empty source-excluded review fitting region')
                model = cls(metadata['features'], depth=2, iterations=128).fit(a['T'][fit][:, columns], d['y'][fit],
                    support=a['oof'][fit], groups=d['groups'][fit], protected_X=a['full'][protected][:, columns],
                    protected_y=d['y'][protected], protected_support=a['ps'][protected])
                artifact = model.artifact({**local.DESCRIPTIONS, **SUPPORT})
                directory = out/'heads'/folder/name; directory.mkdir(parents=True)
                model.model.save_model(str(directory/'model.cbm'))
                model.model.save_model(str(directory/'native.json'), format='json')
                compiled = compile_polynomial(read(directory/'native.json'), artifact)
                executor = ResidualExecutor(compiled)
                delta = np.asarray(model.model.predict(a['full'][:, columns])); maximum = 0.
                # Execute exported named terms independently of CatBoost for all
                #915 cached inputs; these are equivalence checks, not915 test cases.
                for i in range(len(d['examples'])):
                    values = {n: float(a['full'][i, j]) if n in SUPPORT else bool(a['full'][i, j])
                              for j, n in enumerate(d['names'])}
                    portable = executor.evaluate(values, a['ps'][i].tolist())
                    maximum = max(maximum, float(np.max(np.abs(np.asarray(portable['residual'])-delta[i]))))
                assert maximum < 1e-12
                weights = training_weights(d['y'][fit], groups=d['groups'][fit], balanced=balance)
                receipt = {'candidate': name, 'fold': f['fold'], 'class_balanced': balance,
                    'fit_cases': [d['examples'][i]['case'] for i in fit],
                    'protected_review_cases': [d['examples'][i]['case'] for i in protected],
                    'fit_matrix_ref': digest(a['T'][fit][:, columns].tolist()),
                    'support_ref': digest(a['oof'][fit].tolist()), 'training_weights_ref': digest(weights.tolist()),
                    'training_weights': weight_receipt(d['y'][fit], weights),
                    'max_portable_error': maximum, 'shared_terms': len(compiled['clauses'])}
                head_receipts.append(receipt)
                save_json(directory/'metadata.json', artifact); save_json(directory/'receipt.json', receipt)
                save_json(directory/'rubric.json', compiled); (directory/'rubric.txt').write_text(compiled['rubric'])
                predictions[name] = apply_head(d, a, model, columns); contexts[name] = a
        assert predictions['current_control'].tolist() == read(RESIDUAL_STUDY/folder/'contextual_depth2_guarded-predictions.json')
        for name, p in predictions.items():
            a = contexts[name]
            correct = int(np.sum(p[:99] == d['y'][:99]))
            slots = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in originals))
            retained = correct == 99 and slots == 144
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': correct,
                              'slots_correct': slots, 'eligible': retained})
            save_json(out/'predictions_by_fold'/folder/(name+'.json'), p.tolist())
            save_json(out/'routes_by_fold'/folder/(name+'.json'), {
                'review': a['actual'].tolist(), 'available': d['available'].tolist(),
                'locked': a['locked'].tolist(), 'covered': d['valid'].tolist(),
                'fit_cases': [d['examples'][i]['case'] for i in a['fit']]})
            for i in a['held']:
                e = d['examples'][i]
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                    'baseline': reference[e['case']]['prediction'], 'review': bool(a['actual'][i]),
                    'local_available': bool(a['actual'][i] and d['available'][i]),
                    'prior_rule_priority': bool(a['locked'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention)
        print({'stage': 'comparison', 'fold': f['fold'], 'candidates': len(predictions),
               'old_fit_rows': len(old['fit']), 'balanced_fit_rows': len(scopes[-1][1]['fit'])}, flush=True)
    results = {}
    for name in sorted({r['candidate'] for r in rows}):
        r = [v for v in rows if v['candidate'] == name]
        assert len(r) == 276 and len({v['case'] for v in r}) == 276
        results[name] = {'metrics': classification_metrics(r), 'baseline': classification_metrics(r, 'baseline'),
            'gains': sum(v['prediction'] == v['reference'] != v['baseline'] for v in r),
            'losses': sum(v['baseline'] == v['reference'] != v['prediction'] for v in r),
            'changes': sum(v['prediction'] != v['baseline'] for v in r),
            'upstream_coverage': sum(v['covered'] for v in r), 'review_cases': sum(v['review'] for v in r),
            'review_observation_available': sum(v['local_available'] for v in r),
            'original_cases_and_slots_retained': all(v['eligible'] for v in retention if v['candidate'] == name)}
        assert results[name]['upstream_coverage'] == 273
    assert results['current_control']['metrics']['correct'] == 227
    save_json(out/'results.json', results); save_json(out/'head_receipts.json', head_receipts)
    save_json(out/'state.json', {'stage': 'complete', 'head_only': head_only, 'serving_changed': False,
                               'independent_comparison_audit_pending': True})
    with (out/'run.log').open('a') as log:
        log.write('Completed fixed class-balance arms. Current control reproduces227/276. No default/policy promotion.\n')
    print({k: {'correct': v['metrics']['correct'], 'balanced_accuracy': v['metrics']['balanced_accuracy'],
               'eligible': v['original_cases_and_slots_retained']} for k, v in results.items()}, flush=True)


def run(out, workers=3, *, head_only=False, reuse=None):
    if out.exists():
        raise ValueError('Fresh class-balance experiment directory required')
    examples, names, X = data(); y = np.asarray([e['reference'] for e in examples])
    jobs = teacher_jobs(examples)
    protocol = {'version': 'class-balanced-existing-model-v141', 'head_only': head_only,
        'primary_arm': 'balanced_head' if head_only else 'balanced_base_balanced_head',
        'arms': ['current_control', 'balanced_head'] if head_only else list(ARMS),
        'training': 'Use every existing fitting row. Main booster starts with equal row weights; semantic residual starts with inverse source-size weights. Normalize each observed class to equal total weight using FITTING labels only. No downsampling, synthetic data or evaluation resampling.',
        'architecture': 'Identical depth8/1200-tree MultiClass visual booster and depth2/128-tree MultiRMSE contextual semantic residual, existing seeds/rates/regularization and deterministic settings.',
        'protection': 'Main original-row multiplier first of1/5/25 retaining99 predictions; re-normalize classes after each multiplier so class masses remain equal. Residual strength0/.25/.5/.75/1 uses fitting objective with actual-original veto. Report any retention failure as ineligible.',
        'routing': 'Keep v72/v87 priority in their ORIGINAL teacher context. Recompute .8 review masks and view features using each new teacher; use only existing bound8B observations. Unavailable review observations retain the corresponding base prediction. No other-fold review membership is an input feature.',
        'evaluation': 'Same276 development cases, same five outer source-held folds, held-source siblings excluded from every teacher/head. Fold5 fits all915 for local protection and artifact analysis only. Equal-class evaluation is balanced accuracy; no held label enters fitting or strength/anchor selection.',
        'teacher_jobs': [] if head_only else jobs, 'workers': workers, 'threads_per_fit': 2,
        'reuse_teachers_from': str(reuse) if reuse is not None else None,
        'reuse_manifest_sha256': file_hash(reuse/'manifest.json') if reuse is not None else None,
        'new_api_calls': 0, 'new_encoder_or_observer_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
        'limits': 'Reviewed development comparison, not untouched validation. No promotion or goal-status update.'}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Started class-balanced same-architecture offline comparison.\n')
    (out/'llm-histories.log').write_text('Zero model API, local observer, encoder or reserved-set calls. Existing cached evidence only.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/class_balance_v141.py',
        ROOT/'critical/core/calibration/semantic_residual_v103.py', ROOT/'run/verify_calitree_semantic_residual_v105.py',
        ROOT/'critical/core/calibration/semantic_polynomial_v111.py', ROOT/'run/calitree_source_excluded_calibration_v89.py']
    hashes = {str(p): file_hash(p) for p in sources}
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': hashes,
        'features_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()),
        'folds_sha256': file_hash(STUDY/'folds.json'), 'catboost_version': catboost.__version__,
        'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json'),
        'catboost_binary_sha256': file_hash(catboost._catboost.__file__)})
    if not head_only:
        completed = []
        remaining = []
        for job in jobs:
            result = reuse_teacher(job, names, X, y, out, reuse) if reuse is not None else None
            if result is not None:
                completed.append(result)
            else:
                remaining.append(job)
        print({'stage': 'teachers', 'exact_reused': len(completed), 'remaining': len(remaining)}, flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = [pool.submit(fit_teacher, job, names, X, y, out) for job in remaining]
            for future in as_completed(pending):
                completed.append(future.result())
                save_json(out/'teacher_progress.json', {'completed': completed, 'total': len(jobs)})
                print({'stage': 'teachers', 'completed': len(completed), 'total': len(jobs), 'last': completed[-1]}, flush=True)
        if not all(r['retained'] for r in completed):
            with (out/'run.log').open('a') as log:
                log.write('Some source-excluded teacher trials failed99-case protection; see per-teacher trials.\n')
    compare(out, head_only=head_only)
    assert all(file_hash(path) == sha for path, sha in hashes.items())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--head-only', action='store_true')
    parser.add_argument('--reuse-teachers', type=Path)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.workers, head_only=args.head_only,
        reuse=args.reuse_teachers.resolve() if args.reuse_teachers is not None else None)
