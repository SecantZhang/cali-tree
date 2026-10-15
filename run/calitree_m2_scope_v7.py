"""Freeze one scoped candidate before any supplementary development calls."""
import argparse
import math
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.calibration.semantic_hierarchy.scoped_policy_v7 import ScopedSemanticPolicy
from critical.core.calibration.semantic_hierarchy.interpreted_tree_v6 import metrics
from run.calitree_m2_generalize_v6 import fit_job,PROFILES
from run.calitree_single_call import ROOT,read,fingerprint

SOURCE=ROOT/'logs/exps/261014-m2-generalization-interpreted-v6'
ORDER=('meaning_depth5_support3','meaning_depth6_support3','meaning_depth5_support2','meaning_depth6_support2','physical_baseline')


def exact(path,value):
    if path.exists():
        if read(path)!=value:raise ValueError('Frozen scoped candidate changed')
    else:save_json(path,value)


def build(rows):
    candidates=[];selected=None
    for profile in ORDER:
        a=fit_job((str(SOURCE),rows,profile,True));correct=a['policy']['training']['metrics']['correct']
        candidates.append({'profile':profile,'fit_ref':a['fit_ref'],'correct':correct,'total':len(rows)})
        if correct>0.9*len(rows):selected=a;break
    if selected is None:raise ValueError('No local policy reaches the accepted fitting floor')
    model=ScopedSemanticPolicy().fit(rows,selected['policy'],selected['profile'])
    return {'model':model.metadata(),'local_selection':candidates,'fit_sources':sorted(r['source_group'] for r in rows)}


def evaluate(context,rows):
    ps=ScopedSemanticPolicy.restore(context['model']).predict_records([r['features'] for r in rows])
    return {'metrics':metrics([p['prediction'] for p in ps],[r['reference'] for r in rows]),
            'cases':[{'case':r['case'],'reference':r['reference'],'source_group':r['source_group'],**p} for r,p in zip(rows,ps)],
            'fallback_count':sum(p['fallback'] for p in ps)}


def run(out):
    out.mkdir(parents=True,exist_ok=True);data=read(SOURCE/'data.json');rows=data['train']
    protocol={'version':'m2-scoped-semantic-v7.1','profile_priority':ORDER,'fit_floor':'strictly greater than 90% including failures',
        'fallback':'Depth-two semantic-only CART, minimum three source cases per leaf, random seed 2718',
        'scope':'Exact requested-outcome-kind set represented in the reached local leaf',
        'selection':'Fixed priority uses fitting accuracy only; no held-out labels at selection or routing.',
        'honesty':'Developed after exploratory probes on the 48 training sources; their OOF metrics are development evidence. Freeze before separately authorized dev12 evaluation.',
        'missing_interpretation':'Abstain when the selected local or fallback policy requires interpretation and that stage is missing; uncertain categories inside a valid interpretation remain valid features.',
        'new_model_calls':0,'reserved_test_predictions':0}
    exact(out/'protocol.json',protocol)
    files=[Path(__file__).resolve(),ROOT/'critical/core/calibration/semantic_hierarchy/scoped_policy_v7.py',
        ROOT/'critical/core/calibration/semantic_hierarchy/interpreted_features_v6.py',ROOT/'critical/core/calibration/semantic_hierarchy/interpreted_tree_v6.py']
    manifest={'protocol_ref':digest(protocol),'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in files},
              'source_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in [SOURCE/'data.json',SOURCE/'results.json',SOURCE/'manifest.json']}}
    exact(out/'manifest.json',manifest)
    for source in files:
        target=out/'source_snapshot'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert fingerprint(target)==fingerprint(source)
        else:shutil.copyfile(source,target)
    full=build(rows);exact(out/'frozen_context.json',full)
    folds={};oof=[]
    for held in ('G1','G2','G3','G4'):
        fitting=[r for r in rows if r['batch']!=held];test=[r for r in rows if r['batch']==held]
        context=build(fitting);assert not set(context['fit_sources'])&{r['source_group'] for r in test}
        score=evaluate(context,test);folds[held]={'context':context,'result':score};oof+=score['cases']
    result={'training':evaluate(full,rows),'outer_folds':folds,
            'oof_metrics':metrics([r['prediction'] for r in oof],[r['reference'] for r in oof]),
            'oof_fallback_count':sum(r['fallback'] for r in oof),'development12':'not evaluated; additional interpretation calls not yet authorized',
            'new_model_calls':0,'reserved_test_predictions':0}
    exact(out/'results.json',result)
    print({'training':result['training']['metrics'],'oof':result['oof_metrics'],'fallbacks':result['oof_fallback_count']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
