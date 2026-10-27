"""Source-held semantic residuals over a complete audited32B review cache."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.local_warranted_rubric_v97 import SPECS,DESCRIPTIONS,project
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT
from critical.core.calibration.decision_flow_strength_v133 import GRID,MODES,flow,select
from critical.core.decision.artifacts import digest,save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_large_probe_v130 import validate
from run.verify_calitree_semantic_residual_v105 import load as old_load,fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_warranted_rubric_v71 import TEACHERS

CONFIGS=[(family,depth,anchors) for family in('local','contextual') for depth in(2,3) for anchors in(False,True)]


def load(cache,cache_audit,*,legacy_control=False):
    if legacy_control:return old_load(cache,cache_audit)
    verified=read(cache_audit/'verification.json');audited=read(cache_audit/'manifest.json')
    assert verified['passed'] and verified['complete'] and not verified['snapshot_only'] and verified['source_masks_unchanged']
    assert audited['cache_manifest_sha256']==file_hash(cache/'manifest.json')
    for path,sha in audited['source_hashes'].items():assert file_hash(path)==sha,path
    manifest=read(cache/'manifest.json');base=old_load(Path(manifest['legacy_cache']),Path(manifest['legacy_audit']))
    keys=('examples','old_names','raw','semantic','y','groups','regular','valid','pos','sol','provenance','extra_names','names')
    d={k:base[k] for k in keys};profile=read(cache/'identity.json');jobs=read(cache/'jobs.json')
    extra=np.zeros((len(d['examples']),len(d['extra_names'])));available=np.zeros(len(extra),dtype=bool);local_records={};flags_by_row={}
    assert d['extra_names']==list(SPECS)
    for job in jobs:
        response=read(cache/'responses'/(job['case']+'.json'));passed=validate(job,response,profile);local_records[job['case']]=response['record']
        if passed:
            flags=project(job['program'],job['image_pair_ref'],digest(profile),job['prompt_ref'],response['record']);i=d['pos'][job['case']]
            extra[i]=[int(flags[n]) for n in d['extra_names']];available[i]=True;flags_by_row[i]=flags
    d.update(cache=cache,cache_audit=cache_audit,verification=verified,profile=profile,jobs=jobs,extra=extra,available=available,local_records=local_records,flags_by_row=flags_by_row,
        template=(cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text())
    return d


def run(cache,cache_audit,out,*,legacy_control=False):
    if out.exists():raise ValueError('Fresh large-semantic policy study required')
    d=load(cache,cache_audit,legacy_control=legacy_control);examples=d['examples'];names=d['names'];y=d['y']
    protocol={'version':'large-semantic-residual-v135','legacy_control':legacy_control,'configs':CONFIGS,'modes':MODES,'strength_grid':GRID,
        'features':'Same closed local/contextual semantic vocabulary and teacher supports as v103. The explicit legacy-control flag uses audited8B facts; the default uses audited32B bounded facts. No source/editor/case IDs, object names or new raw vision vectors.',
        'fitting':'Each fold genuine source-excluded review observations only; anchored arms also include actual original review inputs as supervised fitting anchors from already fitting groups. No held-source siblings enter.',
        'model':'Same128 depth2/3 MultiRMSE residual trees/source-equal weights. Strength is selected fit-only after each actual guard, up to2. All actual original final decisions veto harmful strengths.',
        'guards':'Score-only, original positive-warrant/independent-review guard, and a separate explicit-absence/no-progress No alternative. Unknown identity alone never supplies failure.',
        'flow':'Existing v72/v87 priority and .8 review route unchanged. Missing/failed records and outside-review cases retain the prior decision. Full276 denominator, original99/144 and273 coverage checked.',
        'selection':'Higher correct, fewer losses, strict/absence/score guard order, smaller depth, local vocabulary, lexical name; no automatic promotion or goal completion. All are reviewed development comparisons.',
        'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Complete audited32B cache accepted; source-held semantic policy fits started.\n');(out/'llm-histories.log').write_text('No neural/API/encoder calls or reserved inputs. Cached source-bound semantic facts only.\n')
    files=[Path(__file__),ROOT/'critical/core/calibration/semantic_residual_v103.py',ROOT/'critical/core/calibration/decision_flow_strength_v133.py',ROOT/'critical/core/calibration/local_warranted_rubric_v97.py',ROOT/'run/verify_calitree_semantic_residual_v105.py']
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    original=[r for bank in(1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']];records=[];retention=[]
    for f in[f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f);folder=a['folder'];fit=a['fit'];protected=a['protected'];actual_indices=np.flatnonzero(a['actual']&d['available']).tolist()
        for family,depth,anchors in CONFIGS:
            columns=[i for i,n in enumerate(names) if n in SPECS or n in SUPPORT or n.startswith('view_') or(family=='contextual' and n.startswith(('meaning_','task_','intent_','requires_','rationale_','rubric_')))]
            feature_names=[names[i] for i in columns];chosen=fit+protected if anchors else fit
            X=np.concatenate([a['T'][fit][:,columns],a['full'][protected][:,columns]],axis=0) if anchors else a['T'][fit][:,columns]
            ps=np.concatenate([a['oof'][fit],a['ps'][protected]],axis=0) if anchors else a['oof'][fit]
            assert len(set(chosen))==len(chosen) and set(chosen)<=set(a['train']) and not set(d['groups'][chosen])&set(d['groups'][a['held']])
            model=SemanticResidual(feature_names,depth=depth).fit(X,y[chosen],support=ps,groups=d['groups'][chosen],
                protected_X=a['full'][protected][:,columns],protected_y=y[protected],protected_support=a['ps'][protected])
            stem=family+'_depth'+str(depth)+('_anchors' if anchors else '_noanchors');metadata=model.artifact({**DESCRIPTIONS,**SUPPORT})
            metadata.update(fit_cases=[examples[i]['case'] for i in fit],anchor_cases=[examples[i]['case'] for i in protected] if anchors else [],
                protected_review_cases=[examples[i]['case'] for i in protected],observer_identity_ref=digest(d['profile']),teacher_ref=digest(read(TEACHERS/folder/'teacher.json')['contract']))
            save_json(out/folder/(stem+'.json'),metadata);model.model.save_model(str(out/folder/(stem+'.cbm')));model.model.save_model(str(out/folder/(stem+'-native.json')),format='json')
            delta=np.asarray(model.model.predict(a['full'][:,columns]));train_delta=np.asarray(model.model.predict(X))
            train_flags=[d['flags_by_row'][i] for i in chosen];protected_flags=[d['flags_by_row'][i] for i in protected]
            for mode in MODES:
                strength,trials=select(ps,train_delta,y[chosen],d['groups'][chosen],train_flags,d['regular'][chosen],a['ps'][protected],delta[protected],y[protected],protected_flags,d['regular'][protected],mode)
                candidate=stem+'_'+mode;p=a['current'].copy();proposal,_,_=flow(a['ps'][actual_indices],delta[actual_indices],strength,[d['flags_by_row'][i] for i in actual_indices],d['regular'][actual_indices],mode);p[actual_indices]=proposal
                assert np.all(p[:99]==y[:99]) and np.array_equal(p[~(a['actual']&d['available'])],a['current'][~(a['actual']&d['available'])])
                count=int(sum(p[d['pos'][r['case']]]==r['reference'] for r in original));assert count==144
                artifact={**metadata,'base_model_ref':digest(metadata),'strength':strength,'strength_trials':trials,'strength_protocol':'after_actual_guarded_flow_v133','mode':mode,
                    'source_model':stem,'family':family,'anchors':anchors}
                save_json(out/folder/(candidate+'.json'),artifact);save_json(out/folder/(candidate+'-predictions.json'),p.tolist())
                retention.append({'candidate':candidate,'fold':f['fold'],'strength':strength,'original_correct':99,'slots_correct':144,'features':len(columns),'fit_rows':len(fit),'anchors':len(chosen)-len(fit)})
                for i in a['held']:records.append({**examples[i],'candidate':candidate,'fold':f['fold'],'prediction':int(p[i]),'baseline':int(a['current'][i]),'review':bool(a['actual'][i]),'local_available':bool(a['actual'][i] and d['available'][i])})
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);print({'fold':f['fold'],'native_fits':len(CONFIGS),'fit_rows':len(fit)},flush=True)
    results={}
    for candidate in sorted({r['candidate'] for r in records}):
        rows=[r for r in records if r['candidate']==candidate];score=accuracy(rows,'prediction')
        results[candidate]={'accuracy':score,'baseline':accuracy(rows,'baseline'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'coverage':sum(r['covered'] for r in rows),'original_cases_retained':99,'original_slots_retained':144,'target_exceeded':score['correct']>=235}
    guard_order={'strict':0,'absence':1,'score':2}
    selected=min(results,key=lambda k:(-results[k]['accuracy']['correct'],results[k]['losses'],guard_order[k.rsplit('_',1)[1]],int(k.split('_depth')[1].split('_')[0]),0 if k.startswith('local_') else 1,k))
    save_json(out/'results.json',results);save_json(out/'selection.json',{'candidate':selected,'result':results[selected],'verified':False,'needs_policy_audit':results[selected]['accuracy']['correct']>227,'serving_changed':False})
    save_json(out/'manifest.json',{'code_sha256':{str(p):file_hash(p) for p in files},'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json'),'targets_ref':digest(y.tolist()),'protocol_ref':digest(protocol)})
    (out/'run.log').write_text('Completed48 source-held model fits and24 score/guard arms. No promotion or goal-status change; independent runtime audit still required for any improvement.\n');print({k:(v['accuracy']['correct'],v['gains'],v['losses']) for k,v in results.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','cache-audit','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--legacy-control',action='store_true');a=p.parse_args();run(a.cache.resolve(),a.cache_audit.resolve(),a.output_dir.resolve(),legacy_control=a.legacy_control)
