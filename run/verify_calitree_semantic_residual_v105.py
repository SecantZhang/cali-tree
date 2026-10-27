"""Re-induce six semantic residuals, compile weighted clauses and replay inference."""
import argparse
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.semantic_residual_runtime_v104 import ResidualExecutor, SemanticResidualPolicy, export_policy, SUPPORT, admissible
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.calibration.independent_expert_v87 import IndependentExpertPolicy, record_from_job
from critical.core.optimization.prompt.calitree.semantic_residual_judge_v104 import SemanticResidualJudge
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.calitree_seeded_rubric_v73 import arrays, attach
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, VISION, data, read
from run.calitree_source_excluded_calibration_v89 import baseline_predictions, RUBRICS, EXPERT
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_cached_sol_router_v85 import cached
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy
from run.verify_calitree_local_review_cache_v98 import validate_response


def load(cache, cache_audit):
    verification = read(cache_audit/'verification.json'); audited = read(cache_audit/'manifest.json')
    assert verification['passed'] and verification['complete'] and not verification['snapshot_only']
    assert audited['cache_manifest_sha256'] == file_hash(cache/'manifest.json')
    for path, sha in audited['source_hashes'].items():
        assert file_hash(path) == sha, path
    examples, old_names, raw, semantic = arrays()
    y = np.asarray([e['reference'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); pos = {e['case']: i for i, e in enumerate(examples)}
    sol, provenance = cached(examples); profile = read(cache/'identity.json'); jobs = read(cache/'jobs.json')
    template = (cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text()
    extra_names = list(local.SPECS); names = old_names+extra_names+list(SUPPORT)
    extra = np.zeros((len(examples), len(extra_names))); available = np.zeros(len(examples), dtype=bool); local_records = {}; flags_by_row = {}
    for job in jobs:
        response = read(cache/'responses'/(job['case']+'.json')); passed = validate_response(job, response, profile)
        local_records[job['case']] = response['record']
        if passed:
            flags = local.project(job['program'], job['image_pair_ref'], digest(profile), job['prompt_ref'], response['record'])
            i = pos[job['case']]; extra[i] = [int(flags[n]) for n in extra_names]; available[i] = True; flags_by_row[i] = flags
    return locals()


def fold_arrays(d, f):
    folder = 'fold'+str(f['fold']); examples = d['examples']; groups = d['groups']; regular = d['regular']; valid = d['valid']
    train = [d['pos'][c] for c in f['train_cases']]; held = [d['pos'][c] for c in f['held_cases']]
    assert not set(groups[train]) & set(groups[held])
    ps = np.asarray(read(TEACHERS/folder/'predictions.json')['support'])
    current, locked = baseline_predictions(folder, d['old_names'], d['raw'], d['semantic'], ps, regular, d['sol'], valid)
    actual = valid & ~locked & (ps.max(axis=1) < .8)
    inner = [(read(INNER/folder/('inner'+str(k))/'membership.json'), read(INNER/folder/('inner'+str(k))/'predictions.json')['support']) for k in range(5)]
    oof, genuine = source_excluded_views(ps, train, held, groups, inner); fitting = valid & genuine & (oof.max(axis=1) < .8)
    membership = next(m for m in read(d['cache']/'memberships.json') if m['fold'] == f['fold'])
    assert membership['actual_review_cases'] == [examples[i]['case'] for i in np.flatnonzero(actual)]
    assert membership['fit_review_cases'] == [examples[i]['case'] for i in np.flatnonzero(fitting)]
    fit = np.flatnonzero(fitting & d['available']).tolist(); protected = [i for i in range(99) if actual[i] and d['available'][i]]
    assert set(fit) <= set(train) and not set(groups[fit]) & set(groups[held])
    matrices = []
    for probabilities, mask in ((ps, actual), (oof, fitting)):
        local_matrix = d['extra']*mask[:, None]; context = np.argmax(probabilities, axis=1)
        for i in np.flatnonzero(mask & d['available']):
            for key, value in local.view_flags(d['flags_by_row'][i], int(context[i]), int(regular[i])).items():
                local_matrix[i, d['extra_names'].index(key)] = int(value)
        matrices.append(np.concatenate([attach(d['raw'], d['semantic'], probabilities, regular), local_matrix, probabilities], axis=1))
    full, T = matrices
    return locals()


def audit(cache, cache_audit, study, out, candidate='contextual_depth2_guarded'):
    if out.exists() or not candidate.endswith('_guarded'):
        raise ValueError('Fresh guarded-policy audit required')
    d = load(cache, cache_audit); producer = read(study/'manifest.json'); protocol = read(study/'protocol.json')
    assert protocol['method'] == 'tree_residual' and producer['targets_ref'] == digest(d['y'].tolist())
    assert producer['protocol_ref'] == digest(protocol) and producer['cache_audit_manifest_sha256'] == file_hash(cache_audit/'manifest.json')
    for path, sha in producer['code_sha256'].items():
        assert file_hash(path) == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    examples, names, y = d['examples'], d['names'], d['y']; base_name = candidate.removesuffix('_guarded')
    saved = {r['case']: r for r in read(study/'predictions.json') if r['candidate'] == candidate}; assert len(saved) == 276
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Strict cache accepted; native re-induction, portable clauses and bound runtime replay started.\n')
    (out/'llm-histories.log').write_text('Zero API, observer, encoder or reserved-source calls. Cached evidence and offline fits only.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py', ROOT/'critical/core/optimization/prompt/calitree/semantic_residual_judge_v104.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    rows = []; retention = []; max_delta_error = 0.
    from catboost import CatBoostRegressor
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a = fold_arrays(d, f); folder = a['folder']; metadata = read(study/folder/(base_name+'.json')); native = read(study/folder/(base_name+'-native.json'))
        columns = [names.index(n) for n in metadata['features']]; fit = a['fit']; protected = a['protected']
        assert metadata['teacher_ref'] == digest(read(TEACHERS/folder/'teacher.json')['contract'])
        assert metadata['fit_cases'] == [examples[i]['case'] for i in fit] and metadata['protected_review_cases'] == [examples[i]['case'] for i in protected]
        assert metadata['observer_identity_ref'] == digest(d['profile'])
        model = SemanticResidual(metadata['features'], depth=metadata['depth'], iterations=metadata['iterations']).fit(a['T'][fit][:, columns], y[fit],
            support=a['oof'][fit], groups=d['groups'][fit], protected_X=a['full'][protected][:, columns], protected_y=y[protected], protected_support=a['ps'][protected])
        assert model.artifact({**local.DESCRIPTIONS, **SUPPORT}) == {k: v for k, v in metadata.items() if k not in ('teacher_ref', 'observer_identity_ref', 'fit_cases', 'protected_review_cases')}
        (out/folder).mkdir(exist_ok=True); model.model.save_model(str(out/folder/'reinduced-native.json'), format='json')
        reinduced = read(out/folder/'reinduced-native.json')
        for key in ('features_info', 'oblivious_trees', 'scale_and_bias'):
            assert reinduced[key] == native[key], (folder, key)
        stored_model = CatBoostRegressor(); stored_model.load_model(str(study/folder/(base_name+'.cbm')))
        native_delta = np.asarray(stored_model.predict(a['full'][:, columns])); assert np.allclose(native_delta, model.model.predict(a['full'][:, columns]), atol=1e-12, rtol=0)
        from critical.core.calibration.semantic_residual_runtime_v104 import compile_residual
        artifact = compile_residual(native, metadata); executor = ResidualExecutor(artifact); p = a['current'].copy()
        for i in range(len(examples)):
            values = {n: (float(a['full'][i, j]) if n in SUPPORT else bool(a['full'][i, j])) for j, n in enumerate(names)}
            result = executor.evaluate(values, a['ps'][i].tolist())
            error = float(np.max(np.abs(np.asarray(result['residual'])-native_delta[i]))); max_delta_error = max(max_delta_error, error); assert error < 1e-12
            if a['actual'][i] and d['available'][i] and admissible(values, int(np.argmax(a['ps'][i])), int(d['regular'][i]), result['prediction']):
                p[i] = result['prediction']
        assert p.tolist() == read(study/folder/(candidate+'-predictions.json'))
        assert np.all(p[:99] == y[:99]) and np.array_equal(p[~(a['actual'] & d['available'])], a['current'][~(a['actual'] & d['available'])])
        slots = sum(p[d['pos'][r['case']]] == r['reference'] for r in originals); assert slots == 144
        retention.append({'fold': f['fold'], 'original_correct': 99, 'slots_correct': int(slots), 'clauses': len(artifact['clauses']), 'fit_rows': len(fit), 'strength': model.strength})
        for i in a['held']:
            r = saved[examples[i]['case']]
            assert all(r[k] == examples[i][k] for k in ('case', 'source_group', 'reference', 'regular', 'covered'))
            assert r['prediction'] == int(p[i]) and r['baseline'] == int(a['current'][i]) and r['fold'] == f['fold']
            rows.append(r)
        save_json(out/folder/'rubric.json', artifact)
        if f['fold'] == 5:
            final_native, final_metadata, final_predictions, final_support, final_review = native, metadata, p, a['ps'], a['actual']
        print({'fold': f['fold'], 'native_reinduced': True, 'weighted_clauses': len(artifact['clauses']), 'original_slots': int(slots)}, flush=True)
    same, teacher_names, X = data(); assert same == examples
    teacher = VisualSemanticPolicy(read(FROZEN/'policy.json'))
    for i in range(len(examples)):
        measured = teacher.probabilities({n: bool(X[i, teacher_names.index(n)]) for n in teacher.artifact['feature_names']})
        assert np.allclose(measured, final_support[i], atol=1e-12, rtol=0)
    previous = SemanticRubricPolicy(teacher, read(RUBRICS/'rubric.json')); base_policy = IndependentExpertPolicy(previous, read(EXPERT/'policy.json'))
    checkpoint = read(ROOT/'logs/exps/261023-local-vlm-download-v94-r1/identity.json')
    exported = export_policy(base_policy, final_native, final_metadata, d['profile'], d['template'], checkpoint); policy = SemanticResidualPolicy(base_policy, exported)
    def forbidden(*args, **kwargs):
        raise AssertionError('Cached runtime cannot call a model or encoder')
    judge = SemanticResidualJudge(None, policy, SimpleNamespace(compute=forbidden))
    original_raw = read(FROZEN/'replay_inputs_without_references.json'); by_case = {r['case']: r for r in d['provenance']}; hashes = read(VISION/'manifest.json')['image_hashes']; runtime = []
    for i, r in enumerate(original_raw):
        pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']], hashes[r['evidence']['edited_image']]])
        expert_record = None
        if r['case'] in by_case:
            slot = by_case[r['case']]['selected_slot']; contract = base_policy.artifact['expert_contract']
            expert_record = record_from_job(r['program'], pair, slot['identity'], read(slot['job']), contract['schema'], contract['template'])
        vision_record = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF, 'program_ref': r['program']['program_ref'],
                         'image_pair_ref': pair, 'encoder_spec_ref': digest(teacher.artifact['encoder_spec']), 'measurements': read(VISION/'cases'/(r['case']+'.json'))['measurements']}
        result = judge.judge(r['program']['instruction'], r['evidence'], program=r['program'], observation=r['observation'], interpretation=r['interpretation'],
                    regular_judgment=r['judgment'], vision_record=vision_record, expert_record=expert_record, local_record=d['local_records'].get(r['case']))
        prediction = local.LABELS.index(result['judgment']['label']) if result['judgment']['label'] != 'unresolved' else -1
        route = result['route']; assert prediction == final_predictions[i] and route['covered'] == bool(d['valid'][i]), r['case']
        assert 'local_review_error' not in route, r['case']
        prior = route['base_route'] if route.get('reason') == 'semantic_residual_override' else route
        assert policy.review_route(prior) == bool(final_review[i]), r['case']
        if route.get('reason') == 'semantic_residual_override':
            assert 'class_support' not in route and 'base_route' in route and result['source'] == 'guarded_weighted_semantic_rubric'
        runtime.append({'case': r['case'], 'prediction': prediction, 'covered': route['covered'], 'source': result['source']})
    result = {'passed': True, 'candidate': candidate, 'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
        'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
        'coverage': sum(r['covered'] for r in rows), 'original_cases_per_fit': 99, 'original_slots_per_fit': 144,
        'reinduced_models': 6, 'portable_residual_rows': 6*len(examples), 'max_residual_error': max_delta_error,
        'portable_teacher_support_replays': len(examples), 'high_level_runtime_replays': len(runtime), 'native_cache_audit_models': d['verification']['native_models_checked'],
        'new_api_calls': 0, 'new_local_observer_calls': 0, 'reserved_sources_used': 0, 'serving_defaults_changed': False,
        'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235,
        'scope': 'Reviewed276-case source-held development comparison, including15 available older Sol views. Not untouched validation.'}
    declared = read(study/'results.json')[candidate]
    assert result['accuracy'] == declared['accuracy'] and result['gains'] == declared['gains'] and result['losses'] == declared['losses']
    assert result['baseline']['correct'] == 225 and result['coverage'] == 273
    save_json(out/'verification.json', result); save_json(out/'policy.json', exported); save_json(out/'predictions.json', rows)
    save_json(out/'retention.json', retention); save_json(out/'runtime_predictions.json', runtime); (out/'rubric.txt').write_text(exported['rubric']['rubric'])
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'cache_audit_manifest_sha256': file_hash(cache_audit/'manifest.json'),
        'study_manifest_sha256': file_hash(study/'manifest.json'), 'policy_ref': exported['artifact_ref'], 'code_sha256': {str(p): file_hash(p) for p in sources}})
    (out/'run.log').write_text('Six native models re-induced;5490 clause/native residuals and915 bound judgments match. No serving defaults changed.\n')
    print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--cache-audit', type=Path, required=True)
    p.add_argument('--study', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--candidate', default='contextual_depth2_guarded')
    a = p.parse_args(); audit(a.cache.resolve(), a.cache_audit.resolve(), a.study.resolve(), a.output_dir.resolve(), a.candidate)
