"""Compare caption-audited semantic policies without changing the evaluation."""
import argparse
from pathlib import Path
import shutil
import time

import numpy as np
from catboost import CatBoostClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

from critical.vision import caption_audit_v79 as audit
from critical.core.decision.artifacts import digest,save_json
from run.calitree_region_policy_v78 import arrays,REGIONS
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read,fingerprint
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_accuracy_headroom_v37 import accuracy

CAPTIONS=ROOT/'logs/exps/261023-caption-audit-v79-r1'
CONFIGS=({'family':'hist','depth':3,'features':'caption'},
         {'family':'hist','depth':5,'features':'caption_region'},
         {'family':'catboost','depth':8,'features':'caption'},
         {'family':'catboost','depth':8,'features':'caption_region'})


def load():
    examples,names,X,raw,records,boolean,region_names,region_values=arrays()
    identity=digest(read(CAPTIONS/'identity.json'));rows=[]
    for e,r in zip(examples,raw):
        c=read(CAPTIONS/'cases'/(e['case']+'.json'))
        assert c['program_ref']==r['program']['program_ref'] and c['identity_ref']==identity
        if r['observation']:assert c['image_pair_ref']==r['observation']['image_pair_ref']
        rows.append(c)
    matrix=np.asarray([[r['measurements'][n] for n in audit.NAMES] for r in rows],dtype=np.float32)
    availability=np.asarray([[r['measurements'][f'caption_{role}_goal_source_min'] is not None for role in audit.ROLES] for r in rows],dtype=np.float32)
    return examples,names+['caption_'+r+'_available' for r in audit.ROLES]+list(audit.NAMES),np.concatenate([X,availability,matrix],axis=1),region_names,region_values,rows


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,X,rnames,R,caption_rows=load()
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples])
    position={e['case']:i for i,e in enumerate(examples)}
    folds=[f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']
    protocol={'version':'caption-audited-semantic-policy-v80','configs':CONFIGS,
        'evaluation':'Same276 primary cases/84 sources/five source-held folds; all siblings excluded. Include failures through unchanged regular fallback.',
        'inputs':'Existing v69 named evidence, plus bound question/caption pixel-audit scalars and optionally localized region scalars; no embeddings, coordinates, case/source/editor IDs or object/color identity inputs.',
        'model_opinions':'Caption agreement and region affinity are fallible model views, never truth or a grading warrant by themselves.',
        'numeric_missing':'NaN means unavailable, with separate availability flags.',
        'models':'Deterministic depth8/1200 CatBoost control; faster shallow histogram boosting depth3or5/600iterations/minleaf8. Original weight1,5,25 chosen by local retention only.',
        'promotion':'Must exceed235/276 and retain99/99 originals; no full-data artifact or semantic-equivalence claim unless independently verified.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol)
    files=[Path(__file__),ROOT/'critical/vision/caption_audit_v79.py',ROOT/'run/calitree_region_policy_v78.py']
    hashes={str(p):fingerprint(p) for p in files}
    for p in files:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    (out/'run.log').write_text('Caption policy comparison started.\n');(out/'llm-histories.log').write_text('Zero API calls, uploads or reserved-source use. Existing bound descriptions audited with frozen local encoder.\n')
    records=[];results={};retention=[]
    for config in CONFIGS:
        name=config['family']+'_d'+str(config['depth'])+'_'+config['features']
        matrix=np.concatenate([X,R],axis=1) if config['features']=='caption_region' else X
        features=names+rnames if config['features']=='caption_region' else names
        rows=[]
        for fold in folds[:5]:
            train=[position[c] for c in fold['train_cases']];held=[position[c] for c in fold['held_cases']]
            assert not set(groups[train])&set(groups[held])
            cols=feature_columns(features,matrix,train,'dedup_noexpert');M=matrix[:,cols];started=time.monotonic()
            trials=[]
            for weight in (1.,5.,25.):
                if config['family']=='catboost':
                    model=CatBoostClassifier(loss_function='MultiClass',depth=config['depth'],iterations=1200,learning_rate=.05,l2_leaf_reg=3.,random_seed=20261021,thread_count=2,verbose=False,allow_writing_files=False,bootstrap_type='No',random_strength=0.)
                else:
                    model=HistGradientBoostingClassifier(max_iter=600,max_depth=config['depth'],max_leaf_nodes=2**config['depth'],min_samples_leaf=8,learning_rate=.05,l2_regularization=3.,early_stopping=False,random_state=20261023)
                with threadpool_limits(limits=2):
                    model.fit(M[train],y[train],sample_weight=np.where(np.asarray(train)<99,weight,1.))
                    support=model.predict_proba(M)
                p=np.argmax(support,axis=1);p[~valid]=regular[~valid];correct=int(np.sum(p[:99]==y[:99]));trials.append({'weight':weight,'original_correct':correct})
                if correct==99:break
            folder=out/name/('fold'+str(fold['fold']));folder.mkdir(parents=True)
            if config['family']=='catboost':model.save_model(str(folder/'model.cbm'))
            save_json(folder/'support.json',support.tolist())
            save_json(folder/'fit.json',{'config':config,'fold':fold['fold'],'train_cases':fold['train_cases'],'held_cases':fold['held_cases'],
                'columns':[features[c] for c in cols],'matrix_ref':digest([[float(v) if np.isfinite(v) else None for v in row] for row in M[train]]),
                'targets_ref':digest(y[train].tolist()),'weight_trials':trials,'original_correct':correct,'elapsed_seconds':time.monotonic()-started})
            retention.append({'candidate':name,'fold':fold['fold'],'original_correct':correct,'features':len(cols)})
            for i in held:rows.append({**examples[i],'prediction':int(p[i]),'candidate':name,'fold':fold['fold']})
            print({'candidate':name,'fold':fold['fold'],'correct':int(np.sum(p[held]==y[held])),'held':len(held),'original_correct':correct,'seconds':round(time.monotonic()-started,1)},flush=True)
        results[name]={'accuracy':accuracy(rows,'prediction'),'all_original_fits_retained':all(r['original_correct']==99 for r in retention if r['candidate']==name),
            'upstream_evidence_coverage':sum(r['covered'] for r in rows),'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
        records.extend(rows);save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);save_json(out/'results.json',results)
        print({name:results[name]},flush=True)
    assert all(fingerprint(p)==h for p,h in hashes.items())
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'code_sha256':hashes,'caption_identity_ref':digest(read(CAPTIONS/'identity.json')),
        'caption_records_ref':digest(caption_rows),'region_identity_ref':digest(read(REGIONS/'identity.json')),'targets_ref':digest(y.tolist())})
    (out/'run.log').write_text('Completed all four fixed-fold comparisons. Results are development data after repeated model selection; no untouched-test or executable-rubric equivalence claim.\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
