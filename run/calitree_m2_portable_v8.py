"""Fit semantic, case-independent M2 rules under the user's clarified objective."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import from_interpreted,CONTRACT_REF,SPECS
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree,LIMITS,metrics
from run.calitree_single_call import ROOT,read,fingerprint

SOURCE=ROOT/'logs/exps/261014-m2-generalization-interpreted-v6'
PROFILES={f'depth{d}_support{s}':{**LIMITS,'max_depth':d,'min_leaf_sources':s}
          for d,s in [(4,3),(5,3),(6,3),(7,3),(5,2),(6,2)]}
VERSION='m2-portability-first-v8'


def exact(path,value):
    if path.exists():
        if read(path)!=value:raise ValueError('Frozen portability experiment changed')
    else:save_json(path,value)


def prepare(out):
    out.mkdir(parents=True,exist_ok=True)
    protocol={'version':VERSION,'feature_contract_ref':CONTRACT_REF,'profiles':PROFILES,
       'user_clarification':'Generalizability means rules should not be too specific to the case input; held-out accuracy is not the acceptance gate before large-corpus training.',
       'local_fit_floor':'Strictly above 90% over all 48 cases, including the original missing observation: at least 44 correct.',
       'allowed':'Instruction operation kinds, semantic progress/endpoints/materiality, and any/all physical evidence predicates.',
       'prohibited':'Case identifiers, object/instruction literals, image hashes, pixel coordinates, raw check counts, majority thresholds, exact observed-case signature routing.',
       'selection':'Qualify by training floor; prefer larger minimum source support, then fewer nodes, shallower depth, more correct training cases, profile name. No held-out metric is used.',
       'scope':'Semantic portability and local fit are the target. Held-out performance and LLM repeat/paraphrase robustness are not established by these checks.',
       'new_model_calls':0,'reserved_test_predictions':0}
    exact(out/'protocol.json',protocol)
    sources=[SOURCE/'data.json',SOURCE/'manifest.json',SOURCE/'results.json']
    code=[Path(__file__).resolve(),ROOT/'critical/core/calibration/semantic_hierarchy/portable_features_v8.py',
          ROOT/'critical/core/calibration/semantic_hierarchy/portable_tree_v8.py',
          ROOT/'critical/core/calibration/semantic_hierarchy/interpreted_features_v6.py',
          ROOT/'critical/core/calibration/semantic_hierarchy/stable_features_v5.py']
    manifest={'version':VERSION,'protocol_ref':digest(protocol),'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in code},
              'source_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in sources}}
    exact(out/'manifest.json',manifest)
    for source in code:
        target=out/'source_snapshot'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert fingerprint(target)==fingerprint(source)
        else:shutil.copyfile(source,target)
    rows=[{**deepcopy(r),'features':from_interpreted(r['features'])} for r in read(SOURCE/'data.json')['train']]
    exact(out/'data.json',{'train':rows});return rows


def job(args):
    out,rows,name,replay=args;path=Path(out)/'fits'/(name+'.json')
    if path.exists():
        model=PortableSemanticTree.restore(read(path));ordered=sorted(rows,key=lambda r:r['source_group']);t=model.metadata()['training']
        assert t['source_groups']==[r['source_group'] for r in ordered]
        assert t['target_ref']==digest([r['reference'] for r in ordered])
        assert t['feature_ref']==digest([r['features'] for r in ordered])
        return model.metadata()
    if replay:raise ValueError('Missing portable fit')
    model=PortableSemanticTree(limits=PROFILES[name]).fit([r['features'] for r in rows],[r['reference'] for r in rows],
        source_groups=[r['source_group'] for r in rows],source_batches=[r['batch'] for r in rows])
    exact(path,model.metadata());path.with_suffix('.txt').write_text(model.render()+'\n')
    print({'profile':name,'correct':model.metadata()['training']['metrics']['correct'],'nodes':model.metadata()['search']['nodes'],
           'states':model.metadata()['search']['states'],'budget_exhausted':model.metadata()['search']['budget_exhausted']},flush=True)
    return model.metadata()


def run(out,replay=False):
    rows=prepare(out);jobs=[(str(out),rows,name,replay) for name in PROFILES]
    if replay:bank={name:job(args) for name,args in zip(PROFILES,jobs)}
    else:
        with ProcessPoolExecutor(max_workers=2) as pool:bank=dict(zip(PROFILES,pool.map(job,jobs)))
    eligible=[k for k,a in bank.items() if a['training']['metrics']['correct']>0.9*len(rows)]
    if not eligible:raise ValueError('No portable profile reaches the accepted local fit floor; continue diagnosis')
    selected=min(eligible,key=lambda k:(-PROFILES[k]['min_leaf_sources'],bank[k]['search']['nodes'],PROFILES[k]['max_depth'],
                                       -bank[k]['training']['metrics']['correct'],k))
    model=PortableSemanticTree.restore(bank[selected]);exact(out/'frozen_policy.json',model.metadata())
    (out/'rules.txt').write_text(model.render()+'\n')
    ps=model.predict_records([r['features'] for r in rows]);conditions=[];leaves=[]
    def walk(node,path):
        if node['type']=='leaf':leaves.append({'conditions':path,'prediction':node['prediction'],'support':node['support'],'sources':node['source_groups']});return
        conditions.append(node['feature'])
        for value in (True,False):walk(node['true' if value else 'false'],path+[{'feature':node['feature'],'value':value}])
    walk(model.metadata()['tree'],[])
    assert all(k in SPECS and '_count_ge_' not in k and not k.endswith('_majority') for k in conditions)
    result={'version':VERSION,'selected_profile':selected,'training_metrics':metrics([p['prediction'] for p in ps],[r['reference'] for r in rows]),
       'cases':[{'case':r['case'],'reference':r['reference'],**p} for r,p in zip(rows,ps)],
       'candidate_metrics':{k:{'metrics':a['training']['metrics'],'nodes':a['search']['nodes'],'eligible':k in eligible} for k,a in bank.items()},
       'rules':leaves,'branch_predicates':sorted(set(conditions)),'semantic_groups':model.metadata()['groups'],
       'held_out_accuracy_used_for_selection':False,'new_model_calls':0,'reserved_test_predictions':0,
       'limitation':'Case-independent vocabulary and reuse are verified; empirical accuracy on a new distribution is a separate claim.'}
    exact(out/'results.json',result)
    if replay:exact(out/'replay.json',{'exact_replay':True,'new_fits':0,'new_model_calls':0,'results_sha256':fingerprint(out/'results.json')})
    print({'selected_profile':selected,'training':result['training_metrics'],'rules':len(leaves),'distinct_predicates':len(set(conditions))},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--replay',action='store_true')
    a=p.parse_args();run(a.output_dir.resolve(),a.replay)
