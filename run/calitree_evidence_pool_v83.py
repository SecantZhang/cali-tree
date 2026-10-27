"""Fixed equal-weight evidence pools with a semantic region route and v72 priority."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.decision.artifacts import digest,save_json
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,data,read,fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

REGION=ROOT/'logs/exps/261023-region-policy-v78-r1'
CAPTION=ROOT/'logs/exps/261023-caption-policy-v80-r1'
RUBRICS=ROOT/'logs/exps/261023-verified-semantic-hybrid-v72-r1'
CONFIGS=('region_mean','region_scoped','caption_mean','joint_mean','joint_scoped')


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,X=data();positions={e['case']:i for i,e in enumerate(examples)}
    y=np.asarray([e['reference'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples])
    # This route certifies computability, not physical truth or a grade.
    eligible=[]
    for e in examples:
        m=read(ROOT/'logs/exps/261023-grounded-regions-v77-r2/cases'/(e['case']+'.json'))['measurements']
        quality={'source_detection_score':.2,'edited_detection_score':.2,'source_binding_margin':.005,'counterpart_margin':.005,'counterpart_similarity':.65}
        eligible.append(m['region_all_plans_bound'] and m['region_all_requirements_supported'] and all(m.get(k) is not None and m[k]>=t for k,t in quality.items()))
    eligible=np.asarray(eligible);originals=[r for bank in (1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']]
    protocol={'version':'semantic-qualified-equal-evidence-pool-v83','configs':CONFIGS,
        'evaluation':'Same276 primary cases and84 sources, five source-held folds, all siblings excluded. No new fits or held-label weight tuning.',
        'pool':'Equal arithmetic mean of normalized teacher and region-Boolean/caption-audit class supports. Lower grade wins exact ties. These are model supports, not factual confidence.',
        'semantic_route':'Region-scoped pools consult the region learner only with complete supported scope and comparative target/reference binding guards. Otherwise omit that learner.',
        'rubric_priority':'Keep each existing v72 semantic correction and its original v69 teacher context. Pool only when the old correction does not fire; never rebind its artifact to the pooled teacher.',
        'local_guarantee':'Every member has the same correct actual argmax for all99 originals. A positive convex pool retains it. Actual144 local slots also replayed.',
        'limits':'Shared inputs mean correlated model errors. This is a reviewed development comparison, not fresh validation or standalone rubric reconstruction.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    records=[];retention=[];sources={}
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision'][:5]:
        folder='fold'+str(f['fold']);train=[positions[c] for c in f['train_cases']];held=[positions[c] for c in f['held_cases']]
        assert not set(groups[train])&set(groups[held])
        teacher=read(TEACHERS/folder/'predictions.json');base=np.asarray(teacher['support']);views={}
        for kind,root,candidate in (('region',REGION,'region_boolean'),('caption',CAPTION,'catboost_d8_caption')):
            path=root/candidate/folder;fit=read(path/'fit.json')
            assert fit['train_cases']==f['train_cases'] and fit['held_cases']==f['held_cases']
            views[kind]=np.asarray(read(path/'support.json'))
            for file in (path/'fit.json',path/'support.json',path/'model.cbm'):sources[str(file)]=fingerprint(file)
        for support in (base,*views.values()):
            assert support.shape==(915,3) and np.all(np.isfinite(support)) and np.allclose(support.sum(axis=1),1.)
            assert np.all(np.argmax(support[:99],axis=1)==y[:99])
        old=np.argmax(base,axis=1);artifact=read(RUBRICS/folder/'rubric.json')
        executor=SemanticRubricExecutor(artifact)
        teacher_artifact=read(TEACHERS/folder/'teacher.json')
        # Outer-fold rubric references bind the complete native fit contract.
        # Keep the old teacher context; do not relabel the pool as its teacher.
        assert artifact['teacher_ref']==digest(teacher_artifact['contract'])
        assert teacher_artifact['contract']['rows']==train
        assert read(RUBRICS/'verification.json')['passed']
        corrected=[];fires=[]
        for i in range(915):
            result=executor.select({n:bool(X[i,names.index(n)]) for n in artifact['feature_names']},int(old[i]))
            corrected.append(result['prediction']);fires.append(result['rule_index'] is not None)
        corrected=np.asarray(corrected);fires=np.asarray(fires)&valid
        for config in CONFIGS:
            if config.startswith('region'):pool=(base+views['region'])/2
            elif config=='caption_mean':pool=(base+views['caption'])/2
            else:pool=(base+views['region']+views['caption'])/3
            if config=='region_scoped':pool[~eligible]=base[~eligible]
            if config=='joint_scoped':pool[~eligible]=(base[~eligible]+views['caption'][~eligible])/2
            p=np.argmax(pool,axis=1);p[fires]=corrected[fires];p[~valid]=regular[~valid]
            assert np.all(p[:99]==y[:99]);slots=int(sum(p[positions[r['case']]]==r['reference'] for r in originals));assert slots==144
            retention.append({'candidate':config,'fold':f['fold'],'original_correct':99,'slots_correct':slots})
            for i in held:records.append({**examples[i],'prediction':int(p[i]),'candidate':config,'fold':f['fold'],'region_qualified':bool(eligible[i]),'v72_priority_fired':bool(fires[i])})
        for file in (TEACHERS/folder/'predictions.json',RUBRICS/folder/'rubric.json'):sources[str(file)]=fingerprint(file)
    results={}
    for name in CONFIGS:
        rows=[r for r in records if r['candidate']==name]
        assert len(rows)==len({r['case'] for r in rows})==276
        results[name]={'accuracy':accuracy(rows,'prediction'),'region_qualified':sum(r['region_qualified'] for r in rows),'upstream_evidence_coverage':sum(r['covered'] for r in rows),
            'all_original_fits_retained':True,'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);save_json(out/'results.json',results);save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
    save_json(out/'manifest.json',{'code_sha256':{str(Path(__file__)):fingerprint(__file__)},'source_hashes':sources,'protocol_ref':digest(protocol)})
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(__file__).read_bytes())
    (out/'run.log').write_text('Completed fixed equal-weight source-held pools with v72 priority, all originals/slots retained. No fits or new model calls.\n');(out/'llm-histories.log').write_text('Zero API calls or new inference. Frozen source-excluded probability tables only.\n')
    print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
