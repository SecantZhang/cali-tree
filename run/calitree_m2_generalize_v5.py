"""Stable evidence plus nested selection of supported M2 rule complexity."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import math
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION as M1_VERSION
from critical.core.calibration.semantic_hierarchy import stable_features_v5 as stable
from critical.core.calibration.semantic_hierarchy.conflict_tree_v4 import ConflictAwareSemanticTree, LIMITS, metrics
from run.calitree_single_call import ROOT, read, fingerprint

VERSION='m2-stable-nested-selection-v5'
V4=ROOT/'logs/exps/261014-m2-conflict-regrouping-v4'
M0=ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
SOURCES={'train':ROOT/'logs/exps/261014-m2-m4-bound-training48-v1',
         'validation':ROOT/'logs/exps/261014-m1-bound-evidence-development12-v2'}
PROFILES={f'depth{depth}_support{support}':{**LIMITS,'max_depth':depth,'min_leaf_sources':support}
          for depth,support in [(6,2),(5,2),(4,2),(6,3),(5,3),(4,3),(6,4)]}


def exact(path,value):
    if path.exists():
        if read(path)!=value:raise ValueError('Frozen v5 artifact changed: '+str(path))
    else:save_json(path,value)


def load_data():
    old=read(V4/'data.json');data={};audits={}
    forbidden={c['group'] for c in read(M0/'splits/test.json')['cases']}
    for partition,directory in SOURCES.items():
        raw={r['case']:r for r in read(directory/'observations.json')}
        cases={c['case']:c for c in read(M0/'splits'/(partition+'.json'))['cases']};data[partition]=[]
        for row in old[partition]:
            c=cases[row['case']];r=raw[row['case']]
            if c['group']!=row['source_group'] or c['group'] in forbidden:raise ValueError('Invalid source role')
            feature=None
            if r['compilation'] is not None and r['observation'] is not None:
                pair=digest([M1_VERSION,'source_first',c['image_hashes']['source_image'],c['image_hashes']['edited_image']])
                feature,audit=stable.project_with_audit(r['compilation']['program'],r['observation']['observation'],pair)
                audits[row['case']]=audit
            data[partition].append({**deepcopy(row),'features':feature})
    return data,audits


def prepare(out):
    out.mkdir(parents=True,exist_ok=True)
    protocol={'version':VERSION,'feature_contract_ref':stable.CONTRACT_REF,'profiles':PROFILES,
        'accepted_user_relaxation':'It is also OK for generalizability if it retains over 90% of accuracy.',
        'fit_floor':'Strictly greater than 90% over all fitting rows, including missing records: 44/48 for full fit.',
        'selection':'For each context, qualify profiles by that context training fit, then rank inner leave-one-original-group-out macro-F1, worst recall, accuracy, stronger source support, fewer nodes, name.',
        'evaluation':'Four outer source-separated groups. Every profile fit and selection inside each outer context excludes its held-out group. Freeze full context before dev12 scoring.',
        'stability':'Exact bound-definition duplicates and ID/order changes are canonicalized; conflicting duplicate states become unknown. No paraphrase equivalence claim.',
        'new_model_calls':0,'reserved_test_predictions':0}
    exact(out/'protocol.json',protocol)
    code=[Path(__file__).resolve(),ROOT/'critical/core/calibration/semantic_hierarchy/stable_features_v5.py',
          ROOT/'critical/core/calibration/semantic_hierarchy/features_v4.py',ROOT/'critical/core/calibration/semantic_hierarchy/conflict_tree_v4.py',
          ROOT/'critical/core/decision/bound_evidence_v2.py',ROOT/'critical/core/decision/bound_evidence.py']
    pins=[V4/'results.json',V4/'completion_seal.json',M0/'completion_seal.json',M0/'splits/train.json',M0/'splits/validation.json',M0/'splits/test.json',
          *(p/'observations.json' for p in SOURCES.values())]
    manifest={'version':VERSION,'protocol_ref':digest(protocol),'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in code},
              'source_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in pins}}
    exact(out/'manifest.json',manifest)
    for source in code:
        path=out/'source_snapshot'/source.relative_to(ROOT);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():assert fingerprint(path)==fingerprint(source)
        else:shutil.copyfile(source,path)
    data,audits=load_data();exact(out/'data.json',data);exact(out/'projection_audit.json',audits)
    return data


def fit_key(rows,profile):
    ordered=sorted(rows,key=lambda r:r['source_group'])
    return digest([stable.CONTRACT_REF,PROFILES[profile],[(r['source_group'],r['batch'],r['reference'],r['features']) for r in ordered]])


def fit_job(args):
    out,rows,profile,replay=args;path=Path(out)/'fits'/(fit_key(rows,profile)+'.json')
    if path.exists():
        value=read(path);ConflictAwareSemanticTree.restore(value['policy']);return value
    if replay:raise ValueError('Missing fit in replay')
    model=ConflictAwareSemanticTree(limits=PROFILES[profile]).fit([stable.as_base(r['features']) for r in rows],[r['reference'] for r in rows],
                source_groups=[r['source_group'] for r in rows],source_batches=[r['batch'] for r in rows])
    value={'profile':profile,'fit_ref':fit_key(rows,profile),'policy':model.metadata()};exact(path,value)
    print({'fit_rows':len(rows),'batches':sorted({r['batch'] for r in rows}),'profile':profile,
           'correct':model.metadata()['training']['metrics']['correct'],'states':model.metadata()['search']['states']},flush=True)
    return value


def predictions(policy,rows):
    return ConflictAwareSemanticTree.restore(policy).predict_records([stable.as_base(r['features']) for r in rows])


def select(out,rows):
    candidates={};groups=sorted({r['batch'] for r in rows});floor=math.floor(len(rows)*0.9)+1
    for profile in PROFILES:
        fitted=fit_job((str(out),rows,profile,True));policy=fitted['policy'];oof=[];inner=[]
        for held in groups:
            fitting=[r for r in rows if r['batch']!=held];test=[r for r in rows if r['batch']==held]
            f=fit_job((str(out),fitting,profile,True));ps=predictions(f['policy'],test)
            assert not set(f['policy']['training']['source_groups'])&{r['source_group'] for r in test}
            inner.append({'held_group':held,'fit_ref':f['fit_ref'],'fit_sources':f['policy']['training']['source_groups'],
                          'validation_sources':[r['source_group'] for r in test],'cases':[r['case'] for r in test],
                          'predictions':[p['prediction'] for p in ps]})
            oof.extend((r,p['prediction']) for r,p in zip(test,ps))
        m=metrics([p for r,p in oof],[r['reference'] for r,p in oof])
        candidates[profile]={'fit_ref':fitted['fit_ref'],'training_metrics':policy['training']['metrics'],
            'eligible':policy['training']['metrics']['correct']>=floor,'inner_metrics':m,'inner_folds':inner,'nodes':policy['search']['nodes']}
    eligible=[name for name,v in candidates.items() if v['eligible']]
    if not eligible:raise ValueError('No profile preserves the user-approved fitting floor')
    def rank(name):
        c=candidates[name];m=c['inner_metrics']
        return (-m['macro_f1'],-m['worst_present_class_recall'],-m['correct'],
                -PROFILES[name]['min_leaf_sources'],c['nodes'],name)
    selected=sorted(eligible,key=rank)[0];fitted=fit_job((str(out),rows,selected,True))
    context={'version':VERSION,'feature_contract_ref':stable.CONTRACT_REF,'fit_sources':sorted(r['source_group'] for r in rows),
             'minimum_correct':floor,'selected_profile':selected,'candidates':candidates,'policy':fitted['policy']}
    context['artifact_ref']=digest(context)
    return context


def evaluate(context,rows):
    ps=predictions(context['policy'],rows)
    return {'metrics':metrics([p['prediction'] for p in ps],[r['reference'] for r in rows]),
            'cases':[{'case':r['case'],'reference':r['reference'],'source_group':r['source_group'],**p} for r,p in zip(rows,ps)]}


def run(out,replay=False,workers=2):
    data=prepare(out);train=data['train'];groups=sorted({r['batch'] for r in train});jobs=[]
    for count in (4,3,2):
        for subset in combinations(groups,count):
            rows=[r for r in train if r['batch'] in subset]
            for profile in PROFILES:jobs.append((str(out),rows,profile,replay))
    if replay:
        for job in jobs:fit_job(job)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:list(pool.map(fit_job,jobs))
    full=select(out,train);exact(out/'frozen_context.json',full)
    training=evaluate(full,train);folds={};oof=[]
    for held in groups:
        fitting=[r for r in train if r['batch']!=held];test=[r for r in train if r['batch']==held]
        context=select(out,fitting);scores=evaluate(context,test)
        assert not set(context['fit_sources'])&{r['source_group'] for r in test}
        folds[held]={'context':context,'result':scores};oof.extend(scores['cases'])
    result={'version':VERSION,'selected_profile':full['selected_profile'],'training':training,'outer_folds':folds,
            'oof_metrics':metrics([r['prediction'] for r in oof],[r['reference'] for r in oof]),
            'development12':evaluate(full,data['validation']),'baseline':read(V4/'results.json'),
            'new_model_calls':0,'reserved_test_predictions':0,
            'scope':'Nested development estimate after architecture exploration; historical exposure and small sample remain limitations.'}
    exact(out/'results.json',result)
    if replay:exact(out/'replay.json',{'exact_replay':True,'new_fits':0,'new_model_calls':0,'results_sha256':fingerprint(out/'results.json')})
    print({'selected_profile':full['selected_profile'],'training':training['metrics'],'nested_oof':result['oof_metrics'],
           'development12':result['development12']['metrics']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--replay',action='store_true');p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();run(a.output_dir.resolve(),a.replay,a.workers)
