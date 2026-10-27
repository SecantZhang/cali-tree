"""Fit fully additive semantic policies on cached source-held inputs."""
import argparse
from pathlib import Path
import shutil
import time
import warnings

import numpy as np

from critical.core.calibration.additive_tables_v140 import export,AdditiveTables
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT
from critical.core.calibration.semantic_rubric_v70 import DESCRIPTIONS
from critical.core.decision.artifacts import digest,save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load,fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,VISION,read
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

CONFIGS=[(strategy,interactions) for strategy in('boolean128','semantic64_numeric') for interactions in(0,32)]
COMPOSITIONS=('prior','current')
BLENDS=(.5,1.)
WEIGHTS=(1.,5.,25.)
INCUMBENT=ROOT/'logs/exps/261023-semantic-residual-v103-r1'


def run(cache,cache_audit,out):
    if out.exists():raise ValueError('Fresh additive-policy study required')
    from interpret.glassbox import ExplainableBoostingClassifier
    import interpret
    assert interpret.__version__=='0.7.8'
    d=load(cache,cache_audit);examples=d['examples']
    # Use the exact v69 primitive semantic/vision Boolean matrix, rather than
    # the correction-specific dynamic teacher-view columns.
    from run.calitree_semantic_rubric_v70 import data
    same,primitive_names,primitive=data();assert same==examples
    y=d['y'];regular=d['regular'];valid=d['valid'];positions=d['pos']
    measures=[read(VISION/'cases'/(e['case']+'.json'))['measurements'] for e in examples]
    numeric_keys=[k for k,v in measures[0].items() if k!='property_probe_available']
    numeric_names=['score_'+k for k in numeric_keys]+['score_property_probe_available']
    numeric=np.asarray([[m[k] for k in numeric_keys]+[int(m['property_probe_available'])] for m in measures],dtype=float)
    descriptions={**DESCRIPTIONS,'evidence_missing':'Bound semantic evidence is unavailable.',
        **{'judge_predicts_'+label:'The independent regular visual judge proposes '+label+'; this is a model opinion, not an image fact.' for label in('unresolved','no','partial','yes')},
        **{n:'The input-relative '+n.removeprefix('score_').replace('_',' ')+' from the frozen SigLIP2 encoder; similarity is not a factual oracle.' for n in numeric_names}}
    protocol={'version':'additive-semantic-policy-v140','interpret_version':'0.7.8','configs':CONFIGS,'compositions':COMPOSITIONS,'blends':BLENDS,'original_weights':WEIGHTS,
        'data':'Same915 cached inputs/five source folds plus full fit; no raw embeddings, IDs, coordinates or object/property-value identities. Top primitive features ranked only by each fitting teacher importance.',
        'models':'Multiclass additive EBM,2000 rounds, learning_rate .03, at most32 pairwise terms, validation_size0, outer_bags1, max_bins32, max_interaction_bins8, min_samples_leaf2, two CPU workers, fixed seed.',
        'retention':'For each blend/composition, first weight1/5/25 retaining all99 actual original decisions wins. If none retains them, mark that arm ineligible. No held labels choose weight or features.',
        'composition':'Prior keeps old v72/v87 locked routes. Current additionally keeps the existing v112 semantic overrides. Other covered inputs use .5/1 blend of old teacher and EBM. Missing bound evidence keeps regular fallback.',
        'explanation':'Export every native term, including multiclass pairs omitted by the library global visualizer; verify portable table probabilities against the native model before evaluation.',
        'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Complete cached inputs accepted; CPU additive-policy comparison started.\n');(out/'llm-histories.log').write_text('No neural/API/encoder calls. Cached primitive semantic/vision values only.\n')
    files=[Path(__file__),ROOT/'critical/core/calibration/additive_tables_v140.py'];source_hashes={}
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    records=[];retention=[];originals=[r for bank in(1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']]
    for f in[f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f);folder=a['folder'];train=a['train'];held=a['held'];ps=a['ps'];current=np.asarray(read(INCUMBENT/folder/'contextual_depth2_guarded-predictions.json'))
        assert np.all(current[:99]==y[:99]);priority=read(TEACHERS/folder/'predictions.json')['priority']
        for strategy,interactions in CONFIGS:
            allowed=[n for n in priority if n in primitive_names and(strategy=='boolean128' or not n.startswith('vision_'))]
            allowed.sort(key=lambda n:(-priority[n],n));selected=allowed[:128 if strategy=='boolean128' else 64]
            X=primitive[:,[primitive_names.index(n) for n in selected]].astype(float);features=selected
            if strategy=='semantic64_numeric':X=np.concatenate([X,numeric],axis=1);features=features+numeric_names
            stem=strategy+'_pairs'+str(interactions);pending={(composition,blend) for composition in COMPOSITIONS for blend in BLENDS};chosen={}
            for weight in WEIGHTS:
                started=time.monotonic()
                model=ExplainableBoostingClassifier(feature_names=features,feature_types=['continuous']*len(features),max_bins=32,max_interaction_bins=8,interactions=interactions,
                    validation_size=0,outer_bags=1,inner_bags=0,learning_rate=.03,max_rounds=2000,early_stopping_rounds=0,min_samples_leaf=2,n_jobs=2,random_state=20261023)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always');model.fit(X[train],y[train],sample_weight=np.where(np.asarray(train)<99,weight,1.))
                p=model.predict_proba(X);artifact=export(model,features,descriptions);portable=AdditiveTables(artifact).predict_proba(X)
                assert np.allclose(p,portable,atol=1e-12,rtol=0) and np.array_equal(np.argmax(p,axis=1),np.argmax(portable,axis=1))
                save_json(out/folder/(stem+'_weight'+str(weight)+'.json'),artifact)
                save_json(out/folder/(stem+'_weight'+str(weight)+'-fit.json'),{'rows':train,'matrix_ref':digest(X[train].tolist()),'targets_ref':digest(y[train].tolist()),'original_weight':weight,
                    'features':features,'term_features':[list(t) for t in model.term_features_],'elapsed_seconds':time.monotonic()-started,'warnings':[str(w.message) for w in caught]})
                for composition,blend in sorted(pending):
                    locked=a['locked'].copy()
                    baseline=a['current'] if composition=='prior' else current
                    if composition=='current':locked|=current!=a['current']
                    output=baseline.copy();eligible=valid&~locked;output[eligible]=np.argmax((1-blend)*ps[eligible]+blend*p[eligible],axis=1)
                    if np.all(output[:99]==y[:99]):chosen[(composition,blend)]=(weight,output.copy(),artifact['artifact_ref'])
                pending-=set(chosen)
                print({'fold':f['fold'],'candidate':stem,'weight':weight,'pending_retention_arms':len(pending),'elapsed_s':time.monotonic()-started},flush=True)
                if not pending:break
            for composition,blend in[(c,b) for c in COMPOSITIONS for b in BLENDS]:
                candidate=stem+'_'+composition+'_blend'+str(blend);key=(composition,blend)
                if key not in chosen:
                    retention.append({'candidate':candidate,'fold':f['fold'],'eligible':False,'reason':'Original99 actual decisions not all retained at any declared fitting weight.'});continue
                weight,output,ref=chosen[key];count=int(sum(output[positions[r['case']]]==r['reference'] for r in originals));assert count==144
                retention.append({'candidate':candidate,'fold':f['fold'],'eligible':True,'original_correct':99,'slots_correct':144,'weight':weight,'model_ref':ref})
                save_json(out/folder/(candidate+'-predictions.json'),output.tolist())
                for i in held:records.append({**examples[i],'candidate':candidate,'fold':f['fold'],'prediction':int(output[i]),'baseline':int(current[i])})
            source_hashes[str(INCUMBENT/folder/'contextual_depth2_guarded-predictions.json')]=file_hash(INCUMBENT/folder/'contextual_depth2_guarded-predictions.json')
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
    results={}
    for candidate in sorted({r['candidate'] for r in retention}):
        rows=[r for r in records if r['candidate']==candidate];checks=[r for r in retention if r['candidate']==candidate];eligible=len(checks)==6 and all(r['eligible'] for r in checks) and len(rows)==276
        results[candidate]={'eligible':eligible,'scored_rows':len(rows),'accuracy':accuracy(rows,'prediction') if eligible else None,'baseline':accuracy(rows,'baseline') if eligible else None,
            'coverage':sum(r['covered'] for r in rows) if eligible else None,'target_exceeded':eligible and accuracy(rows,'prediction')['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':{str(p):file_hash(p) for p in files},'source_hashes':source_hashes,'protocol_ref':digest(protocol),'targets_ref':digest(y.tolist()),'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json')})
    (out/'run.log').write_text('Completed source-held CPU additive policies. Ineligible local-retention arms are not candidates for promotion; independent runtime audit still required for any improvement.\n');print({k:(v['accuracy']['correct'] if v['eligible'] else 'ineligible') for k,v in results.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','cache-audit','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.cache.resolve(),a.cache_audit.resolve(),a.output_dir.resolve())
