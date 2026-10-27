"""Compile equivalent boosted factors and audit scores plus V112/V144 routes."""
import argparse
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor

from critical.core.calibration.boosted_factor_merge_v175 import compile_factors, FactorExecutor
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_residual_v103 import corrected_support
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, admissible
from critical.core.calibration.balanced_semantic_patches_v144 import execute as patch_execute
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.calibration.independent_expert_v87 import record_from_job
from critical.core.optimization.prompt.calitree import CaliTreeJudge
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.calitree_single_tree_v173 import inputs, ROOT, STUDY, FROZEN, V112, V144, PATCH, SELECTION
from run.calitree_compact_balance_v143 import CACHE, CACHE_AUDIT
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_seeded_rubric_v73 import attach
from run.calitree_source_excluded_calibration_v89 import baseline_predictions
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_semantic_rubric_v70 import VISION, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from critical.core.calibration import local_warranted_rubric_v97 as local


def compact_bytes(value):
    return len(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def classifier_from_native(native):
    mapping = {r['feature_index']: r['flat_feature_index'] for r in native['features_info']['float_features']}
    trees = []
    for tree in native['oblivious_trees']:
        features = []
        for split in tree.get('splits') or []:
            assert split['split_type'] == 'FloatFeature' and split['border'] == .5
            features.append(mapping[split['float_feature_index']])
        trees.append({'features': features, 'values': tree['leaf_values']})
    scale, bias = native['scale_and_bias']
    return {'scale': scale, 'bias': bias, 'trees': trees}


def prove_tables(classifier, artifact):
    """Independent exhaustive coordinate check for every merged factor."""
    checked = 0
    assert artifact['source_classifier_ref'] == digest(classifier)
    assert artifact['scale'] == classifier['scale'] and artifact['bias'] == classifier['bias']
    seen = []
    for factor in artifact['factors']:
        positions = {feature: i for i, feature in enumerate(factor['features'])}
        for leaf in range(1 << len(positions)):
            contributions = []
            for index in factor['source_trees']:
                tree = classifier['trees'][index]
                assert set(tree['features']) == set(positions)
                old_leaf = sum(((leaf >> positions[j]) & 1) << bit for bit, j in enumerate(tree['features']))
                contributions.append(tree['values'][3*old_leaf:3*old_leaf+3])
            expected = [math.fsum(v[c] for v in contributions) for c in range(3)]
            assert expected == factor['nonzero_leaves'].get(str(leaf), [0., 0., 0.])
            checked += 1
        seen.extend(factor['source_trees'])
    assert sorted(seen) == list(range(len(classifier['trees'])))
    return checked


def check_routes(d, f, ps, native_matrix, slots):
    a = fold_arrays(d, f); folder = a['folder']; before_ps = a['ps']
    assert np.allclose(ps, before_ps, atol=1e-12, rtol=0)
    current, locked = baseline_predictions(folder, d['old_names'], d['raw'], d['semantic'], ps, d['regular'], d['sol'], d['valid'])
    assert np.array_equal(current, a['current']) and np.array_equal(locked, a['locked'])
    review = d['valid'] & ~locked & (ps.max(axis=1) < .8)
    assert np.array_equal(review, a['actual'])
    local_matrix = d['extra']*review[:, None]; context = np.argmax(ps, axis=1)
    for i in np.flatnonzero(review & d['available']):
        for key, value in local.view_flags(d['flags_by_row'][i], int(context[i]), int(d['regular'][i])).items():
            local_matrix[i, d['extra_names'].index(key)] = int(value)
    matrix = np.concatenate([attach(d['raw'], d['semantic'], ps, d['regular']), local_matrix, ps], axis=1)
    numeric = [d['names'].index(n) for n in SUPPORT]
    boolean = [j for j in range(len(d['names'])) if j not in numeric]
    assert np.array_equal(matrix[:, boolean], a['full'][:, boolean])
    metadata = read(V112/folder/'contextual_depth2.json'); columns = [d['names'].index(n) for n in metadata['features']]
    model = CatBoostRegressor(); model.load_model(str(V112/folder/'contextual_depth2.cbm'))
    delta = model.predict(matrix[:, columns]); old_delta = model.predict(a['full'][:, columns])
    assert np.array_equal(delta, old_delta)
    supports = corrected_support(ps, delta, metadata['strength']); proposed = np.argmax(supports, axis=1)
    prediction = current.copy(); final_locked = locked.copy() | ~d['valid']
    for i in np.flatnonzero(review & d['available']):
        values = {n: float(matrix[i, j]) if n in SUPPORT else bool(matrix[i, j]) for j, n in enumerate(d['names'])}
        if proposed[i] != current[i] and admissible(values, int(context[i]), int(d['regular'][i]), int(proposed[i])):
            prediction[i] = proposed[i]; final_locked[i] = True
    assert prediction.tolist() == read(V112/folder/'contextual_depth2_guarded-predictions.json')
    artifact = read(V144/folder/(PATCH+'.json')); patched = prediction.copy()
    for i in range(len(prediction)):
        values = {n: bool(matrix[i, d['names'].index(n)]) for n in artifact['feature_names']}
        patched[i] = patch_execute(artifact, values, int(prediction[i]), bool(~final_locked[i]))
    assert patched.tolist() == read(V144/folder/(PATCH+'-predictions.json'))
    for p in (prediction, patched):
        assert np.all(p[:99] == d['y'][:99])
        assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
    rows = [{**d['examples'][i], 'fold': f['fold'], 'v112': int(prediction[i]), 'v144': int(patched[i])} for i in a['held']]
    return rows, {'rows': len(prediction), 'boolean_context_values': len(prediction)*len(boolean),
                  'v112_predictions_retained': True, 'v144_predictions_retained': True, 'review_mask_retained': True}


def bound_replay(artifact, d):
    """Inject only the compact scorer for verification, retaining parent identities.

    This is an executor substitution test, not deployment of a new selector or
    a claim that the existing default manifest loads the new artifact format.
    """
    def forbidden(*args, **kwargs): raise AssertionError('No fresh model/encoder calls')
    baseline = CaliTreeJudge(encoder=SimpleNamespace(compute=forbidden))
    merged = CaliTreeJudge(encoder=SimpleNamespace(compute=forbidden))
    teacher = merged.policy.base.base.teacher
    assert artifact['source_classifier_ref'] == digest(teacher.artifact['classifier'])
    teacher.probabilities = FactorExecutor(artifact).probabilities
    hashes = read(VISION/'manifest.json')['image_hashes']
    provenance = {r['case']: r for r in read(ROOT/'logs/exps/261023-cached-sol-router-v85-r3/expert_provenance.json')}
    rows, max_float_difference = [], 0.
    def equal_routes(a, b):
        nonlocal max_float_difference
        if isinstance(a, float):
            assert isinstance(b, (float, int)) and abs(a-b) <= 1e-12
            max_float_difference = max(max_float_difference, abs(a-b))
        elif isinstance(a, dict):
            assert isinstance(b, dict) and set(a) == set(b)
            for k in a: equal_routes(a[k], b[k])
        elif isinstance(a, list):
            assert isinstance(b, list) and len(a) == len(b)
            for x, y in zip(a, b): equal_routes(x, y)
        else: assert a == b
    for r in read(FROZEN/'replay_inputs_without_references.json'):
        case = r['case']; pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']], hashes[r['evidence']['edited_image']]])
        expert = None
        if case in provenance:
            slot = provenance[case]['selected_slot']; contract = baseline.policy.base.artifact['expert_contract']
            expert = record_from_job(r['program'], pair, slot['identity'], read(slot['job']), contract['schema'], contract['template'])
        measured = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
            'program_ref': r['program']['program_ref'], 'image_pair_ref': pair,
            'encoder_spec_ref': digest(baseline.policy.artifact['encoder_spec']), 'measurements': read(VISION/'cases'/(case+'.json'))['measurements']}
        request = {'program': r['program'], 'observation': r['observation'], 'interpretation': r['interpretation'],
            'regular_judgment': r['judgment'], 'vision_record': measured, 'expert_record': expert,
            'local_record': d['local_records'].get(case)}
        a = baseline.judge(r['program']['instruction'], r['evidence'], **request)
        b = merged.judge(r['program']['instruction'], r['evidence'], **request)
        for field in ('judgment', 'source', 'regular_execution_ref', 'regular_error', 'extraction_error'):
            assert a[field] == b[field], (case, field)
        equal_routes(a['route'], b['route'])
        rows.append({'case': case, 'label': b['judgment']['label'], 'covered': b['route']['covered'], 'source': b['source']})
    return rows, max_float_difference


def run(out):
    if out.exists(): raise ValueError('Fresh merge/audit directory required')
    out.mkdir(parents=True)
    protocol = {'version': 'boosted-semantic-factor-sharing-v176',
        'merge': 'Group identical semantic predicate sets, align branch coordinates, sum score vectors with fsum, omit exact-zero leaves. No semantic broadening or label-based selection.',
        'proof': 'Exhaustive Boolean assignments within every shared factor, all original tree memberships exactly once, native/canonical classifier source binding.',
        'replay': 'Six source-fold/full models on915 cases; recompute V112/V144 contexts, guarded decisions, coverage and protected99/144; full high-level915 bound requests with scorer-only substitution.',
        'numeric': 'Exact in real arithmetic; float aggregation order changes. Require max class-support/route float difference1e-12 and identical recorded predictions and routing.',
        'new_api_calls': 0, 'new_model_fits': 0, 'new_encoder_or_observer_calls': 0, 'reserved_sources_used': 0, 'default_changed': False}
    save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Equivalent semantic factor merging and independent exhaustive table proof started.\n')
    (out/'llm-histories.log').write_text('Zero API, encoder, observer or fitting calls. Frozen model compilation/replay only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/boosted_factor_merge_v175.py']
    hashes = {str(p): file_hash(p) for p in files}; selection_before = file_hash(SELECTION)
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    examples, names, X, y, valid, regular, groups, pos, folds, descriptions = inputs(); d = load(CACHE, CACHE_AUDIT)
    assert examples == d['examples']
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    reports, rows, scalar_max, coordinate_proofs, score_rows, contexts = [], [], 0., 0, 0, 0
    for f in folds:
        folder = 'fold'+str(f['fold']); directory = out/folder; directory.mkdir()
        model = CatBoostClassifier(); model.load_model(str(TEACHERS/folder/'teacher.cbm'))
        model.save_model(str(directory/'native.json'), format='json')
        classifier = classifier_from_native(read(directory/'native.json'))
        nn = f['selected_features']; cc = [names.index(n) for n in nn]
        artifact = compile_factors(classifier, nn, descriptions); runtime = FactorExecutor(artifact)
        coordinate_proofs += prove_tables(classifier, artifact)
        ps = runtime.predict_matrix(X[:, cc]); native = np.asarray(read(TEACHERS/folder/'predictions.json')['support'])
        assert np.allclose(ps, native, atol=1e-12, rtol=0) and np.array_equal(np.argmax(ps, axis=1), np.argmax(native, axis=1))
        fake = SimpleNamespace(artifact={'feature_names': nn, 'classifier': classifier})
        for i in range(len(X)):
            values = {n: bool(X[i, j]) for n, j in zip(nn, cc)}
            before = VisualSemanticPolicy.probabilities(fake, values); after = runtime.probabilities(values)
            scalar_max = max(scalar_max, max(abs(x-z) for x, z in zip(before, after)))
            assert np.allclose(after, ps[i], atol=1e-12, rtol=0)
        score_rows += len(X)
        saved, context_report = check_routes(d, f, ps, X, slots); rows.extend(saved); contexts += context_report['boolean_context_values']
        baseline_size = compact_bytes({'feature_names': nn, 'descriptions': artifact['descriptions'], 'classifier': classifier})
        report = {'fold': f['fold'], 'source_trees': len(classifier['trees']), 'shared_factors': len(artifact['factors']),
            'source_condition_occurrences': sum(len(t['features']) for t in classifier['trees']),
            'shared_condition_occurrences': sum(len(t['features']) for t in artifact['factors']),
            'source_score_scalars': sum(len(t['values']) for t in classifier['trees']),
            'shared_score_scalars': sum(3*len(t['nonzero_leaves']) for t in artifact['factors']),
            'baseline_scoring_bytes': baseline_size, 'merged_scoring_bytes': compact_bytes(artifact),
            'max_support_error': float(np.max(np.abs(ps-native))), **context_report}
        reports.append(report); save_json(directory/'merged.json', artifact); save_json(directory/'compression.json', report)
        save_json(out/'compression.json', reports)
        if f['fold'] == 5:
            assert artifact['source_classifier_ref'] == digest(read(FROZEN/'policy.json')['classifier'])
            final = artifact
        print(report, flush=True)
    assert scalar_max <= 1e-12 and len(rows) == 276
    metrics = {version: classification_metrics(rows, version) for version in ('v112', 'v144')}
    assert metrics['v112']['correct'] == 227 and metrics['v144']['correct'] == 226
    bound, float_difference = bound_replay(final, d)
    assert len(bound) == 915 and sum(r['covered'] for r in rows) == 273
    assert all(file_hash(p) == sha for p, sha in hashes.items()) and file_hash(SELECTION) == selection_before
    report = {'passed': True, 'compiled_models': len(reports), 'exhaustive_factor_assignments': coordinate_proofs,
        'scalar_native_rows': score_rows, 'max_scalar_support_error': scalar_max,
        'boolean_context_values_retained': contexts, 'v112_v144_predictions_checked': 2*score_rows,
        'high_level_bound_requests': len(bound), 'max_route_float_difference': float_difference,
        'coverage': 273, 'original_cases_per_fit': 99, 'local_slots_per_fit': 144, 'metrics': metrics,
        'new_api_calls': 0, 'new_model_fits': 0, 'new_encoder_or_observer_calls': 0,
        'reserved_sources_used': 0, 'default_changed': False,
        'semantic_limit': 'Exact named-predicate structure sharing. No abstracted rubric, merged dissimilar conditions or improved generalization claim.',
        'runtime_limit': 'Compact scorer is executable. Full pipeline is tested by scorer-only substitution; selected artifact loader remains unchanged.'}
    save_json(out/'verification.json', report); save_json(out/'bound_predictions.json', bound); save_json(out/'predictions.json', rows)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': hashes, 'selection_sha256': selection_before,
        'final_factor_ref': final['artifact_ref'], 'folds_sha256': file_hash(STUDY/'folds.json'), 'input_matrix_ref': digest(X.tolist())})
    (out/'run.log').write_text('Completed six compiled models, exhaustive factor proofs, all915 scalar cases per fold and full915 bound requests. V112/V144 predictions and routing preserved within float tolerance. Default unchanged.\n')
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
