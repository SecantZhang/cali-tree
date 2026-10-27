"""Re-induce the cached-expert gate and replay bound optional-expert inference."""
import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from catboost import CatBoostClassifier

from critical.core.calibration.seeded_rubric_v73 import SeededRubric,Search
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor,SemanticRubricPolicy
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.calibration.independent_expert_v87 import ExpertGate,IndependentExpertPolicy,record_from_job,export_expert_policy,content_ref
from critical.core.optimization.prompt.calitree.independent_semantic_judge_v87 import IndependentSemanticJudge
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.core.decision.artifacts import digest,save_json
from critical.vision import paired_features_v69 as vision
from run.calitree_seeded_rubric_v73 import arrays,attach
from run.calitree_semantic_rubric_v70 import data,FROZEN,VISION,STUDY,ROOT,read,fingerprint
from run.calitree_cached_sol_router_v85 import cached,expert_artifact
from run.calitree_warranted_rubric_v71 import TEACHERS,INNER
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

RUBRICS=ROOT/'logs/exps/261023-verified-semantic-hybrid-v72-r1'
CANDIDATE='semantic_s1_hypothetical'


def audit(study,out):
    if out.exists():raise ValueError('Fresh audit directory required')
    examples,names,raw,semantic=arrays();sol,provenance=cached(examples);original_raw=read(FROZEN/'replay_inputs_without_references.json')
    full_examples,teacher_names,teacher_X=data();assert examples==full_examples
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);pos={e['case']:i for i,e in enumerate(examples)}
    manifest=read(study/'manifest.json')
    for file,expected in manifest['code_sha256'].items():assert fingerprint(study/'source_snapshot'/Path(file).relative_to(ROOT))==expected
    for file,expected in manifest['source_hashes'].items():assert fingerprint(file)==expected
    reserved=read(ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json');assert not set(groups)&{e['source_group'] for e in reserved}
    expected_rows={r['case']:r for r in read(study/'predictions.json') if r['candidate']==CANDIDATE}
    originals=[r for bank in (1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']]
    rows=[];retention=[];closure=[];native_count=0;final_gate=final_predictions=None
    out.mkdir(parents=True);(out/'run.log').write_text('Independent source exclusion, gate induction and bound runtime audit started.\n');(out/'llm-histories.log').write_text('Zero API calls or new neural inference. Native classifiers and cached bound judgments only.\n')
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        folder='fold'+str(f['fold']);teacher=TEACHERS/folder;train=[pos[c] for c in f['train_cases']];held=[pos[c] for c in f['held_cases']]
        assert not set(groups[train])&set(groups[held]);meta=read(teacher/'teacher.json')['contract'];assert meta['rows']==train
        columns=[teacher_names.index(n) for n in meta['columns']];assert meta['matrix_ref']==digest(teacher_X[train][:,columns].tolist()) and meta['targets_ref']==digest(y[train].tolist())
        model=CatBoostClassifier();model.load_model(str(teacher/'teacher.cbm'));ps=model.predict_proba(teacher_X[:,columns],thread_count=2)
        saved=read(teacher/'predictions.json');assert np.allclose(ps,saved['support'],atol=1e-12,rtol=0);native_count+=1;oof_ps=ps.copy()
        memberships=[]
        for inner in range(5):
            path=INNER/folder/('inner'+str(inner));m=read(path/'membership.json');excluded=set(m['held_sources']);expected_train=[i for i in train if groups[i] not in excluded]
            assert m['train']==expected_train and not set(m['training_sources'])&(excluded|set(groups[held]))
            info=read(path/'teacher.json')['contract'];cs=[teacher_names.index(n) for n in info['columns']]
            assert info['rows']==expected_train and info['matrix_ref']==digest(teacher_X[expected_train][:,cs].tolist()) and info['targets_ref']==digest(y[expected_train].tolist())
            model=CatBoostClassifier();model.load_model(str(path/'teacher.cbm'));p=model.predict_proba(teacher_X[:,cs],thread_count=2)
            assert np.allclose(p,read(path/'predictions.json')['support'],atol=1e-12,rtol=0);native_count+=1
            indices=[i for i in train if groups[i] in excluded];oof_ps[indices]=p[indices];memberships.append(m)
        actual=np.argmax(ps,axis=1);context=actual.copy();oof=np.argmax(oof_ps,axis=1);actual[~valid]=regular[~valid];oof[~valid]=regular[~valid]
        full=attach(raw,semantic,ps,sol);training=attach(raw,semantic,oof_ps,sol)
        protection=np.concatenate([attach(raw[:99],semantic[:99],ps[:99],np.full(99,g)) for g in (0,1,2)])
        py=np.tile(y[:99],3);pb=np.tile(actual[:99],3);pr=np.repeat((0,1,2),99);fit=[i for i in train if valid[i] and sol[i]>=0]
        stored=read(study/folder/(CANDIDATE+'.json'));ranking={n:saved['priority'].get(n,0.)+(1000 if n.startswith('meaning_') else 1500 if n.startswith('rubric_') else 0) for n in names}
        learned=SeededRubric(names,Search(**stored['config'])).fit(training[fit],y[fit],groups=groups[fit].tolist(),base=oof[fit],regular=sol[fit],protected_X=protection,protected_y=py,protected_base=pb,protected_regular=pr,priority=ranking)
        rebuilt=expert_artifact(learned,digest(meta));assert rebuilt==stored
        gate=ExpertGate(stored);assert stored['artifact_ref']==content_ref(stored)
        for index,values in enumerate(protection):
            selected=gate.select({n:bool(values[names.index(n)]) for n in stored['feature_names']},int(pb[index]),int(pr[index]))
            assert selected is None or selected['prediction']==py[index]
        old=read(RUBRICS/folder/'rubric.json');executor=SemanticRubricExecutor(old);current=[];priority=[]
        for i in range(915):
            r=executor.select({n:bool(raw[i,names.index(n)]) for n in old['feature_names']},int(actual[i])) if valid[i] else {'prediction':int(regular[i]),'rule_index':None}
            current.append(r['prediction']);priority.append(r['rule_index'] is not None)
        current=np.asarray(current);priority=np.asarray(priority);p=current.copy();fired=np.zeros(915,dtype=bool)
        for i in range(915):
            if valid[i] and not priority[i] and sol[i]>=0:
                r=gate.select({n:bool(full[i,names.index(n)]) for n in stored['feature_names']},int(actual[i]),int(sol[i]))
                if r is not None:p[i]=r['prediction'];fired[i]=True
        assert np.all(p[:99]==y[:99]);slots=int(sum(p[pos[r['case']]]==r['reference'] for r in originals));assert slots==144
        retention.append({'fold':f['fold'],'original_correct':99,'slots_correct':slots,'hypothetical_original_labels_checked':297})
        for c in f['held_cases']:
            i=pos[c];assert p[i]==expected_rows[c]['prediction'];rows.append({**examples[i],'prediction':int(p[i]),'baseline':int(current[i]),'sol':int(sol[i]),'expert_selected':bool(fired[i]),'fold':f['fold']})
        # Distillation ablation: an explicit witness must support the proposed
        # grade, and only one counterfactual expert grade may qualify. This is
        # deliberately a changed policy, not an equivalence certificate.
        possibilities=[set() for _ in examples]
        for g,label in enumerate(('no','partial','yes')):
            hypothesis=attach(raw,semantic,ps,np.full(915,g))
            for i in range(915):
                if not valid[i] or not semantic[i]['rubric_'+label+'_ready']:continue
                r=gate.select({n:bool(hypothesis[i,names.index(n)]) for n in stored['feature_names']},int(context[i]),g)
                if r is not None and r['prediction']!=context[i]:possibilities[i].add(g)
        lifted=current.copy()
        for i,s in enumerate(possibilities):
            if valid[i] and not priority[i] and len(s)==1:lifted[i]=next(iter(s))
        assert np.all(lifted[:99]==y[:99])
        for c in f['held_cases']:
            i=pos[c];closure.append({**examples[i],'prediction':int(lifted[i]),'baseline':int(current[i]),'fold':f['fold']})
        save_json(out/folder/'gate.json',stored);save_json(out/folder/'memberships.json',{'train_cases':f['train_cases'],'held_cases':f['held_cases'],'fit_sol_cases':[examples[i]['case'] for i in fit],'inner_folds':memberships})
        if f['fold']==5:final_gate=stored;final_predictions=p;final_support=ps
        print({'fold':f['fold'],'native_models_checked':native_count,'original_slots':slots},flush=True)
    base=SemanticRubricPolicy(VisualSemanticPolicy(read(FROZEN/'policy.json')),read(RUBRICS/'rubric.json'))
    # Confirm the portable native teacher is the same full model before binding
    # the learned gate to its exported classifier identity.
    for i in range(915):
        assert np.allclose(base.teacher.probabilities({n:bool(teacher_X[i,teacher_names.index(n)]) for n in base.teacher.artifact['feature_names']}),final_support[i],atol=1e-12,rtol=0)
    identities=[]
    for r in provenance:
        identity=r['selected_slot']['identity']
        if identity not in identities:identities.append(identity)
    contract={'identities':identities,'schema':task.SCHEMA,'template':(task.TEMPLATES/'regular.txt').read_text()}
    artifact=export_expert_policy(base,final_gate,contract);policy=IndependentExpertPolicy(base,artifact)
    def forbidden(*args,**kwargs):raise AssertionError('No model or encoder call allowed in cached replay')
    judge=IndependentSemanticJudge(None,policy,SimpleNamespace(compute=forbidden));by_case={r['case']:r for r in provenance};hashes=read(VISION/'manifest.json')['image_hashes'];runtime=[]
    for i,r in enumerate(original_raw):
        pair=digest(['bound-physical-evidence-v2','source_first',hashes[r['evidence']['source_image']],hashes[r['evidence']['edited_image']]])
        record=None
        if r['case'] in by_case:
            selected=by_case[r['case']]['selected_slot'];record=record_from_job(r['program'],pair,selected['identity'],read(selected['job']),contract['schema'],contract['template'])
        measured=read(VISION/'cases'/(r['case']+'.json'))['measurements'];v={'version':vision.VERSION,'feature_contract_ref':vision.CONTRACT_REF,'program_ref':r['program']['program_ref'],'image_pair_ref':pair,'encoder_spec_ref':digest(base.teacher.artifact['encoder_spec']),'measurements':measured}
        result=judge.judge(r['program']['instruction'],r['evidence'],program=r['program'],observation=r['observation'],interpretation=r['interpretation'],regular_judgment=r['judgment'],vision_record=v,expert_record=record)
        review=policy.review_bound(r['program'],r['observation'],pair,r['interpretation'],r['judgment'],v)
        predicted=('no','partial','yes').index(result['judgment']['label']) if result['judgment']['label']!='unresolved' else -1
        assert predicted==final_predictions[i] and result['route']['covered']==bool(valid[i]),r['case']
        assert 'independent_expert_error' not in result['route'],r['case']
        if result['source']=='independent_semantic_expert':assert 'class_support' not in result['route'] and 'base_route' in result['route']
        if i<99:assert not review['review_needed']
        runtime.append({'case':r['case'],'prediction':predicted,'covered':result['route']['covered'],'source':result['source'],'review_needed':review['review_needed']})
    result={'passed':True,'candidate':CANDIDATE,'accuracy':accuracy(rows,'prediction'),'baseline':accuracy(rows,'baseline'),
        'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
        'valid_sol_primary':sum(r['sol']>=0 for r in rows),'expert_selected_primary':sum(r['expert_selected'] for r in rows),'coverage':sum(r['covered'] for r in rows),
        'native_models_checked':native_count,'reinduced_gates':6,'original_cases_per_fit':99,'original_slots_per_fit':144,'hypothetical_original_labels_per_fit':297,'runtime_cases':len(runtime),'original_cases_requesting_independent_review':sum(r['review_needed'] for r in runtime[:99]),
        'no_independent_vote_ablation':{'accuracy':accuracy(closure,'prediction'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in closure),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in closure)},
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False,
        'scope':'Source-held development with15 available nonrandom cached Sol views, not a complete or fresh Sol benchmark. The optional expert remains essential; counterfactual standalone grading is a changed, worse policy. >85% remains unmet.'}
    assert result['accuracy']['correct']==225 and result['gains']==2 and result['losses']==0 and result['coverage']==273
    save_json(out/'policy.json',artifact);(out/'rubric.txt').write_text(artifact['gate']['rubric']);save_json(out/'predictions.json',rows);save_json(out/'retention.json',retention);save_json(out/'runtime_predictions.json',runtime);save_json(out/'standalone_ablation.json',closure)
    save_json(out/'manifest.json',{'auditor_sha256':fingerprint(__file__),'study_manifest_sha256':fingerprint(study/'manifest.json'),'policy_ref':artifact['artifact_ref'],
        'runtime_sha256':fingerprint(ROOT/'critical/core/calibration/independent_expert_v87.py'),'judge_sha256':fingerprint(ROOT/'critical/core/optimization/prompt/calitree/independent_semantic_judge_v87.py')})
    (out/'run.log').write_text('Independently verified cached-expert source-held comparison and915 high-level bound replays. See verification.json for scope.\n');save_json(out/'verification.json',result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();audit(a.study.resolve(),a.output_dir.resolve())
