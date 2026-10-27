"""Fit compact semantic score corrections on cached source-excluded teachers."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.rubric_score_v82 import RubricScore
from critical.core.calibration.rubric_evidence_v73 import SPECS
from critical.core.calibration.judge_semantics_v60 import SPECS as LANGUAGE
from critical.core.decision import nli_rubric_v81 as nli
from critical.vision import caption_audit_v79 as caption
from critical.core.decision.artifacts import digest,save_json
from run.calitree_seeded_rubric_v73 import arrays,attach
from run.calitree_warranted_rubric_v71 import TEACHERS,INNER
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read,fingerprint
from run.calitree_accuracy_headroom_v37 import accuracy


def run(out,with_nli=False):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,raw,semantic=arrays();selected=[i for i,n in enumerate(names) if n in SPECS or n in LANGUAGE]
    descriptors={**SPECS,**LANGUAGE};groups=np.asarray([e['source_group'] for e in examples]);y=np.asarray([e['reference'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples])
    extras=[];extra_names=[]
    captions=ROOT/'logs/exps/261023-caption-audit-v79-r1';cidentity=digest(read(captions/'identity.json'))
    keys=[n for n in caption.NAMES if n.startswith('caption_outcome_') and n.endswith('_min')]
    extra_names+=keys;descriptors.update(caption.DESCRIPTIONS)
    for e in examples:
        r=read(captions/'cases'/(e['case']+'.json'));assert r['identity_ref']==cidentity
        extras.append([r['measurements'][n] for n in keys])
    if with_nli:
        folder=ROOT/'logs/exps/261023-nli-rubric-v81-r2';identity=digest(read(folder/'identity.json'))
        extra_names += [n for n in nli.NAMES if not n.endswith('_neutral')];descriptors.update(nli.DESCRIPTIONS)
        for i,e in enumerate(examples):
            r=read(folder/'cases'/(e['case']+'.json'));assert r['identity_ref']==identity
            extras[i]+=[r['features'][n] for n in nli.NAMES if not n.endswith('_neutral')]
    extra=np.asarray(extras,dtype=float);feature_names=[names[i] for i in selected]+extra_names
    position={e['case']:i for i,e in enumerate(examples)}
    configs=[(family,regularization) for family in ('semantic','audited') for regularization in (.01,.1,1.)]
    if with_nli:configs=[('audited',v) for v in (.01,.1,1.)]
    protocol={'version':RubricScore.version,'with_nli':with_nli,'configs':configs,
        'evaluation':'Same276 primary cases/84 sources/five source-held folds with all siblings excluded.',
        'fit':'Use the30 cached inner source-excluded teacher views; actual protected99-case predictions veto correction strength. Equal weight per pixel source.',
        'semantics':'At most24 named concept/view terms plus intercept and explicit teacher temperature. No raw embeddings, identifiers or object names as learned inputs.',
        'retention':'Strength selected from0,.25,.5,.75,1 by fitting-source accuracy after protecting all99 originals. Zero exactly retains the teacher.',
        'limits':'Additive correction to a boosted score, not a standalone semantic distillation or calibrated truth probability.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol)
    files=[Path(__file__),ROOT/'critical/core/calibration/rubric_score_v82.py'];hashes={str(p):fingerprint(p) for p in files}
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    (out/'run.log').write_text('Compact semantic score calibration started.\n');(out/'llm-histories.log').write_text('Zero API calls, new teacher fits, uploads or reserved-source access.\n')
    records=[];retention=[]
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        train=[position[c] for c in f['train_cases']];held=[position[c] for c in f['held_cases']];assert not set(groups[train])&set(groups[held])
        folder=TEACHERS/('fold'+str(f['fold']));full_ps=np.asarray(read(folder/'predictions.json')['support']);oof_ps=full_ps.copy()
        for inner in range(5):
            cache=INNER/folder.name/('inner'+str(inner));entry=read(cache/'membership.json');excluded=set(entry['held_sources'])
            assert not set(entry['training_sources']) & (excluded|set(groups[held]))
            indices=[i for i in train if groups[i] in excluded];oof_ps[indices]=np.asarray(read(cache/'predictions.json')['support'])[indices]
        full=attach(raw,semantic,full_ps,regular)[:,selected];training=attach(raw,semantic,oof_ps,regular)[:,selected]
        fit=[i for i in train if valid[i]]
        for family,reg in configs:
            label=family+'_reg'+str(reg);F=np.concatenate([full,extra],axis=1) if family=='audited' else full;T=np.concatenate([training,extra],axis=1) if family=='audited' else training;N=feature_names if family=='audited' else [names[i] for i in selected]
            model=RubricScore(N,regularization=reg).fit(T[fit],y[fit],support=oof_ps[fit],groups=groups[fit],protected_X=F[:99],protected_y=y[:99],protected_support=full_ps[:99])
            proposed=np.argmax(model.predict_proba(F,support=full_ps),axis=1);proposed[~valid]=regular[~valid]
            assert np.all(proposed[:99]==y[:99])
            artifact={**model.artifact(descriptors),'teacher_ref':digest(read(folder/'teacher.json'))};save_json(out/folder.name/(label+'.json'),artifact)
            retention.append({'candidate':label,'fold':f['fold'],'original_correct':99,'strength':model.strength,'features':len(model.columns)})
            for i in held:records.append({**examples[i],'prediction':int(proposed[i]),'teacher':int(np.argmax(full_ps[i])) if valid[i] else int(regular[i]),'candidate':label,'fold':f['fold']})
        print({'fold':f['fold'],'held':len(held)},flush=True)
    results={}
    for family,reg in configs:
        name=family+'_reg'+str(reg);rows=[r for r in records if r['candidate']==name]
        results[name]={'accuracy':accuracy(rows,'prediction'),'gains':sum(r['prediction']==r['reference']!=r['teacher'] for r in rows),'losses':sum(r['teacher']==r['reference']!=r['prediction'] for r in rows),
            'all_original_fits_retained':True,'upstream_evidence_coverage':sum(r['covered'] for r in rows),'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
    assert all(fingerprint(p)==h for p,h in hashes.items())
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'code_sha256':hashes,'caption_identity_ref':cidentity,'nli_used':with_nli,'targets_ref':digest(y.tolist())})
    (out/'run.log').write_text('Completed source-held compact semantic score calibration; all99 originals retained in all six fits. See measured results.json; no serving change.\n');print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--with-nli',action='store_true')
    a=p.parse_args();run(a.output_dir.resolve(),a.with_nli)
