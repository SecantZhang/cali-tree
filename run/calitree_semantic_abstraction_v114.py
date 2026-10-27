"""Compare meaningful claim interactions without rationale-word proxies."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_residual_v103 import SemanticResidual
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, admissible
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_warranted_rubric_v71 import TEACHERS

CONFIGS=[(family,depth) for family in ('meaning','meaning_task') for depth in (2,3)]


def run(cache,cache_audit,out):
    if out.exists():
        raise ValueError('Fresh semantic-abstraction study required')
    d=load(cache,cache_audit);names=d['names'];examples=d['examples'];y=d['y']
    protocol={'version':'rationale-free-semantic-residual-v114','configs':CONFIGS,
        'reason':'Near-constant rationale availability and word-presence interactions can obscure the intended judging policy. Compare claim/meaning-only and task-aware semantic vocabularies, both excluding rationale token proxies.',
        'features':{'meaning':['local_','meaning_','rubric_','view_','teacher_support_'],'meaning_task':['local_','meaning_','rubric_','view_','teacher_support_','intent_','requires_','task_']},
        'fitting':'Each fold genuine source-excluded review observations plus actual original review inputs as supervised anchors. No source/editor IDs, raw visual vectors or object names. All original labels already belong to fitting sources.',
        'model':'Same128 depth2/3 MultiRMSE residual trees and source-equal weights. Fit-only strength grid with hard original-case veto.',
        'flow':'Same .8 review region and v72/v87 priority. Compare score-only with the unchanged affirmative-local-warrant/independent-regular-review guard. All276 cases and99/144 protection remain required.',
        'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Rationale-free source-held semantic residual comparison started.\n');(out/'llm-histories.log').write_text('Cached evidence only; no model/API/encoder calls or reserved sources.\n')
    files=[Path(__file__),ROOT/'run/verify_calitree_semantic_residual_v105.py',ROOT/'critical/core/calibration/semantic_residual_v103.py',ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py']
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    slots=[r for bank in(1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']];records=[];retention=[]
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f);folder=a['folder'];fit=a['fit'];protected=a['protected'];chosen=fit+protected
        assert len(set(chosen))==len(chosen) and set(chosen)<=set(a['train']) and not set(d['groups'][chosen]) & set(d['groups'][a['held']])
        for family,depth in CONFIGS:
            columns=[j for j,n in enumerate(names) if n.startswith(tuple(protocol['features'][family]))];feature_names=[names[j] for j in columns]
            assert not any(n.startswith('rationale_') for n in feature_names)
            X=np.concatenate([a['T'][fit][:,columns],a['full'][protected][:,columns]],axis=0);supports=np.concatenate([a['oof'][fit],a['ps'][protected]],axis=0)
            model=SemanticResidual(feature_names,depth=depth).fit(X,y[chosen],support=supports,groups=d['groups'][chosen],protected_X=a['full'][protected][:,columns],protected_y=y[protected],protected_support=a['ps'][protected])
            stem=family+'_depth'+str(depth);artifact=model.artifact({**DESCRIPTIONS,**SUPPORT});artifact.update(teacher_ref=digest(read(TEACHERS/folder/'teacher.json')['contract']),observer_identity_ref=digest(d['profile']),
                fit_cases=[examples[i]['case'] for i in fit],anchor_cases=[examples[i]['case'] for i in protected],protected_review_cases=[examples[i]['case'] for i in protected],family=family)
            save_json(out/folder/(stem+'.json'),artifact);model.model.save_model(str(out/folder/(stem+'.cbm')));model.model.save_model(str(out/folder/(stem+'-native.json')),format='json')
            proposed=np.argmax(model.predict_proba(a['full'][:,columns],support=a['ps']),axis=1)
            for guarded in(False,True):
                candidate=stem+('_guarded' if guarded else '_score');p=a['current'].copy()
                for i in np.flatnonzero(a['actual']&d['available']):
                    if not guarded or admissible(d['flags_by_row'][i],int(np.argmax(a['ps'][i])),int(d['regular'][i]),int(proposed[i])):
                        p[i]=proposed[i]
                assert np.all(p[:99]==y[:99]) and np.array_equal(p[~(a['actual']&d['available'])],a['current'][~(a['actual']&d['available'])])
                count=int(sum(p[d['pos'][r['case']]]==r['reference'] for r in slots));assert count==144
                save_json(out/folder/(candidate+'-predictions.json'),p.tolist());retention.append({'candidate':candidate,'fold':f['fold'],'original_correct':99,'slots_correct':144,'strength':model.strength,'features':len(feature_names)})
                for i in a['held']:
                    records.append({**examples[i],'candidate':candidate,'fold':f['fold'],'prediction':int(p[i]),'baseline':int(a['current'][i]),'review':bool(a['actual'][i]),'local_available':bool(a['actual'][i]&d['available'][i])})
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);print({'fold':f['fold'],'configs':4},flush=True)
    results={}
    for candidate in sorted({r['candidate'] for r in records}):
        rows=[r for r in records if r['candidate']==candidate];score=accuracy(rows,'prediction')
        results[candidate]={'accuracy':score,'baseline':accuracy(rows,'baseline'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'coverage':sum(r['covered'] for r in rows),'original_cases_retained':99,'original_slots_retained':144,'target_exceeded':score['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':{str(p):file_hash(p) for p in files},'protocol_ref':digest(protocol),'targets_ref':digest(y.tolist()),'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json')})
    (out/'run.log').write_text('Completed four rationale-free semantic residual fits and score/guarded comparisons; no serving change.\n');print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','cache-audit','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.cache.resolve(),a.cache_audit.resolve(),a.output_dir.resolve())
