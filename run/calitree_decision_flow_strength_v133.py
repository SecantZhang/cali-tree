"""Test wider fit-only calibration strengths after real guarded decision flow."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.decision_flow_strength_v133 import GRID,MODES,flow,select
from critical.core.decision.artifacts import digest,save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load,fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

SOURCES=[('local_depth2','logs/exps/261023-semantic-residual-v103-r1',False),('local_depth3','logs/exps/261023-semantic-residual-v103-r1',False),
         ('contextual_depth2','logs/exps/261023-semantic-residual-v103-r1',False),('contextual_depth3','logs/exps/261023-semantic-residual-v103-r1',False),
         ('all_anchors_depth2','logs/exps/261023-anchored-semantic-residual-v106-r1',True),('all_anchors_depth3','logs/exps/261023-anchored-semantic-residual-v106-r1',True)]


def run(cache,cache_audit,out):
    if out.exists():raise ValueError('Fresh end-to-end-strength study required')
    from catboost import CatBoostRegressor
    d=load(cache,cache_audit);names=d['names'];y=d['y'];examples=d['examples']
    protocol={'version':'actual-flow-strength-v133','sources':SOURCES,'modes':MODES,'strength_grid':GRID,
        'change':'Keep existing selected native model weights fixed. Choose strength from fitting-only actual decision-flow accuracy/MSE, after each final guard, rather than before it. Allow up to2 while retaining original final decisions.',
        'warrants':'Strict mode keeps existing admissibility. Absence mode also permits No from explicit absent/opposite endpoint AND explicit no/incidental progress, for one requirement with consistent claims. Unknown target identity alone never permits No.',
        'fitting':'Same genuine inner-source-excluded fitting views; anchor-model fitting includes only its already used actual original review anchors. No held labels select strength.',
        'protection':'Hard original final-decision veto under each mode; then verify all99 original cases/144 slots and outside-review behavior. All276 cases and273 upstream coverage remain fixed.',
        'new_api_calls':0,'new_observer_calls':0,'new_model_fits':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Existing native weights cold-loaded; actual-flow strength comparison started.\n');(out/'llm-histories.log').write_text('No neural/API/encoder calls or new fits. Existing source-bound scores only.\n')
    files=[Path(__file__),ROOT/'critical/core/calibration/decision_flow_strength_v133.py',ROOT/'run/verify_calitree_semantic_residual_v105.py']
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    originals=[r for bank in(1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']];records=[];retention=[];source_hashes={}
    for f in[f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f);folder=a['folder'];fit=a['fit'];protected=a['protected'];actual_indices=np.flatnonzero(a['actual']&d['available']).tolist()
        for stem,location,anchors in SOURCES:
            source=ROOT/location;metadata=read(source/folder/(stem+'.json'));columns=[names.index(n) for n in metadata['features']]
            assert metadata['fit_cases']==[examples[i]['case'] for i in fit] and metadata['protected_review_cases']==[examples[i]['case'] for i in protected]
            assert metadata.get('anchor_cases',[])==([examples[i]['case'] for i in protected] if anchors else [])
            model=CatBoostRegressor();model.load_model(str(source/folder/(stem+'.cbm')))
            delta=np.asarray(model.predict(a['full'][:,columns]));fit_delta=np.asarray(model.predict(a['T'][fit][:,columns]))
            chosen=fit+protected if anchors else fit
            train_support=np.concatenate([a['oof'][fit],a['ps'][protected]],axis=0) if anchors else a['oof'][fit]
            train_delta=np.concatenate([fit_delta,delta[protected]],axis=0) if anchors else fit_delta
            train_flags=[d['flags_by_row'][i] for i in chosen];protected_flags=[d['flags_by_row'][i] for i in protected]
            assert not set(d['groups'][chosen])&set(d['groups'][a['held']])
            for mode in MODES:
                strength,trials=select(train_support,train_delta,y[chosen],d['groups'][chosen],train_flags,d['regular'][chosen],
                    a['ps'][protected],delta[protected],y[protected],protected_flags,d['regular'][protected],mode)
                candidate=stem+'_'+mode;p=a['current'].copy()
                final,_,_=flow(a['ps'][actual_indices],delta[actual_indices],strength,[d['flags_by_row'][i] for i in actual_indices],d['regular'][actual_indices],mode)
                p[actual_indices]=final
                assert np.all(p[:99]==y[:99]) and np.array_equal(p[~(a['actual']&d['available'])],a['current'][~(a['actual']&d['available'])])
                count=int(sum(p[d['pos'][r['case']]]==r['reference'] for r in originals));assert count==144
                save_json(out/folder/(candidate+'.json'),{'candidate':candidate,'strength':strength,'mode':mode,'trials':trials,'source_metadata_ref':digest(metadata),
                    'fit_cases':[examples[i]['case'] for i in chosen],'protected_review_cases':[examples[i]['case'] for i in protected]})
                save_json(out/folder/(candidate+'-predictions.json'),p.tolist());retention.append({'candidate':candidate,'fold':f['fold'],'strength':strength,'original_correct':99,'slots_correct':144})
                for i in a['held']:records.append({**examples[i],'candidate':candidate,'fold':f['fold'],'prediction':int(p[i]),'baseline':int(a['current'][i])})
            for name in(stem+'.json',stem+'.cbm',stem+'-native.json'):source_hashes[str(source/folder/name)]=file_hash(source/folder/name)
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);print({'fold':f['fold'],'native_models':len(SOURCES),'modes':3},flush=True)
    results={}
    for candidate in sorted({r['candidate'] for r in records}):
        rows=[r for r in records if r['candidate']==candidate];score=accuracy(rows,'prediction')
        results[candidate]={'accuracy':score,'baseline':accuracy(rows,'baseline'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'coverage':sum(r['covered'] for r in rows),'original_cases_retained':99,'original_slots_retained':144,'target_exceeded':score['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':{str(p):file_hash(p) for p in files},'source_hashes':source_hashes,'targets_ref':digest(y.tolist()),'protocol_ref':digest(protocol),'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json')})
    (out/'run.log').write_text('Completed36 existing native-model replays and18 actual-flow strength arms, with no new model fits/calls.\n');print({k:(v['accuracy']['correct'],v['gains'],v['losses']) for k,v in results.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','cache-audit','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.cache.resolve(),a.cache_audit.resolve(),a.output_dir.resolve())
