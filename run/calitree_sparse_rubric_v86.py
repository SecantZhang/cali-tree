"""Test one-source semantic warrants on the unchanged source-held comparison.

Observed transfer in cached Sol diagnostics motivates this support ablation;
it does not turn one-source support into a general accuracy guarantee.
"""
import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np

from critical.core.calibration.seeded_rubric_v73 import SeededRubric,Search
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.decision.artifacts import digest,save_json
from run.calitree_seeded_rubric_v73 import arrays,attach
from run.calitree_semantic_rubric_v70 import ROOT,STUDY,read,fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS,INNER
from run.calitree_fallback_routing_v34 import old_inputs,PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

RUBRICS=ROOT/'logs/exps/261023-verified-semantic-hybrid-v72-r1'
CONFIGS=[Search(family=family,max_features=192,min_sources=1,loss_cost=cost) for family in ('semantic','grounded','auxiliary') for cost in (1.,2.)]
CONFIGS += [Search(family=family,mode='grades',max_features=192,min_sources=1,loss_cost=2.) for family in ('semantic','grounded')]


def run(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    examples,names,raw,semantic=arrays();y=np.asarray([e['reference'] for e in examples]);groups=np.asarray([e['source_group'] for e in examples]);regular=np.asarray([e['regular'] for e in examples]);valid=np.asarray([e['covered'] for e in examples]);pos={e['case']:i for i,e in enumerate(examples)}
    protocol={'version':'single-source-warranted-rubric-v86','configs':[asdict(c) for c in CONFIGS],
        'motivation':'Cached independent expert routing transferred a material-collateral/progress region between two held sources only after allowing one positive fitting source. Test the same support choice over all existing semantic warrants.',
        'scope':'Same276 primary cases,84 source groups, five source-held folds; every held-source sibling excluded. No new observations or model calls.',
        'warrants':'A grading rule starts from affirmative No/Partial/Yes evidence; a judge-selection rule starts from a review/defer or unwarranted/warranted disagreement. Uncertainty alone never grades No.',
        'fitting':'Use the same30 inner source-excluded cached teacher views. One positive source is sufficient to propose a rule; every actual original case vetoes harmful rules.',
        'priority':'Existing v72 correction keeps its original teacher context and wins before new rules.',
        'limits':'One-source rules have weak fitting support. Outer-fold transfer and original-case retention are measured explicitly; these are reviewed development cases, not fresh validation.',
        'new_api_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol)
    (out/'run.log').write_text('One-source semantic support ablation started.\n');(out/'llm-histories.log').write_text('Zero API calls or new teacher fits; cached Luna judgments and raw bound semantics only.\n')
    records=[];retention=[];source_hashes={};originals=[r for bank in (1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']]
    prior={r['case']:r for r in read(RUBRICS/'predictions.json')}
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        train=[pos[c] for c in f['train_cases']];held=[pos[c] for c in f['held_cases']];assert not set(groups[train])&set(groups[held])
        folder='fold'+str(f['fold']);teacher=TEACHERS/folder;saved=read(teacher/'predictions.json');ps=np.asarray(saved['support']);oof_ps=ps.copy()
        for inner in range(5):
            path=INNER/folder/('inner'+str(inner));membership=read(path/'membership.json');excluded=set(membership['held_sources'])
            assert not set(membership['training_sources'])&(excluded|set(groups[held]))
            indices=[i for i in train if groups[i] in excluded];oof_ps[indices]=np.asarray(read(path/'predictions.json')['support'])[indices]
        actual=np.argmax(ps,axis=1);oof=np.argmax(oof_ps,axis=1);actual[~valid]=regular[~valid];oof[~valid]=regular[~valid]
        original=read(RUBRICS/folder/'rubric.json');executor=SemanticRubricExecutor(original);columns={n:i for i,n in enumerate(names)}
        current=[];priority=[]
        for i in range(len(examples)):
            result=executor.select({n:bool(raw[i,columns[n]]) for n in original['feature_names']},int(actual[i])) if valid[i] else {'prediction':int(regular[i]),'rule_index':None}
            current.append(result['prediction']);priority.append(result['rule_index'] is not None)
        current=np.asarray(current);priority=np.asarray(priority);assert all(current[i]==prior[examples[i]['case']]['prediction'] for i in held)
        full=attach(raw,semantic,ps,regular);training=attach(raw,semantic,oof_ps,regular);fit=[i for i in train if valid[i]]
        ranking={n:saved['priority'].get(n,0.)+(1000 if n.startswith('meaning_') else 1500 if n.startswith('rubric_') else 0) for n in names}
        for config in CONFIGS:
            name=config.family+'_'+config.mode+'_cost'+str(config.loss_cost)
            rule=SeededRubric(names,config).fit(training[fit],y[fit],groups=groups[fit].tolist(),base=oof[fit],regular=regular[fit],
                protected_X=full[:99],protected_y=y[:99],protected_base=actual[:99],protected_regular=regular[:99],priority=ranking)
            p=np.asarray(rule.predict(full,base=actual,regular=regular));p[priority]=current[priority];p[~valid]=regular[~valid]
            assert np.all(p[:99]==y[:99]);slots=int(sum(p[pos[r['case']]]==r['reference'] for r in originals));assert slots==144
            artifact=rule.artifact(digest(read(teacher/'teacher.json')['contract']));save_json(out/folder/(name+'.json'),artifact);(out/folder/(name+'.txt')).write_text(rule.render())
            retention.append({'candidate':name,'fold':f['fold'],'original_correct':99,'slots_correct':slots,'rules':len(rule.rules),'conditions':sum(len(r['conditions']) for r in rule.rules)})
            for i in held:records.append({**examples[i],'prediction':int(p[i]),'baseline':int(current[i]),'candidate':name,'fold':f['fold']})
        source_hashes[str(teacher/'predictions.json')]=fingerprint(teacher/'predictions.json');source_hashes[str(RUBRICS/folder/'rubric.json')]=fingerprint(RUBRICS/folder/'rubric.json')
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention)
        print({'fold':f['fold'],'held':len(held),'rules':{r['candidate']:r['rules'] for r in retention if r['fold']==f['fold']}},flush=True)
    results={}
    for config in CONFIGS:
        name=config.family+'_'+config.mode+'_cost'+str(config.loss_cost);rows=[r for r in records if r['candidate']==name]
        results[name]={'accuracy':accuracy(rows,'prediction'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'all_original_fits_retained':True,'upstream_evidence_coverage':sum(r['covered'] for r in rows),'target_exceeded':accuracy(rows,'prediction')['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':{str(Path(__file__)):fingerprint(__file__)},'source_hashes':source_hashes,'protocol_ref':digest(protocol),'targets_ref':digest(y.tolist())})
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(__file__).read_bytes())
    (out/'run.log').write_text('Completed eight one-source semantic rubric candidates with all originals/slots retained. No serving change or paid calls.\n');print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
