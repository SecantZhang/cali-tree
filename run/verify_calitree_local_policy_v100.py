"""Re-induce a selected local rubric and replay the real bound inference path."""
import argparse
from pathlib import Path
from types import SimpleNamespace
from dataclasses import asdict

import numpy as np

from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.calibration.seeded_rubric_v73 import Search
from critical.core.calibration.local_semantic_runtime_v99 import LocalRuleExecutor, LocalSemanticPolicy, export_policy
from critical.core.calibration.source_excluded_calibration_v89 import source_excluded_views
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.calibration.independent_expert_v87 import IndependentExpertPolicy, record_from_job
from critical.core.optimization.prompt.calitree.local_semantic_judge_v99 import LocalSemanticJudge
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


def audit(cache, study, cache_audit, out, candidate=None):
    if out.exists():
        raise ValueError('Fresh policy audit directory required')
    verification = read(cache_audit/'verification.json'); audited = read(cache_audit/'manifest.json')
    assert verification['passed'] and verification['complete'] and not verification['snapshot_only']
    assert audited['cache_manifest_sha256'] == file_hash(cache/'manifest.json')
    for path, sha in audited['source_hashes'].items():
        assert file_hash(path) == sha
    producer = read(study/'manifest.json'); candidate = candidate or read(study/'selection.json')['candidate']
    for path, sha in producer['code_sha256'].items():
        assert file_hash(path) == file_hash(study/'source_snapshot'/Path(path).relative_to(ROOT)) == sha
    assert producer['cache_manifest_sha256'] == file_hash(cache/'manifest.json') and producer['cache_result_sha256'] == file_hash(cache/'results.json')
    examples, old_names, raw, semantic = arrays(); same, teacher_names, X = data(); assert examples == same
    y = np.asarray([e['reference'] for e in examples]); groups = np.asarray([e['source_group'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples]); valid = np.asarray([e['covered'] for e in examples]); pos = {e['case']: i for i, e in enumerate(examples)}
    assert digest(y.tolist()) == producer['targets_ref']
    sol, provenance = cached(examples); manifest = read(cache/'manifest.json'); profile = read(cache/'identity.json')
    jobs = read(cache/'jobs.json'); membership = read(cache/'memberships.json')
    template = (cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text()
    extra_names = list(local.SPECS); names = old_names+extra_names
    extra = np.zeros((len(examples), len(extra_names)), dtype=np.float32); available = np.zeros(len(examples), dtype=bool); local_records = {}
    for job in jobs:
        response = read(cache/'responses'/(job['case']+'.json')); passed = validate_response(job, response, profile)
        local_records[job['case']] = response['record']
        if passed:
            flags = local.project(job['program'], job['image_pair_ref'], manifest['identity_ref'], job['prompt_ref'], response['record'])
            i = pos[job['case']]; extra[i] = [int(flags[n]) for n in extra_names]; available[i] = True
    saved_rows = {r['case']: r for r in read(study/'predictions.json') if r['candidate'] == candidate}
    assert len(saved_rows) == 276
    originals = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Source-bound local-policy re-induction and high-level runtime audit started.\n')
    (out/'llm-histories.log').write_text('Zero API or local-observer calls. Source audited native caches, rule re-induction and cached bound inference only.\n')
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True); snapshot.write_bytes(Path(__file__).read_bytes())
    rows = []; retention = []; final = final_predictions = final_support = final_review = None
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        folder = 'fold'+str(f['fold']); train = [pos[c] for c in f['train_cases']]; held = [pos[c] for c in f['held_cases']]
        assert not set(groups[train]) & set(groups[held])
        metadata = read(TEACHERS/folder/'teacher.json')['contract']; ps = np.asarray(read(TEACHERS/folder/'predictions.json')['support'])
        assert metadata['rows'] == train
        current, locked = baseline_predictions(folder, old_names, raw, semantic, ps, regular, sol, valid)
        actual = valid & ~locked & (ps.max(axis=1) < .8)
        inner = [(read(INNER/folder/('inner'+str(k))/'membership.json'), read(INNER/folder/('inner'+str(k))/'predictions.json')['support']) for k in range(5)]
        oof, genuine = source_excluded_views(ps, train, held, groups, inner)
        fit_mask = valid & genuine & (oof.max(axis=1) < .8); fit = np.flatnonzero(fit_mask).tolist()
        expected = next(m for m in membership if m['fold'] == f['fold'])
        assert expected['actual_review_cases'] == [examples[i]['case'] for i in np.flatnonzero(actual)]
        assert expected['fit_review_cases'] == [examples[i]['case'] for i in fit]
        assert set(fit) <= set(train) and not set(groups[fit]) & set(groups[held])
        base = np.argmax(ps, axis=1); base[~valid] = regular[~valid]
        oof_base = np.argmax(oof, axis=1); oof_base[~valid] = regular[~valid]
        augmented = []
        for probabilities, mask, context in ((ps, actual, base), (oof, fit_mask, oof_base)):
            local_matrix = extra*mask[:, None]
            for i in np.flatnonzero(mask & available):
                views = local.view_flags({n: bool(extra[i, j]) for j, n in enumerate(extra_names)}, int(context[i]), int(regular[i]))
                for key, value in views.items():
                    local_matrix[i, extra_names.index(key)] = int(value)
            augmented.append(np.concatenate([attach(raw, semantic, probabilities, regular), local_matrix], axis=1))
        full, fitting = augmented; stored = read(study/folder/(candidate+'.json')); config = Search(**stored['config'])
        assert asdict(config) in read(study/'protocol.json')['configs']
        priority = {n: (5000. if n in ('local_no_ready', 'local_partial_ready', 'local_yes_ready') else 2500. if n in local.SPECS else 1000. if n.startswith('meaning_') else 0.) for n in names}
        model = local.LocalWarrantedRubric(names, config).fit(fitting[fit], y[fit], groups=groups[fit].tolist(), base=oof_base[fit], regular=regular[fit],
                protected_X=full[:99], protected_y=y[:99], protected_base=base[:99], protected_regular=regular[:99], priority=priority)
        reconstructed = {k: v for k, v in model.artifact(digest(metadata)).items() if k != 'artifact_ref'}
        reconstructed.update(review_threshold=.8, observer_identity_ref=manifest['identity_ref'], local_fact_contract_ref=local.CONTRACT_REF,
                             observer_template_ref=digest(template), prior_rules_keep_original_context=True, fit_cases=[examples[i]['case'] for i in fit])
        reconstructed['artifact_ref'] = digest(reconstructed); assert reconstructed == stored
        executor = LocalRuleExecutor(stored); predictions = current.copy()
        for i in np.flatnonzero(actual & available):
            result = executor.select({n: bool(full[i, names.index(n)]) for n in stored['feature_names']}, int(base[i]), int(regular[i]))
            if result is not None:
                predictions[i] = result['prediction']
        assert predictions.tolist() == read(study/folder/'all_predictions.json')[candidate]
        assert np.all(predictions[:99] == y[:99]) and np.array_equal(predictions[~actual], current[~actual])
        slots = int(sum(predictions[pos[r['case']]] == r['reference'] for r in originals)); assert slots == 144
        retention.append({'fold': f['fold'], 'original_correct': 99, 'slots_correct': slots, 'rules': len(stored['rules']), 'fit_rows': len(fit)})
        for i in held:
            r = saved_rows[examples[i]['case']]
            assert all(r[k] == examples[i][k] for k in ('case', 'source_group', 'reference', 'regular', 'covered'))
            assert r['prediction'] == int(predictions[i]) and r['baseline'] == int(current[i]) and r['fold'] == f['fold']
            rows.append(r)
        save_json(out/folder/'rubric.json', stored)
        if f['fold'] == 5:
            final, final_predictions, final_support, final_review = stored, predictions, ps, actual
        print({'fold': f['fold'], 'reinduced_rules': len(stored['rules']), 'original_slots': slots}, flush=True)
    teacher = VisualSemanticPolicy(read(FROZEN/'policy.json'))
    for i in range(len(examples)):
        measured = teacher.probabilities({n: bool(X[i, teacher_names.index(n)]) for n in teacher.artifact['feature_names']})
        assert np.allclose(measured, final_support[i], atol=1e-12, rtol=0)
    previous = SemanticRubricPolicy(teacher, read(RUBRICS/'rubric.json')); base_policy = IndependentExpertPolicy(previous, read(EXPERT/'policy.json'))
    checkpoint = read(ROOT/'logs/exps/261023-local-vlm-download-v94-r1/identity.json')
    artifact = export_policy(base_policy, final, profile, template, checkpoint); policy = LocalSemanticPolicy(base_policy, artifact)
    def forbidden(*args, **kwargs):
        raise AssertionError('Cached bound replay must not make observer/encoder/model calls')
    judge = LocalSemanticJudge(None, policy, SimpleNamespace(compute=forbidden))
    original_raw = read(FROZEN/'replay_inputs_without_references.json'); by_case = {r['case']: r for r in provenance}; hashes = read(VISION/'manifest.json')['image_hashes']; runtime = []
    for i, r in enumerate(original_raw):
        pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']], hashes[r['evidence']['edited_image']]])
        expert_record = None
        if r['case'] in by_case:
            slot = by_case[r['case']]['selected_slot']; contract = base_policy.artifact['expert_contract']
            expert_record = record_from_job(r['program'], pair, slot['identity'], read(slot['job']), contract['schema'], contract['template'])
        measured = read(VISION/'cases'/(r['case']+'.json'))['measurements']
        vision_record = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF, 'program_ref': r['program']['program_ref'],
                         'image_pair_ref': pair, 'encoder_spec_ref': digest(teacher.artifact['encoder_spec']), 'measurements': measured}
        result = judge.judge(r['program']['instruction'], r['evidence'], program=r['program'], observation=r['observation'], interpretation=r['interpretation'],
                    regular_judgment=r['judgment'], vision_record=vision_record, expert_record=expert_record, local_record=local_records.get(r['case']))
        prediction = ('no', 'partial', 'yes').index(result['judgment']['label']) if result['judgment']['label'] != 'unresolved' else -1
        assert prediction == final_predictions[i] and result['route']['covered'] == bool(valid[i]), r['case']
        assert 'local_review_error' not in result['route'], r['case']
        previous_route = result['route']['base_route'] if result['route'].get('reason') == 'local_semantic_review_override' else result['route']
        assert policy.review_route(previous_route) == bool(final_review[i]), r['case']
        if result['route'].get('local_rule'):
            assert 'class_support' not in result['route'] and 'base_route' in result['route']
        runtime.append({'case': r['case'], 'prediction': prediction, 'covered': result['route']['covered'], 'source': result['source']})
    result = {'passed': True, 'candidate': candidate, 'accuracy': accuracy(rows, 'prediction'), 'baseline': accuracy(rows, 'baseline'),
        'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rows), 'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rows),
        'coverage': sum(r['covered'] for r in rows), 'original_cases_per_fit': 99, 'original_slots_per_fit': 144,
        'reinduced_folds': 6, 'portable_teacher_support_replays': len(examples), 'high_level_runtime_replays': len(runtime),
        'native_cache_audit_models': verification['native_models_checked'], 'new_api_calls': 0, 'new_local_observer_calls': 0,
        'reserved_sources_used': 0, 'serving_defaults_changed': False,
        'target_exceeded': accuracy(rows, 'prediction')['correct'] >= 235,
        'scope': 'Reviewed276-case source-held development comparison with the existing optional cached expert; not untouched validation.'}
    assert result['baseline']['correct'] == 225 and result['coverage'] == 273
    declared = read(study/'results.json')[candidate]
    assert result['accuracy'] == declared['accuracy'] and result['gains'] == declared['gains'] and result['losses'] == declared['losses']
    save_json(out/'verification.json', result); save_json(out/'policy.json', artifact); save_json(out/'predictions.json', rows)
    save_json(out/'retention.json', retention); save_json(out/'runtime_predictions.json', runtime); (out/'rubric.txt').write_text(final['rubric'])
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'cache_audit_manifest_sha256': file_hash(cache_audit/'manifest.json'),
        'study_manifest_sha256': file_hash(study/'manifest.json'), 'policy_ref': artifact['artifact_ref'],
        'runtime_sha256': file_hash(ROOT/'critical/core/calibration/local_semantic_runtime_v99.py'),
        'judge_sha256': file_hash(ROOT/'critical/core/optimization/prompt/calitree/local_semantic_judge_v99.py')})
    (out/'run.log').write_text('Selected local policy re-induced and915 actual bound judgments replayed. See verification.json; no default promotion performed.\n')
    print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cache', type=Path, required=True); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--cache-audit', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--candidate')
    a = p.parse_args(); audit(a.cache.resolve(), a.study.resolve(), a.cache_audit.resolve(), a.output_dir.resolve(), a.candidate)
