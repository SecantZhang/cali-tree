"""Independently replay the class-balanced development comparison, without calls."""
import argparse
import ast
from pathlib import Path
import shutil

from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from critical.core.calibration.class_balance_v141 import (
    training_weights, weight_receipt, classification_metrics, ClassBalancedResidual)
from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.semantic_residual_runtime_v104 import ResidualExecutor, SUPPORT, admissible
from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_class_balanced_v141 import (CACHE, CACHE_AUDIT, INCUMBENT, RESIDUAL_STUDY,
    teacher_jobs, balanced_arrays)
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, data, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS


def native_classifier_support(native, X):
    """Execute native JSON parameters directly; no CatBoost inference is used."""
    X = np.asarray(X, dtype=np.float32)
    mapping = {f['feature_index']: f['flat_feature_index'] for f in native['features_info']['float_features']}
    logits = np.zeros((len(X), 3))
    for tree in native['oblivious_trees']:
        leaf = np.zeros(len(X), dtype=int)
        for bit, split in enumerate(tree.get('splits') or []):
            assert split['split_type'] == 'FloatFeature' and split['border'] == .5
            leaf |= (X[:, mapping[split['float_feature_index']]] > np.float32(split['border'])).astype(int) << bit
        values = np.asarray(tree['leaf_values']).reshape(-1, 3)
        logits += values[leaf]
    scale, bias = native['scale_and_bias']; logits = logits*scale+np.asarray(bias)
    masses = np.exp(logits-logits.max(axis=1, keepdims=True))
    return masses/masses.sum(axis=1, keepdims=True)


def audit(study, out):
    if out.exists():
        raise ValueError('Fresh class-balanced audit directory required')
    protocol = read(study/'protocol.json'); producer = read(study/'manifest.json')
    assert read(study/'state.json')['stage'] == 'complete'
    assert producer['protocol_ref'] == digest(protocol)
    assert producer['folds_sha256'] == file_hash(STUDY/'folds.json')
    assert producer['cache_audit_manifest_sha256'] == file_hash(CACHE_AUDIT/'manifest.json')
    for path, sha in producer['code_sha256'].items():
        assert file_hash(path) == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    d = load(CACHE, CACHE_AUDIT); examples, names, X = data()
    assert examples == d['examples'] and producer['features_ref'] == digest(X.tolist())
    assert producer['targets_ref'] == digest(d['y'].tolist())
    out.mkdir(parents=True)
    (out/'run.log').write_text('Replay training weights, source exclusions, native classifiers and shared semantic terms.\n')
    (out/'llm-histories.log').write_text('Zero API/observer/encoder calls or reserved-source reads.\n')
    source = out/'source_snapshot/run'/Path(__file__).name; source.parent.mkdir(parents=True); shutil.copyfile(__file__, source)
    teacher_errors = []; teacher_receipts = []; reused_teachers = 0
    if protocol.get('reuse_teachers_from'):
        previous = Path(protocol['reuse_teachers_from'])
        assert protocol['reuse_manifest_sha256'] == file_hash(previous/'manifest.json')
        old_snapshot = previous/'source_snapshot/run/calitree_class_balanced_v141.py'
        new_snapshot = study/'source_snapshot/run/calitree_class_balanced_v141.py'
        assert read(previous/'manifest.json')['code_sha256'][str(ROOT/'run/calitree_class_balanced_v141.py')] == file_hash(old_snapshot)
        old_tree = ast.parse(old_snapshot.read_text().replace('directory.mkdir(parents=True)',
                                                           'directory.mkdir(parents=True, exist_ok=True)'))
        new_tree = ast.parse(new_snapshot.read_text())
        function = lambda tree: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fit_teacher')
        assert ast.dump(function(old_tree)) == ast.dump(function(new_tree))
    if not protocol['head_only']:
        assert protocol['teacher_jobs'] == teacher_jobs(examples)
        for job in protocol['teacher_jobs']:
            folder = study/'teachers'/job['key']; metadata = read(folder/'teacher.json')
            if (folder/'reuse.json').exists():
                reuse = read(folder/'reuse.json'); origin = Path(reuse['origin'])
                assert origin == Path(protocol['reuse_teachers_from'])/'teachers'/job['key']
                assert reuse['origin_manifest_sha256'] == protocol['reuse_manifest_sha256']
                assert reuse['fit_function_unchanged_except_parent_mkdir'] is True
                for file, sha in reuse['files'].items():
                    assert file_hash(origin/file) == file_hash(folder/file) == sha
                reused_teachers += 1
            old = Path(job['old']); old_contract = read(old/'teacher.json')['contract']
            assert metadata['contract'] == old_contract
            assert metadata['old_contract_sha256'] == file_hash(old/'teacher.json')
            rows = job['rows']; cols = [names.index(n) for n in old_contract['columns']]
            assert rows == old_contract['rows']
            assert digest(X[rows][:, cols].tolist()) == old_contract['matrix_ref']
            assert digest(d['y'][rows].tolist()) == old_contract['targets_ref']
            w = training_weights(d['y'][rows], original=np.asarray(rows) < 99,
                                 original_weight=metadata['original_multiplier'])
            assert metadata['training_weights_ref'] == digest(w.tolist())
            assert metadata['training_weights'] == weight_receipt(d['y'][rows], w)
            assert np.allclose(metadata['training_weights']['class_weight_mass'], 1/3, atol=1e-14, rtol=0)
            for trial in metadata['trials']:
                tw = training_weights(d['y'][rows], original=np.asarray(rows) < 99,
                                      original_weight=trial['original_multiplier'])
                assert trial['class_weight_mass'] == weight_receipt(d['y'][rows], tw)['class_weight_mass']
                assert np.allclose(trial['class_weight_mass'], 1/3, atol=1e-14, rtol=0)
            model = CatBoostClassifier(); model.load_model(str(folder/'teacher.cbm'))
            saved = np.asarray(read(folder/'predictions.json')['support'])
            native = np.asarray(model.predict_proba(X[:, cols]))
            portable = native_classifier_support(read(folder/'native.json'), X[:, cols])
            maximum = float(np.max(np.abs(portable-native))); teacher_errors.append(maximum)
            assert np.allclose(native, saved, atol=1e-12, rtol=0) and maximum < 1e-12
            retained = bool(np.all(np.argmax(portable[:99], axis=1) == d['y'][:99]))
            assert retained == metadata['original_cases_retained']
            teacher_receipts.append({'key': job['key'], 'class_weight_mass': metadata['training_weights']['class_weight_mass'],
                                     'original_cases_retained': retained, 'max_portable_error': maximum})
        save_json(out/'teacher_checks.json', teacher_receipts)
        print({'native_teachers_checked': len(teacher_receipts), 'max_error': max(teacher_errors)}, flush=True)
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    incumbent = {r['case']: r for r in read(INCUMBENT/'predictions.json')}
    rows = []; retained_rows = []; max_residual_error = 0.; reinduced = 0; source_files = {}
    for f in [v for v in read(STUDY/'folds.json') if v['candidate'] == 'boost_full_vision']:
        old = fold_arrays(d, f); folder = old['folder']
        base_metadata = read(RESIDUAL_STUDY/folder/'contextual_depth2.json')
        columns = [d['names'].index(n) for n in base_metadata['features']]
        scope_arrays = {'original': old}
        if not protocol['head_only']:
            scope_arrays['balanced'] = balanced_arrays(d, f, study/'teachers')
        results = {}; contexts = {}
        for scope, a in scope_arrays.items():
            assert not set(d['groups'][a['train']]) & set(d['groups'][a['held']])
            assert set(a['fit']) <= set(a['train'])
            assert not set(d['groups'][a['fit']]) & set(d['groups'][a['held']])
            assert np.array_equal(a['actual'], d['valid'] & ~a['locked'] & (a['ps'].max(axis=1) < .8))
            if scope == 'balanced':
                raw = np.argmax(a['ps'], axis=1); raw[~d['valid']] = d['regular'][~d['valid']]
                results['balanced_base_raw'] = raw
                results['balanced_base'] = a['current'].copy()
                contexts['balanced_base_raw'] = contexts['balanced_base'] = a
            for balance in (False, True):
                name = ('balanced_head' if balance else 'current_control') if scope == 'original' else (
                       'balanced_base_balanced_head' if balance else 'balanced_base_source_head')
                path = study/'heads'/folder/name; metadata = read(path/'metadata.json'); receipt = read(path/'receipt.json')
                fit, protected = a['fit'], a['protected']
                assert receipt['fit_cases'] == [examples[i]['case'] for i in fit]
                assert receipt['protected_review_cases'] == [examples[i]['case'] for i in protected]
                assert receipt['fit_matrix_ref'] == digest(a['T'][fit][:, columns].tolist())
                assert receipt['support_ref'] == digest(a['oof'][fit].tolist())
                weights = training_weights(d['y'][fit], groups=d['groups'][fit], balanced=balance)
                assert receipt['training_weights_ref'] == digest(weights.tolist())
                assert receipt['training_weights'] == weight_receipt(d['y'][fit], weights)
                if balance:
                    masses = np.asarray(receipt['training_weights']['class_weight_mass'])
                    assert np.allclose(masses[masses > 0], 1/np.sum(masses > 0))
                cls = ClassBalancedResidual if balance else SemanticResidual
                fitted = cls(metadata['features'], depth=2, iterations=128).fit(a['T'][fit][:, columns], d['y'][fit],
                    support=a['oof'][fit], groups=d['groups'][fit], protected_X=a['full'][protected][:, columns],
                    protected_y=d['y'][protected], protected_support=a['ps'][protected])
                assert fitted.artifact({**local.DESCRIPTIONS, **SUPPORT}) == metadata
                target = out/folder/(name+'-native.json'); target.parent.mkdir(exist_ok=True)
                fitted.model.save_model(str(target), format='json')
                reinduced_native = read(target); stored_native = read(path/'native.json')
                for key in ('features_info', 'oblivious_trees', 'scale_and_bias'):
                    assert reinduced_native[key] == stored_native[key]
                compiled = compile_polynomial(stored_native, metadata)
                assert compiled == read(path/'rubric.json')
                assert compiled['rubric'] == (path/'rubric.txt').read_text()
                executor = ResidualExecutor(compiled)
                delta = np.asarray(fitted.model.predict(a['full'][:, columns]))
                p = a['current'].copy()
                for i in range(len(examples)):
                    values = {n: float(a['full'][i, j]) if n in SUPPORT else bool(a['full'][i, j])
                              for j, n in enumerate(d['names'])}
                    result = executor.evaluate(values, a['ps'][i].tolist())
                    maximum = float(np.max(np.abs(np.asarray(result['residual'])-delta[i])))
                    max_residual_error = max(max_residual_error, maximum)
                    assert maximum < 1e-12
                    if a['actual'][i] and d['available'][i] and admissible(
                            d['flags_by_row'][i], int(np.argmax(a['ps'][i])), int(d['regular'][i]), result['prediction']):
                        p[i] = result['prediction']
                results[name] = p; contexts[name] = a; reinduced += 1
                for file in ('model.cbm', 'native.json', 'metadata.json', 'receipt.json', 'rubric.json', 'rubric.txt'):
                    source_files[str(path/file)] = file_hash(path/file)
            if scope == 'balanced':
                # Frozen semantic-head arm is a diagnostic of teacher replacement,
                # distinct from the primary arm that retrains both layers.
                stored = CatBoostRegressor(); stored.load_model(str(RESIDUAL_STUDY/folder/'contextual_depth2.cbm'))
                from critical.core.calibration.semantic_residual_v103 import corrected_support
                proposed = np.argmax(corrected_support(a['ps'], stored.predict(a['full'][:, columns]), base_metadata['strength']), axis=1)
                p = a['current'].copy()
                for i in np.flatnonzero(a['actual'] & d['available']):
                    if admissible(d['flags_by_row'][i], int(np.argmax(a['ps'][i])), int(d['regular'][i]), int(proposed[i])):
                        p[i] = proposed[i]
                results['balanced_base_frozen_head'] = p; contexts['balanced_base_frozen_head'] = a
        for name, p in results.items():
            a = contexts[name]
            assert p.tolist() == read(study/'predictions_by_fold'/folder/(name+'.json'))
            if name not in ('balanced_base_raw', 'balanced_base'):
                assert np.array_equal(p[~(a['actual'] & d['available'])], a['current'][~(a['actual'] & d['available'])])
            assert np.array_equal(p[~d['valid']], d['regular'][~d['valid']])
            route = read(study/'routes_by_fold'/folder/(name+'.json'))
            assert route == {'review': a['actual'].tolist(), 'available': d['available'].tolist(),
                'locked': a['locked'].tolist(), 'covered': d['valid'].tolist(),
                'fit_cases': [examples[i]['case'] for i in a['fit']]}
            correct = int(np.sum(p[:99] == d['y'][:99]))
            slots = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in originals))
            retained_rows.append({'candidate': name, 'fold': f['fold'], 'original_correct': correct,
                                  'slots_correct': slots, 'eligible': correct == 99 and slots == 144})
            for i in a['held']:
                e = examples[i]
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                    'baseline': incumbent[e['case']]['prediction'], 'review': bool(a['actual'][i]),
                    'local_available': bool(a['actual'][i] and d['available'][i]),
                    'prior_rule_priority': bool(a['locked'][i])})
        print({'fold': f['fold'], 'reinduced_heads': reinduced, 'compared_arms': len(results)}, flush=True)
    assert sorted(rows, key=lambda r: (r['candidate'], r['case'])) == sorted(
        read(study/'predictions.json'), key=lambda r: (r['candidate'], r['case']))
    assert sorted(retained_rows, key=lambda r: (r['candidate'], r['fold'])) == sorted(
        read(study/'retention.json'), key=lambda r: (r['candidate'], r['fold']))
    checked_results = {}
    for name in protocol['arms']:
        rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == 276 and len({r['case'] for r in rr}) == 276
        checked_results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'changes': sum(r['prediction'] != r['baseline'] for r in rr),
            'upstream_coverage': sum(r['covered'] for r in rr), 'review_cases': sum(r['review'] for r in rr),
            'review_observation_available': sum(r['local_available'] for r in rr),
            'original_cases_and_slots_retained': all(r['eligible'] for r in retained_rows if r['candidate'] == name)}
    assert checked_results == read(study/'results.json')
    assert checked_results['current_control']['metrics']['correct'] == 227
    result = {'passed': True, 'primary_arm': protocol['primary_arm'], 'results': checked_results,
        'native_teachers_checked': len(teacher_receipts), 'exact_reused_teachers': reused_teachers,
        'native_teacher_rows': len(teacher_receipts)*len(examples),
        'reinduced_semantic_heads': reinduced, 'portable_residual_rows': reinduced*len(examples),
        'max_teacher_error': max(teacher_errors, default=0.), 'max_residual_error': max_residual_error,
        'all_evaluation_denominators': 276, 'upstream_coverage': 273,
        'new_api_calls': 0, 'new_observer_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
        'scope': 'Audited class-balanced development comparison. No serving artifact or untouched validation claim.'}
    save_json(out/'verification.json', result); save_json(out/'predictions.json', rows)
    save_json(out/'retention.json', retained_rows)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__),
        'producer_manifest_sha256': file_hash(study/'manifest.json'), 'source_files': source_files})
    (out/'run.log').write_text('Completed class-weight/source/denominator checks, native teacher replay, residual re-induction and portable named-term replay. No serving change.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy']) for k, v in checked_results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.study.resolve(), a.output_dir.resolve())
