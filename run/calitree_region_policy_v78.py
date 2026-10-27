"""Compare bound region measurements under the fixed source-held protocol."""
import argparse
from dataclasses import asdict
from pathlib import Path
import shutil
import time

import numpy as np
from catboost import CatBoostClassifier

from critical.core.calibration.region_expert_v78 import PROFILES, proposal, CONTRACT_REF
from critical.vision import grounded_regions_v77 as regions
from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_rubric_v70 import data, ROOT, FROZEN, STUDY, read, fingerprint
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_accuracy_headroom_v37 import accuracy

REGIONS=ROOT/'logs/exps/261023-grounded-regions-v77-r2'
CONFIGS=('region_boolean','region_numeric','meaning_region_numeric')


def arrays():
    examples,names,X=data();raw=read(FROZEN/'replay_inputs_without_references.json')
    records=[]
    identity=digest(read(REGIONS/'identity.json'))
    for e,r in zip(examples,raw):
        record=read(REGIONS/'cases'/(e['case']+'.json'))
        assert record['identity_ref']==identity and record['program_ref']==r['program']['program_ref']
        assert record['features']==regions.predicates(record['measurements'])
        if r['observation']:assert record['image_pair_ref']==r['observation']['image_pair_ref']
        records.append(record)
    boolean=np.asarray([[int(r['features'][n]) for n in regions.SPECS] for r in records],dtype=np.float32)
    numeric_names=[n for n in regions.SPECS if n.endswith('_available') or n in ('region_all_plans_bound','region_all_requirements_supported')]
    numeric=np.asarray([[int(r['features'][n]) for n in numeric_names]+[r['measurements'].get(n) for n in regions.BOUNDS] for r in records],dtype=np.float32)
    return examples,names,X,raw,records,boolean,numeric_names+['score_region_'+n for n in regions.BOUNDS],numeric


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,X,raw,regions_data,boolean,numeric_names,numeric=arrays()
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples])
    regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples])
    position={e['case']:i for i,e in enumerate(examples)}
    folds=[f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']
    out.mkdir(parents=True)
    protocol={'version':'grounded-region-policy-v78','configs':CONFIGS,
        'evaluation':'Unchanged276 primary cases,84 pixel sources, five fixed source-held folds; all source siblings excluded.',
        'inputs':'V69 closed semantic predicates plus input-relative detector/crop/color/geometry comparisons. No boxes, embeddings, source/editor/case identity or requested object/color identity predictors.',
        'numerical_missing':'NaN means unavailable; separate availability predicates. Undetected never establishes physical absence.',
        'model':'Same deterministic1200-iteration depth8 CatBoost and training-only original weight1,5,25; feature dedup uses fitting rows only.',
        'rubric_control':'Four explicit region proposal profiles are diagnostic opinions, not promoted overrides. Frozen before their paired comparison.',
        'coverage':'Unchanged bound-evidence gate; all failed/unavailable cases included through regular fallback.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    save_json(out/'protocol.json',protocol)
    files=[Path(__file__),ROOT/'critical/core/calibration/region_expert_v78.py',ROOT/'critical/vision/grounded_regions_v77.py']
    hashes={str(p):fingerprint(p) for p in files}
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    (out/'run.log').write_text('Local region policy comparison started.\n');(out/'llm-histories.log').write_text('Zero model API calls or uploads. Frozen local detector/encoder records only.\n')
    controls=[]
    baseline=[r for r in read(STUDY/'predictions.json') if r['candidate']=='boost_full_vision']
    for profile in PROFILES:
        rows=[]
        for b in baseline:
            i=position[b['case']];p=proposal(raw[i]['program'],regions_data[i],dict(zip(names,map(bool,X[i]))),profile)
            label=p['prediction'] if p['prediction']>=0 and valid[i] else b['direct']
            rows.append({'case':b['case'],'reference':b['reference'],'teacher':b['direct'],'proposal':p,'prediction':label})
        controls.append({'profile':asdict(profile),'accuracy':accuracy(rows,'prediction'),
            'gains':sum(r['prediction']==r['reference']!=r['teacher'] for r in rows),
            'losses':sum(r['teacher']==r['reference']!=r['prediction'] for r in rows),'rows':rows})
    save_json(out/'explicit_rubric_controls.json',controls)
    results={};predictions=[];checks=[]
    for config in CONFIGS:
        selected=[i for i,n in enumerate(names) if config!='meaning_region_numeric' or n.startswith(('meaning_','task_','requires_','intent_','rationale_','judge_','evidence_','vision_'))]
        feature_names=[names[i] for i in selected]+(list(regions.SPECS) if config=='region_boolean' else numeric_names)
        matrix=np.concatenate([X[:,selected],boolean if config=='region_boolean' else numeric],axis=1)
        rows=[]
        for f in folds:
            train=[position[c] for c in f['train_cases']];held=[position[c] for c in f['held_cases']]
            assert not set(groups[train])&set(groups[held])
            cols=feature_columns(feature_names,matrix,train,'dedup_noexpert');M=matrix[:,cols]
            folder=out/config/('fold'+str(f['fold']));folder.mkdir(parents=True)
            started=time.monotonic();trials=[]
            for weight in (1.,5.,25.):
                model=CatBoostClassifier(loss_function='MultiClass',depth=8,iterations=1200,learning_rate=.05,l2_leaf_reg=3.,random_seed=20261021,thread_count=2,verbose=False,allow_writing_files=False,bootstrap_type='No',random_strength=0.)
                model.fit(M[train],y[train],sample_weight=np.where(np.asarray(train)<99,weight,1.))
                support=model.predict_proba(M);p=np.argmax(support,axis=1);p[~valid]=regular[~valid]
                correct=int(np.sum(p[:99]==y[:99]));trials.append({'weight':weight,'original_correct':correct})
                if correct==99:break
            model.save_model(str(folder/'model.cbm'))
            save_json(folder/'fit.json',{'config':config,'fold':f['fold'],'train_cases':f['train_cases'],'held_cases':f['held_cases'],
                'columns':[feature_names[c] for c in cols],'matrix_ref':digest([[float(v) if np.isfinite(v) else None for v in row] for row in M[train]]),'targets_ref':digest(y[train].tolist()),
                'weight_trials':trials,'original_correct':correct,'elapsed_seconds':time.monotonic()-started})
            save_json(folder/'support.json',support.tolist())
            checks.append({'candidate':config,'fold':f['fold'],'original_correct':correct,'features':len(cols)})
            for i in held:rows.append({**examples[i],'prediction':int(p[i]),'candidate':config,'fold':f['fold']})
            print({'candidate':config,'fold':f['fold'],'held':len(held),'correct':int(np.sum(p[held]==y[held])),'original_correct':correct,'seconds':round(time.monotonic()-started,1)},flush=True)
        results[config]={'accuracy':accuracy(rows,'prediction'),'all_original_fits_retained':all(c['original_correct']==99 for c in checks if c['candidate']==config),
            'upstream_evidence_coverage':sum(r['covered'] for r in rows),'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
        predictions.extend(rows);save_json(out/'predictions.json',predictions);save_json(out/'results.json',results);save_json(out/'retention.json',checks)
        print({config:results[config]},flush=True)
    assert all(fingerprint(p)==h for p,h in hashes.items())
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'code_sha256':hashes,'region_identity_ref':digest(read(REGIONS/'identity.json')),
        'region_records_ref':digest(regions_data),'region_expert_contract_ref':CONTRACT_REF,'base_matrix_ref':digest(X.tolist()),'targets_ref':digest(y.tolist())})
    (out/'run.log').write_text('All three configurations completed over fixed folds; explicit physical rubric controls recorded. See results.json for measured accuracy, with all cases included. No promotion or serving change.\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
