"""Replay completed local-evidence studies and actual protected training slots."""
import argparse
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier
from scipy.special import softmax

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision import nli_rubric_v81 as nli
from critical.vision import grounded_regions_v77 as regions
from critical.vision import caption_audit_v79 as caption
from run.calitree_region_policy_v78 import arrays
from run.calitree_caption_policy_v80 import load as caption_arrays
from run.calitree_seeded_rubric_v73 import arrays as semantic_arrays,attach
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read,fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_accuracy_headroom_v37 import accuracy


def audit(kind,study,out):
    if out.exists():raise ValueError('Fresh audit directory required')
    manifest=read(study/'manifest.json')
    for path,sha in manifest['code_sha256'].items():assert fingerprint(path)==sha,path
    if kind=='region':examples,names,X,_,_,B,rnames,R=arrays()
    elif kind=='caption':examples,names,X,rnames,R,_=caption_arrays()
    else:examples,names,X,semantic=semantic_arrays()
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);position={e['case']:i for i,e in enumerate(examples)}
    folds={f['fold']:f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision'}
    originals=[item for bank in (1,2,3) for item in old_inputs(PREVIOUS,bank)[3]['local']];assert len(originals)==144
    predicted={(r['candidate'],r['case']):r for r in read(study/'predictions.json')}
    checks=[];rows=[];native=0
    if kind in ('region','caption'):
        for file in sorted(study.glob('*/fold*/fit.json')):
            fit=read(file);config=fit['config'];candidate=file.parent.parent.name;fold=fit['fold'];f=folds[fold]
            assert fit['train_cases']==f['train_cases'] and fit['held_cases']==f['held_cases']
            if kind=='region':
                selected=[i for i,n in enumerate(names) if config!='meaning_region_numeric' or n.startswith(('meaning_','task_','requires_','intent_','rationale_','judge_','evidence_','vision_'))]
                features=[names[i] for i in selected]+(list(regions.SPECS) if config=='region_boolean' else rnames)
                matrix=np.concatenate([X[:,selected],B if config=='region_boolean' else R],axis=1)
                model_file=file.parent/'model.cbm'
            else:
                features=names+rnames if config['features']=='caption_region' else names
                matrix=np.concatenate([X,R],axis=1) if config['features']=='caption_region' else X
                model_file=file.parent/'model.cbm'
            train=[position[c] for c in f['train_cases']];held=[position[c] for c in f['held_cases']]
            assert not set(groups[train])&set(groups[held])
            cols=feature_columns(features,matrix,train,'dedup_noexpert');assert fit['columns']==[features[c] for c in cols]
            M=matrix[:,cols]
            assert digest([[float(v) if np.isfinite(v) else None for v in row] for row in M[train]])==fit['matrix_ref']
            assert digest(y[train].tolist())==fit['targets_ref']
            support=np.asarray(read(file.parent/'support.json'))
            if model_file.exists():
                model=CatBoostClassifier();model.load_model(str(model_file));native+=1
                assert np.allclose(model.predict_proba(M),support,rtol=0,atol=1e-12)
                params=model.get_all_params();assert params['depth']==8 and params['iterations']==1200 and params['random_seed']==20261021
            p=np.argmax(support,axis=1);p[~valid]=regular[~valid]
            assert int(np.sum(p[:99]==y[:99]))==fit['original_correct']==99
            slots=int(sum(p[position[r['case']]]==r['reference'] for r in originals));assert slots==144
            for i in held:
                expected=predicted[candidate,examples[i]['case']];assert p[i]==expected['prediction'];rows.append(expected)
            checks.append({'candidate':candidate,'fold':fold,'native_replayed':model_file.exists(),'original_correct':99,'slots_correct':slots})
    else:
        with_nli=read(study/'protocol.json')['with_nli']
        for file in sorted(study.glob('fold*/*.json')):
            artifact=read(file)
            if artifact.get('version')!='additive-semantic-score-correction-v82':continue
            fold=int(file.parent.name[4:]);f=folds[fold];teacher=TEACHERS/file.parent.name
            assert artifact['teacher_ref']==digest(read(teacher/'teacher.json'))
            support=np.asarray(read(teacher/'predictions.json')['support']);full=attach(X,semantic,support,regular)
            values={n:full[:,i] for i,n in enumerate(names)}
            for i,e in enumerate(examples):
                record=read(ROOT/'logs/exps/261023-caption-audit-v79-r1/cases'/(e['case']+'.json'))
                for n in caption.NAMES:
                    if n.startswith('caption_outcome_') and n.endswith('_min'):
                        if n not in values:values[n]=np.full(len(examples),np.nan)
                        values[n][i]=record['measurements'][n] if record['measurements'][n] is not None else np.nan
                if with_nli:
                    r=read(ROOT/'logs/exps/261023-nli-rubric-v81-r2/cases'/(e['case']+'.json'))
                    for n in nli.NAMES:
                        if n.endswith('_neutral'):continue
                        if n not in values:values[n]=np.full(len(examples),np.nan)
                        values[n][i]=r['features'][n] if r['features'][n] is not None else np.nan
            offset=np.log(np.clip(support,1e-9,1.));extra=np.tile(artifact['intercept_no_partial_yes'],(len(examples),1))
            for term in artifact['terms']:
                column=values[term['feature']];z=np.clip((np.where(np.isfinite(column),column,term['mean'])-term['mean'])/term['scale'],-5,5)
                extra+=z[:,None]*np.asarray(term['coefficients_no_partial_yes'])
            p=np.argmax(offset+artifact['strength']*((artifact['temperature']-1)*offset+extra),axis=1);p[~valid]=regular[~valid]
            assert np.all(p[:99]==y[:99]);slots=int(sum(p[position[r['case']]]==r['reference'] for r in originals));assert slots==144
            candidate=file.stem
            for c in f['held_cases']:
                expected=predicted[candidate,c];assert p[position[c]]==expected['prediction'];rows.append(expected)
            checks.append({'candidate':candidate,'fold':fold,'explicit_equation_replayed':True,'original_correct':99,'slots_correct':slots})
    candidates=sorted({r['candidate'] for r in rows});metrics={}
    for candidate in candidates:
        rs=[r for r in rows if r['candidate']==candidate]
        assert len(rs)==len({r['case'] for r in rs})==276 and len({r['source_group'] for r in rs})==84
        assert sum(r['covered'] for r in rs)==273
        metrics[candidate]=accuracy(rs,'prediction')
    expected_candidates=set(read(study/'results.json'));assert set(candidates)==expected_candidates
    for c,score in metrics.items():assert score==read(study/'results.json')[c]['accuracy']
    result={'passed':True,'kind':kind,'candidates':metrics,'native_models_replayed':native,'fits_with_retained_originals_and_slots':len(checks),
        'original_cases_per_fit':99,'original_slots_per_fit':144,'upstream_coverage':273,'new_api_calls':0,'reserved_sources_used':0,
        'scope':'Native CatBoost inference and explicit score equations replayed; failed histogram candidates have cached-support/membership/metric checks only. No serving or promotion claim.'}
    out.mkdir(parents=True);save_json(out/'retention.json',checks)
    save_json(out/'manifest.json',{'auditor_sha256':fingerprint(__file__),'study_manifest_sha256':fingerprint(study/'manifest.json')})
    (out/'run.log').write_text('Completed independent local-evidence replay: '+str(result)+'\n');(out/'llm-histories.log').write_text('Zero API calls or new extraction/fitting.\n')
    save_json(out/'verification.json',result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=('region','caption','score'),required=True);p.add_argument('--study',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();audit(a.kind,a.study.resolve(),a.output_dir.resolve())
