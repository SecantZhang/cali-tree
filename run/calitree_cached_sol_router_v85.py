"""Route qualified cached Sol judgments with source-held semantic rules.

No new model calls. Compare actual-input protection with a stronger arm that
protects every original against every hypothetical Sol label.
"""
import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np

from critical.core.calibration.seeded_rubric_v73 import SeededRubric,Search
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.decision.artifacts import digest,save_json
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.audit_calitree_regular_views_v84 import media_identity
from run.calitree_seeded_rubric_v73 import arrays,attach
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,FROZEN,read,fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS,INNER
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

AUDIT=ROOT/'logs/exps/261023-regular-views-v84-audit-r2'
RUBRICS=ROOT/'logs/exps/261023-verified-semantic-hybrid-v72-r1'
CONFIGS=[(Search(family=family,mode='routes',max_features=192,loss_cost=2.,min_sources=support),protection)
         for support in (2,1) for protection in ('hypothetical','actual') for family in ('semantic','grounded','auxiliary')]


def candidate_name(config,protection):
    return config.family if config.min_sources==2 and protection=='hypothetical' else f'{config.family}_s{config.min_sources}_{protection}'


def expert_artifact(rule,teacher_ref):
    value={k:v for k,v in rule.artifact(teacher_ref).items() if k!='artifact_ref'}
    value.update({'selected_expert':'gpt-6.1-sol','semantic_role':'Choose this independent regular visual judgment only when a review rule matches; otherwise retain v72.'})
    value['artifact_ref']=digest(value)
    return value


def cached(examples):
    audit=read(AUDIT/'results.json');raw=read(FROZEN/'replay_inputs_without_references.json')
    image_hashes=read(ROOT/'logs/exps/261021-paired-vision-v63/manifest.json')['image_hashes']
    prompt=(task.TEMPLATES/'regular.txt').read_text();labels=[];provenance=[]
    for e,r in zip(examples,raw):
        choices=[v for v in audit['all_matches'].get(e['case'],[]) if v['identity'].get('model')=='gpt-6.1-sol']
        choices.sort(key=lambda v:(v['job'],v['slot_ref']))
        if not choices:labels.append(-1);continue
        selected=choices[0];job=read(selected['job'])
        assert fingerprint(selected['job'])==selected['job_sha256']
        assert job['payload']=={'instruction':r['program']['instruction']}
        assert job['media_identity']==media_identity(r['evidence'],image_hashes)
        expected=digest([selected['identity'],job['case_id'],'flat_judge',job['payload'],task.SCHEMA,prompt,job['media_identity'],job['slot'],job['max_tokens']])
        assert expected==job['execution_ref']==selected['slot_ref']
        parsed=job.get('parsed');label=-1
        if job['outcome']=='completed' and isinstance(parsed,dict) and set(parsed)=={'rationale','label'} and parsed['label'] in ('no','partial','yes') and isinstance(parsed['rationale'],str) and parsed['rationale'].strip():label=('no','partial','yes').index(parsed['label'])
        labels.append(label);provenance.append({'case':e['case'],'available':label>=0,'selected_slot':selected,'label':label,'judgment':parsed if label>=0 else None})
    return np.asarray(labels),provenance


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,raw,semantic=arrays();sol,provenance=cached(examples)
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);pos={e['case']:i for i,e in enumerate(examples)}
    protocol={'version':'cached-independent-sol-semantic-router-v85','configs':[{'search':asdict(c),'protection':p} for c,p in CONFIGS],
        'expert':'Previously paid generic regular GPT-6.1 Sol judgments, selected by sorted compatible request path before reference scoring; missing/failed Sol keeps v72.',
        'evaluation':'Same276 primary cases/84 pixel sources/five source-held folds. Sol coverage15 valid primary cases plus1 failed slot is disclosed; not a full fresh Sol benchmark.',
        'selection':'Every routing rule begins with an explicit semantic review/defer reason or unwarranted-teacher/warranted-expert disagreement. No grade from model-support uncertainty alone.',
        'fitting':'Existing30 inner source-excluded v69 teacher views, actual fitting source labels only; every outer-held source sibling excluded. No new teacher fits.',
        'protection':'Factorial comparison: protect actual cached original views, or all three hypothetical Sol labels per original. Every arm retains all99 actual originals and144 slots. Actual-only protection does not promise invariance under fresh Sol labels.',
        'support_ablation':'One versus two distinct positive fitting sources. Every outer evaluation source remains excluded; support1 permits compact rules with limited fitting evidence rather than changing the benchmark.',
        'priority':'Existing v72 rules keep their original v69 teacher context and priority. The new gate only selects an optional Sol judgment, otherwise keeps v72.',
        'source_selection_bias':'The cached Sol subset comes from older selected diagnostics, with limited and nonrandom primary coverage. No claim of general full-population Sol routing accuracy.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);save_json(out/'expert_provenance.json',provenance)
    (out/'run.log').write_text('Source-held semantic Sol routing comparison started.\n');(out/'llm-histories.log').write_text('Zero API calls; old cryptographically matched Sol response paths recorded in expert_provenance.json.\n')
    original_slots=[item for bank in (1,2,3) for item in old_inputs(PREVIOUS,bank)[3]['local']]
    baseline={r['case']:r for r in read(RUBRICS/'predictions.json')}
    records=[];retention=[];controls=[]
    source_hashes={str(AUDIT/'results.json'):fingerprint(AUDIT/'results.json')}
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        train=[pos[c] for c in f['train_cases']];held=[pos[c] for c in f['held_cases']];assert not set(groups[train])&set(groups[held])
        folder='fold'+str(f['fold']);teacher=TEACHERS/folder;saved=read(teacher/'predictions.json');ps=np.asarray(saved['support']);oof_ps=ps.copy()
        for inner in range(5):
            path=INNER/folder/('inner'+str(inner));membership=read(path/'membership.json');excluded=set(membership['held_sources'])
            assert not set(membership['training_sources'])&(excluded|set(groups[held]))
            indices=[i for i in train if groups[i] in excluded];oof_ps[indices]=np.asarray(read(path/'predictions.json')['support'])[indices]
        actual=np.argmax(ps,axis=1);oof=np.argmax(oof_ps,axis=1);actual[~valid]=regular[~valid];oof[~valid]=regular[~valid]
        original=read(RUBRICS/folder/'rubric.json');assert original['teacher_ref']==(read(FROZEN/'policy.json')['artifact_ref'] if f['fold']==5 else digest(read(teacher/'teacher.json')['contract']))
        executor=SemanticRubricExecutor(original);columns={n:i for i,n in enumerate(names)}
        current=[];priority=[]
        for i in range(len(examples)):
            result=executor.select({n:bool(raw[i,columns[n]]) for n in original['feature_names']},int(actual[i])) if valid[i] else {'prediction':int(regular[i]),'rule_index':None}
            current.append(result['prediction']);priority.append(result['rule_index'] is not None)
        current=np.asarray(current);priority=np.asarray(priority)
        assert all(current[i]==baseline[examples[i]['case']]['prediction'] for i in held)
        full=attach(raw,semantic,ps,sol);training=attach(raw,semantic,oof_ps,sol)
        hypothetical=np.concatenate([attach(raw[:99],semantic[:99],ps[:99],np.full(99,label)) for label in (0,1,2)])
        fit=[i for i in train if valid[i] and sol[i]>=0]
        descriptor_priority={n:saved['priority'].get(n,0.)+(1000 if n.startswith('meaning_') else 1500 if n.startswith('rubric_') else 0) for n in names}
        for config,protection_mode in CONFIGS:
            if protection_mode=='hypothetical':protection,py,pb,pr=hypothetical,np.tile(y[:99],3),np.tile(actual[:99],3),np.repeat((0,1,2),99)
            else:protection,py,pb,pr=full[:99],y[:99],actual[:99],sol[:99]
            name=candidate_name(config,protection_mode);rule=SeededRubric(names,config).fit(training[fit],y[fit],groups=groups[fit].tolist(),base=oof[fit],regular=sol[fit],
                protected_X=protection,protected_y=py,protected_base=pb,protected_regular=pr,priority=descriptor_priority)
            possible=np.asarray(rule.predict(protection,base=pb,regular=pr));assert np.all(possible==py)
            p=np.asarray(rule.predict(full,base=actual,regular=sol));p[priority]=current[priority];p[~valid]=regular[~valid]
            assert np.all(p[:99]==y[:99]);slots=int(sum(p[pos[r['case']]]==r['reference'] for r in original_slots));assert slots==144
            artifact=expert_artifact(rule,digest(read(teacher/'teacher.json')['contract']))
            save_json(out/folder/(name+'.json'),artifact);(out/folder/(name+'.txt')).write_text(artifact['rubric'])
            retention.append({'candidate':name,'fold':f['fold'],'original_correct':99,'slots_correct':slots,'protection':protection_mode,'hypothetical_labels_checked':297 if protection_mode=='hypothetical' else 0,'rules':len(rule.rules)})
            for i in held:records.append({**examples[i],'prediction':int(p[i]),'baseline':int(current[i]),'sol':int(sol[i]),'candidate':name,'fold':f['fold']})
        for i in held:controls.append({**examples[i],'baseline':int(current[i]),'sol':int(sol[i]),'replace_if_available':int(sol[i]) if sol[i]>=0 and valid[i] else int(current[i])})
        source_hashes[str(teacher/'predictions.json')]=fingerprint(teacher/'predictions.json');source_hashes[str(RUBRICS/folder/'rubric.json')]=fingerprint(RUBRICS/folder/'rubric.json')
        print({'fold':f['fold'],'held_cases':len(held),'available_sol_training':len(fit),'rules':{r['candidate']:r['rules'] for r in retention if r['fold']==f['fold']}},flush=True)
    results={}
    for config,protection_mode in CONFIGS:
        name=candidate_name(config,protection_mode);rows=[r for r in records if r['candidate']==name]
        results[name]={'accuracy':accuracy(rows,'prediction'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'available_sol':sum(r['sol']>=0 for r in rows),'all_original_fits_retained':True,'all_hypothetical_original_sol_labels_retained':protection_mode=='hypothetical','upstream_evidence_coverage':sum(r['covered'] for r in rows),'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);save_json(out/'controls.json',controls)
    save_json(out/'manifest.json',{'code_sha256':{str(Path(__file__)):fingerprint(__file__)},'source_hashes':source_hashes,'targets_ref':digest(y.tolist()),'protocol_ref':digest(protocol)})
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(__file__).read_bytes())
    (out/'run.log').write_text('Completed twelve source-held semantic Sol routing candidates; all actual originals retained, hypothetical invariance only in its declared arms. No new API calls.\n');print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
