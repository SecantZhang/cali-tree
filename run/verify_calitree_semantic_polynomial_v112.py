"""Prove exact semantic-term compression through native and bound runtime replay."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, ResidualExecutor, SemanticResidualPolicy, admissible
from critical.core.calibration.local_semantic_runtime_v99 import content_ref
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricPolicy
from critical.core.calibration.independent_expert_v87 import IndependentExpertPolicy, record_from_job
from critical.core.optimization.prompt.calitree.semantic_residual_judge_v104 import SemanticResidualJudge
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS, LABELS
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, VISION, read
from run.calitree_source_excluded_calibration_v89 import RUBRICS, EXPERT
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy


def audit(cache, cache_audit, study, verified, out):
    if out.exists():
        raise ValueError('Fresh compression audit required')
    prior = read(verified/'verification.json'); parent_manifest = read(verified/'manifest.json')
    assert prior['passed'] and prior['high_level_runtime_replays'] == 915 and prior['reinduced_models'] == 6
    assert parent_manifest['study_manifest_sha256'] == file_hash(study/'manifest.json') and parent_manifest['cache_audit_manifest_sha256'] == file_hash(cache_audit/'manifest.json')
    for path, sha in parent_manifest['code_sha256'].items():
        assert file_hash(path) == sha
    original_policy = read(verified/'policy.json'); assert original_policy['artifact_ref'] == content_ref(original_policy) == parent_manifest['policy_ref']
    d = load(cache, cache_audit); names = d['names']; examples = d['examples']; y = d['y']; candidate = prior['candidate']; stem = candidate.removesuffix('_guarded')
    original_slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Exact algebraic semantic compression audit started; no selection/pruning.\n'); (out/'llm-histories.log').write_text('No observer/encoder/API calls. Existing selected model re-induction and bound cached inference only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/semantic_polynomial_v111.py']
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,dest)
    rows=[]; compression=[]; maximum=0.; saved={r['case']:r for r in read(verified/'predictions.json')}
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f); folder=a['folder']; native=read(study/folder/(stem+'-native.json')); metadata=read(study/folder/(stem+'.json')); old=read(verified/folder/'rubric.json')
        assert native and digest(native)==old['native_model_ref']
        compiled=compile_polynomial(native,metadata); assert compiled['compilation']['source_clauses_ref']==old['artifact_ref']
        before=ResidualExecutor(old); after=ResidualExecutor(compiled); columns=[names.index(n) for n in metadata['features']]; fit=a['fit']; protected=a['protected']
        assert metadata['fit_cases']==[examples[i]['case'] for i in fit] and metadata['protected_review_cases']==[examples[i]['case'] for i in protected]
        model=SemanticResidual(metadata['features'],depth=metadata['depth'],iterations=metadata['iterations']).fit(a['T'][fit][:,columns],y[fit],support=a['oof'][fit],groups=d['groups'][fit],
            protected_X=a['full'][protected][:,columns],protected_y=y[protected],protected_support=a['ps'][protected])
        assert model.artifact({**DESCRIPTIONS,**SUPPORT})=={k:v for k,v in metadata.items() if k not in ('fit_cases','protected_review_cases','teacher_ref','observer_identity_ref')}
        (out/folder).mkdir(); model.model.save_model(str(out/folder/'native.json'),format='json'); reconstructed=read(out/folder/'native.json')
        assert all(reconstructed[k]==native[k] for k in ('features_info','oblivious_trees','scale_and_bias'))
        native_delta=np.asarray(model.model.predict(a['full'][:,columns])); p=a['current'].copy()
        for i in range(len(examples)):
            values={n:float(a['full'][i,j]) if n in SUPPORT else bool(a['full'][i,j]) for j,n in enumerate(names)}
            v=before.evaluate(values,a['ps'][i].tolist()); w=after.evaluate(values,a['ps'][i].tolist())
            maximum=max(maximum,float(np.max(np.abs(np.asarray(w['residual'])-native_delta[i]))))
            assert maximum<1e-12 and v['prediction']==w['prediction']
            assert np.allclose(v['corrected_model_mass'],w['corrected_model_mass'],atol=1e-12,rtol=0)
            if a['actual'][i] and d['available'][i] and admissible(values,int(np.argmax(a['ps'][i])),int(d['regular'][i]),w['prediction']):
                p[i]=w['prediction']
        assert p.tolist()==read(study/folder/(candidate+'-predictions.json')) and np.all(p[:99]==y[:99])
        assert sum(p[d['pos'][r['case']]]==r['reference'] for r in original_slots)==144
        for i in a['held']:
            r=saved[examples[i]['case']]; assert r['prediction']==int(p[i]) and r['fold']==f['fold']; rows.append(r)
        summary={'fold':f['fold'],'source_clauses':len(old['clauses']),'shared_terms':len(compiled['clauses']),
            'single_conditions':sum(len(t['conditions'])==1 for t in compiled['clauses']), 'interactions':sum(len(t['conditions'])>1 for t in compiled['clauses']),
            'feature_count':len(compiled['features']),'original_correct':99,'original_slots_correct':144}
        compression.append(summary); save_json(out/folder/'rubric.json',compiled); print(summary,flush=True)
        if f['fold']==5:
            final,final_predictions,final_review=compiled,p,a['actual']
    teacher=VisualSemanticPolicy(read(FROZEN/'policy.json')); previous=SemanticRubricPolicy(teacher,read(RUBRICS/'rubric.json')); base=IndependentExpertPolicy(previous,read(EXPERT/'policy.json'))
    exported=deepcopy(original_policy); exported.update(rubric=final,compilation_parent_ref=original_policy['artifact_ref']); exported['artifact_ref']=content_ref(exported)
    policy=SemanticResidualPolicy(base,exported)
    def forbidden(*args,**kwargs):
        raise AssertionError('Compressed cached runtime must not call a model or encoder')
    judge=SemanticResidualJudge(None,policy,SimpleNamespace(compute=forbidden)); by_case={r['case']:r for r in d['provenance']}; hashes=read(VISION/'manifest.json')['image_hashes']; runtime=[]
    prior_runtime={r['case']:r for r in read(verified/'runtime_predictions.json')}
    for i,r in enumerate(read(FROZEN/'replay_inputs_without_references.json')):
        pair=digest(['bound-physical-evidence-v2','source_first',hashes[r['evidence']['source_image']],hashes[r['evidence']['edited_image']]]); expert=None
        if r['case'] in by_case:
            slot=by_case[r['case']]['selected_slot']; contract=base.artifact['expert_contract']; expert=record_from_job(r['program'],pair,slot['identity'],read(slot['job']),contract['schema'],contract['template'])
        vision_record={'version':vision.VERSION,'feature_contract_ref':vision.CONTRACT_REF,'program_ref':r['program']['program_ref'],'image_pair_ref':pair,
            'encoder_spec_ref':digest(teacher.artifact['encoder_spec']),'measurements':read(VISION/'cases'/(r['case']+'.json'))['measurements']}
        result=judge.judge(r['program']['instruction'],r['evidence'],program=r['program'],observation=r['observation'],interpretation=r['interpretation'],regular_judgment=r['judgment'],
            vision_record=vision_record,expert_record=expert,local_record=d['local_records'].get(r['case']))
        prediction=LABELS.index(result['judgment']['label']) if result['judgment']['label']!='unresolved' else -1; route=result['route']
        assert prediction==final_predictions[i] and 'local_review_error' not in route
        item={'case':r['case'],'prediction':prediction,'covered':route['covered'],'source':result['source']}; assert item==prior_runtime[r['case']]
        preceding=route['base_route'] if route.get('reason')=='semantic_residual_override' else route
        assert policy.review_route(preceding)==bool(final_review[i])
        if route.get('reason')=='semantic_residual_override':
            assert 'class_support' not in route and route['semantic_residual']['guard'] in ('affirmative_local_grade_warrant','independent_regular_review')
        runtime.append(item)
    result={'passed':True,'accuracy':accuracy(rows,'prediction'),'coverage':sum(r['covered'] for r in rows),'original_cases_per_fit':99,'original_slots_per_fit':144,
        'reinduced_models':6,'native_residual_rows':6*len(examples),'portable_runtime_replays':len(runtime),'max_native_residual_error':maximum,
        'all_predictions_and_routes_unchanged':True,'source_full_clauses':compression[-1]['source_clauses'],'full_shared_terms':compression[-1]['shared_terms'],
        'full_single_conditions':compression[-1]['single_conditions'],'full_interactions':compression[-1]['interactions'],'full_feature_count':len(final['features']),
        'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0,'serving_defaults_changed':False,'target_exceeded':accuracy(rows,'prediction')['correct']>=235,
        'scope':'Exact algebraic compression of an existing reviewed-development policy; not a new accuracy improvement or untouched validation.'}
    assert result['accuracy']==prior['accuracy'] and result['coverage']==prior['coverage']
    save_json(out/'verification.json',result); save_json(out/'policy.json',exported); save_json(out/'predictions.json',rows); save_json(out/'runtime_predictions.json',runtime); save_json(out/'compression.json',compression)
    (out/'rubric.txt').write_text(final['rubric']); save_json(out/'manifest.json',{'parent_manifest_sha256':file_hash(verified/'manifest.json'),'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json'),
        'policy_ref':exported['artifact_ref'],'code_sha256':{str(p):file_hash(p) for p in files}})
    (out/'run.log').write_text('Six native models re-induced;5490 residuals and915 bound judgments unchanged. Exact shared semantic compression verified; no new accuracy claim.\n'); print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cache','cache-audit','study','verified','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); audit(a.cache.resolve(),a.cache_audit.resolve(),a.study.resolve(),a.verified.resolve(),a.output_dir.resolve())
