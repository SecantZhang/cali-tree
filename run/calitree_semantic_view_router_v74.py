"""Small interpretable judge-selection trees inside explicit review regions."""
import argparse
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from critical.core.calibration.rubric_evidence_v73 import SEMANTIC
from critical.core.calibration.seeded_rubric_v73 import DESCRIPTIONS,REVIEW
from run.calitree_seeded_rubric_v73 import arrays,attach
from run.calitree_semantic_rubric_v70 import STUDY,ROOT,read,fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS,INNER
from run.calitree_accuracy_headroom_v37 import accuracy
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.decision.artifacts import save_json,digest


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,raw,semantic=arrays();pos={e['case']:i for i,e in enumerate(examples)}
    y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples])
    regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);cols={n:i for i,n in enumerate(names)}
    configs=[(family,depth) for family in ('semantic','auxiliary') for depth in (2,4,6)]
    protocol={'version':'semantic-review-view-router-v74','configs':configs,'target':'Over85% requires235/276.',
      'gating':'Regular routing requires disagreement and an explicit same-requirement review condition or a warranted regular alternative to an unwarranted teacher proposal.',
      'selection':'Fit a depth-bounded readable routing tree on source-excluded teacher views. Each regular leaf needs two distinct gain sources and positive fitting benefit. Protect every original actual prediction.',
      'new_paid_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol)
    (out/'run.log').write_text('Review-constrained judge-selection tree comparison in progress.\n');(out/'llm-histories.log').write_text('Zero API calls.\n')
    records=[];retention=[]
    def eligible(matrix):
        review=np.any(matrix[:,[cols[n] for n in REVIEW]],axis=1)
        supported=(matrix[:,cols['view_teacher_unwarranted']]!=0)&(matrix[:,cols['view_regular_warranted']]!=0)
        return (matrix[:,cols['view_disagrees']]!=0)&(review|supported)&valid
    for f in (f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision'):
        train=[pos[c] for c in f['train_cases']];held=[pos[c] for c in f['held_cases']]
        folder=TEACHERS/('fold'+str(f['fold']));saved=read(folder/'predictions.json');ps=np.asarray(saved['support']);oof_ps=ps.copy()
        for inner in range(5):
            cache=INNER/folder.name/('inner'+str(inner));entry=read(cache/'membership.json');excluded=set(entry['held_sources'])
            assert not set(entry['training_sources'])&(excluded|set(groups[held]))
            indices=[i for i in train if groups[i] in excluded];oof_ps[indices]=np.asarray(read(cache/'predictions.json')['support'])[indices]
        full=attach(raw,semantic,ps,regular);training=attach(raw,semantic,oof_ps,regular)
        teacher=np.argmax(ps,axis=1);oof=np.argmax(oof_ps,axis=1);teacher[~valid]=regular[~valid];oof[~valid]=regular[~valid]
        allowed=eligible(training);actual_allowed=eligible(full);fit=[i for i in train if allowed[i]]
        for family,depth in configs:
            selected=[i for i,n in enumerate(names) if n.startswith(('rubric_','view_','meaning_','intent_','requires_','task_')) or (family=='auxiliary' and n.startswith('vision_'))]
            target=(regular==y)&(oof!=y)
            useful=(regular==y)|(oof==y)
            for protected_weight in (1.,5.,25.,125.):
                weight=np.where(useful,1.,.05)*np.where(oof==y,2.,1.)*np.where(np.arange(915)<99,protected_weight,1.)
                model=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=3,random_state=20261023)
                model.fit(training[fit][:,selected],target[fit].astype(int),sample_weight=weight[fit])
                leaves=model.apply(training[fit][:,selected]);approved=set()
                for leaf in set(leaves):
                    rows=[i for i,l in zip(fit,leaves) if l==leaf]
                    gain=[i for i in rows if target[i]];loss=[i for i in rows if oof[i]==y[i] and regular[i]!=y[i]]
                    if len({groups[i] for i in gain})>=2 and len(gain)>2*len(loss) and model.predict(training[rows[:1]][:,selected])[0]==1:
                        approved.add(int(leaf))
                route=np.isin(model.apply(full[:,selected]),list(approved))&actual_allowed
                predicted=np.where(route,regular,teacher)
                if np.all(predicted[:99]==y[:99]):break
            name=family+'_d'+str(depth);local=int(np.sum(predicted[:99]==y[:99]))
            retention.append({'candidate':name,'fold':f['fold'],'original_correct':local,'protected_weight':protected_weight})
            tree=model.tree_
            def node(index):
                if tree.children_left[index]<0:return {'action':'regular' if index in approved else 'teacher'}
                return {'feature':names[selected[int(tree.feature[index])]],'false':node(int(tree.children_left[index])),
                        'true':node(int(tree.children_right[index]))}
            save_json(out/folder.name/(name+'.json'),{'tree':node(0),'review_definitions':{n:DESCRIPTIONS[n] for n in SEMANTIC},
                                                    'approved_regular_leaves':sorted(approved),'upstream_review_gate_required':True})
            # Keep the verified v72 semantic correction ahead of statistical routing.
            v72=SemanticRubricExecutor(read(ROOT/'logs/exps/261023-warranted-rubric-v71-r2'/folder.name/'auxiliary_correct.json'))
            combined=predicted.copy()
            for i in held:
                values={n:bool(raw[i,cols[n]]) for n in v72.artifact['feature_names']}
                semantic_prediction=v72.select(values,int(teacher[i]))['prediction'] if valid[i] else int(regular[i])
                if semantic_prediction!=teacher[i]:combined[i]=semantic_prediction
                records.append({**examples[i],'teacher':int(teacher[i]),'prediction':int(predicted[i]),'combined':int(combined[i]),'candidate':name,'fold':f['fold'],'regular_routed':bool(route[i])})
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
        print({'fold':f['fold'],'held':len(held)},flush=True)
    results={}
    for family,depth in configs:
        name=family+'_d'+str(depth);rows=[r for r in records if r['candidate']==name]
        results[name]={'router':accuracy(rows,'prediction'),'with_v72':accuracy(rows,'combined'),
                       'original_retained':all(r['original_correct']==99 for r in retention if r['candidate']==name),
                       'regular_routed':sum(r['regular_routed'] for r in rows)}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':fingerprint(__file__),'target_ref':digest(y.tolist())})
    (out/'run.log').write_text('Completed six source-held review-constrained router trees and verified-v72 composition. No paid calls.\n')
    print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
