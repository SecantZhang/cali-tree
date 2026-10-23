"""Source-held-out evaluation of verdict verifiers and guarded region merging."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.calibration import semantic_guarded_merge_v32 as fixed
from critical.core.calibration import semantic_region_merge_v28 as previous
from critical.core.decision.artifacts import digest,save_json
from run.calitree_semantic_region_merge_v28 import inputs as old_inputs
from run.collect_calitree_aurora_pilot_v29r1 import metrics
from run.calitree_aurora_pilot_v29 import ROOT,read,fingerprint

PILOT=ROOT/'logs/exps/261020-aurora-pilot80-v29-run1'
PREVIOUS=ROOT/'logs/exps/261020-shared-regions-v27-r1'
METHODS=('verified_v27','verified_v28','guarded_merge')


def load_pilot():
    rows=read(PILOT/'collection/predictions.json');metadata={r['case']:r for r in read(PILOT/'inputs.json')};result=[]
    for r in rows:
        s=read(PILOT/'collection/cases'/(r['case']+'.json'));record=None
        if s['extraction_error']is None:record=fixed.shared.evidence.project(s['program'],s['observation'],s['pair_ref'],s['interpretation'])
        result.append({**r,'program':s['program'],'features':record,'instruction':metadata[r['case']]['instruction']})
    return result


def context(bank):
    rows,programs,baseline,cohorts,bound,previous_directory,prior,probes=old_inputs(PREVIOUS,bank)
    protected=[];examples=[]
    for scope,cohort in cohorts.items():
        for r in cohort:
            e=bound[r['case']]['example'];examples.append(e)
            route=baseline.previous.select(e['program'],e['features'])
            if route['covered']and route['prediction']==r['reference']:
                protected.append({'prediction':route['prediction'],'reference':r['reference'],
                                  'values':fixed.shared.evidence.feature_values(e['program'],e['features']),
                                  'source_group':r['source_group'],'case':r['case']})
    v28=previous.SemanticMergedRegionGate(read(ROOT/f'logs/exps/261020-semantic-region-merge-v28-r2/split{bank}/gate.json'))
    return rows,programs,baseline,v28,protected,examples


def calibrations(base,examples):
    result=[]
    for e in examples:
        if e['features']is None:continue
        route=base.previous.select(e['program'],e['features'])
        if route['covered']:
            result.append({'values':fixed.shared.evidence.feature_values(e['program'],e['features']),
                           'prediction':route['prediction'],'reference':e['reference'],
                           'source_group':e['source_group'],'case':e['case']})
    return result


def build(bank,training):
    rows,programs,base,v28,protected,regression=context(bank)
    verifier=fixed.fit_verifier(protected,calibrations(base,training))
    merged,fit=fixed.develop(base,rows,programs,verifier,regression,[e for e in training if e['features']is not None])
    gates={'verified_v27':fixed.VerifiedRegionGate(base,verifier),'verified_v28':fixed.VerifiedRegionGate(v28,verifier),'guarded_merge':merged}
    # Actual local coverage and old correct acceptances must survive every fitted
    # fold. No inference membership exception or record-hash lookup is installed.
    for name,gate in gates.items():
        for r in rows:
            route=gate.select(programs[r['source_group']],r['features'])
            assert route['covered']and route['prediction']==r['reference']
        for e in regression:
            before=base.select(e['program'],e['features'])
            after=gate.select(e['program'],e['features'])
            if before['covered']:assert after['covered']and after['prediction']==before['prediction']
    return gates,verifier,fit


def measure(gate,e):
    if e['features']is None:return {'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
    return gate.select(e['program'],e['features'])


def run(out):
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    protocol={'version':fixed.VERSION,'config':fixed.asdict(fixed.Config()),
              'calibration':'For each pilot source group, fit on all other 15 groups plus original local and previously correct regression support. No sibling output or held-source label in fitting.',
              'verifier':'Per-verdict CNF; at most eight clauses with one/two declared semantic literals each. Preserve all correct protected support. Enumerated train-error rejection, not held-out score selection.',
              'merge':'Require symbolic preservation of goal/materiality/uncertainty/outcome obligations per task scope; retain child local support and reject new false calibration acceptances.',
              'arms':list(METHODS),'prior_exposure':'Pilot already reviewed when design was chosen: source-cross-fitting is an exploratory procedure check, not a pristine blind trial.',
              'forward':'After final models freeze, evaluate the 36 legacy compiler-v3 evaluation inputs disjoint from new fitting. Their prior research exposure is disclosed. No regular response exists in the approved current cache.',
              'new_model_calls':0,'default_changed':False}
    save_json(out/'protocol.json',protocol)
    pilot=load_pilot();groups=sorted({r['source_group']for r in pilot});predictions={r['case']:{k:r[k]for k in ('case','source_group','task','editor','historical_exposure','reference','regular','regular_error','extraction_error')}for r in pilot}
    for r in pilot:
        predictions[r['case']]['routes']={k:v for k,v in r['routes'].items()if k.startswith('v27')or k.startswith('v28')}
        for name in predictions[r['case']]['routes']:predictions[r['case']][name]=r[name]
    folds=[]
    for fold,group in enumerate(groups):
        training=[r for r in pilot if r['source_group']!=group];held=[r for r in pilot if r['source_group']==group]
        assert len(held)==5 and not {r['source_group']for r in training}&{group}
        for bank in(1,2,3):
            gates,verifier,fit=build(bank,training)
            folder=out/f'fold{fold:02}/split{bank}'
            save_json(folder/'verifier.json',verifier);save_json(folder/'merge_fit.json',fit)
            for name,gate in gates.items():save_json(folder/(name+'.json'),gate.export())
            for r in held:
                for name,gate in gates.items():
                    arm=f'{name}_split{bank}';route=measure(gate,r)
                    predictions[r['case']]['routes'][arm]=route
                    predictions[r['case']][arm]=route['prediction']if route['covered']else r['regular']
            folds.append({'fold':fold,'held_source':group,'bank':bank,'training_sources':sorted({r['source_group']for r in training}),
                          'held_cases':[r['case']for r in held],'fit_ref':digest(fit),'verifier_ref':verifier['artifact_ref'],
                          'merges':len(fit['accepted']),'semantic_rejections':fit['semantic_obligation_rejections']})
        print({'fold_completed':fold+1,'total':len(groups)},flush=True)
    records=[predictions[r['case']]for r in pilot];arms=['regular']+[f'{name}_split{i}'for i in(1,2,3)for name in('v27','v28',*METHODS)]
    summary={'version':fixed.VERSION,'source_crossfit':{a:metrics(records,a)for a in arms},'folds':folds,'new_model_calls':0}
    save_json(out/'crossfit_predictions.json',records);save_json(out/'results.json',summary)
    # Freeze final all-development gates before accessing forward reference labels.
    frozen={}
    for bank in(1,2,3):
        gates,verifier,fit=build(bank,pilot);folder=out/f'full/split{bank}'
        save_json(folder/'verifier.json',verifier);save_json(folder/'merge_fit.json',fit)
        for name,gate in gates.items():
            save_json(folder/(name+'.json'),gate.export());frozen[f'{name}_split{bank}']=gate.artifact['artifact_ref']
    save_json(out/'freeze.json',{'protocol_ref':digest(protocol),'final_gates':frozen,'pilot_training_sources':groups,'source_crossfit':True})
    code=[Path(__file__).resolve(),Path(fixed.__file__).resolve()]
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'code_hashes':{str(p):fingerprint(p)for p in code},
              'pilot':str(PILOT),'baseline_regions':str(PREVIOUS),'pilot_completion_seal_sha256':fingerprint(PILOT/'completion_seal.json')})
    (out/'run.log').write_text('16-source leave-one-group-out fitting; local retention checked in all 48 bank folds; final gates frozen.\n')
    (out/'llm-histories.log').write_text('Zero model calls.\n')
    for a,m in summary['source_crossfit'].items():print(a,m['correct'],m['tree_accepted'],m['accepted_accuracy'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
