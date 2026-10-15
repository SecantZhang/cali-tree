"""Offline strict and quote-normalized fast-model calibration comparisons."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import numpy as np

from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.semantic_calibration import SemanticRouter
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.semantic_evidence import feature_record,QUALITIES
from critical.core.decision.literal_quotes import normalize_literal_quotes
from critical.core.decision.artifacts import save_json,digest
from run.calitree_small_models import prepare,verify,SOL
from run.calitree_single_call import ROOT,read,fingerprint


def latency(values):
    return {'n':len(values),'median_seconds':float(np.median(values)) if values else None,
            'p90_seconds':float(np.percentile(values,90)) if values else None}


def job_for(output,key,case,arm):
    files=list((output/'ledgers'/key/case/arm/'jobs').glob('*.json'))
    if len(files)!=1:raise ValueError('Exactly one durable call per slot required')
    return read(files[0])


def evidence_rows(output,key,cases,observed,normalized):
    values=[];normalizations=[]
    for c in cases:
        row=observed[(key,c['case'],'evidence')];extract=row['extraction'];facts=extract['observations'] if extract else None
        if facts is None and normalized:
            job=job_for(output,key,c['case'],'evidence')
            if job['outcome']=='completed' and isinstance(job.get('parsed'),dict):
                try:
                    fixed,changes=normalize_literal_quotes(job['parsed'],c['instruction'])
                except (ValueError,TypeError,KeyError):pass
                else:
                    if changes:facts=fixed;normalizations.append({'case':c['case'],'changes':changes,'raw_execution_ref':job['execution_ref']})
        values.append(feature_record(facts,c['instruction']) if facts is not None else
                      {'lower':[0]*8,'upper':[4]*8,'descriptor':None})
    return values,normalizations


def summarize(predictions,targets):return classification_metrics(predictions,targets)[0]


def fit_mode(output,m,key,cases,observed,*,normalized):
    name='literal_quote_normalized' if normalized else 'strict'
    features,repairs=evidence_rows(output,key,cases,observed,normalized)
    valid=[f['descriptor'] for f in features if f['descriptor'] is not None]
    router=SemanticRouter().fit(valid) if valid else None
    destination=output/'calibration'/key/name;destination.mkdir(parents=True,exist_ok=True)
    router_value=router.metadata() if router else None
    if (destination/'router.json').exists() and read(destination/'router.json')!=router_value:raise ValueError('Changed label-blind router')
    save_json(destination/'router.json',router_value) # before any labels enter fitting
    registry=CalibrationRegistry(destination/'registry');groups={};pool={k:[] for k in ('flat','frozen_sol_shared','local_shared','local_clustered')};all_y=[]
    sol=read(SOL/'results.json')
    for batch in ('G1','G2','G3','G4'):
        indices=[i for i,c in enumerate(cases) if c['batch']==batch];part=[cases[i] for i in indices];x=[features[i] for i in indices]
        y=[('no','partial','yes').index(c['reference']) for c in part];all_y+=y
        flat=[('no','partial','yes').index(r['prediction']) if r['prediction'] is not None else -1 for c in part for r in [observed[(key,c['case'],'flat')]]]
        frozen=VisibilityOrdinalCalibrator.restore(sol['groups'][batch]['unclustered']['policy'])
        frozen_records=frozen.predict_records(x);predictions={'flat':flat,'frozen_sol_shared':[r['prediction'] for r in frozen_records]}
        arms={}
        for family,clustered in [('local_shared',False),('local_clustered',True)]:
            policy=None;error=None;version=path=None
            try:
                if router is None:raise ValueError('No valid instruction contracts')
                fit=VisibilityOrdinalCalibrator(router,clustered=clustered).fit(x,y,source_groups=[c['group'] for c in part])
            except ValueError as exc:
                error=str(exc);records=[{'prediction':-1} for _ in part]
            else:
                records=fit.predict_records(x);policy=fit.metadata();version,path=registry.publish(policy)
                if VisibilityOrdinalCalibrator.restore(policy).predict_records(x)!=records:raise ValueError('Changed restored policy')
            predictions[family]=[r['prediction'] for r in records]
            arms[family]={'policy':policy,'error':error,'registry_version':version,'registry_path':str(path) if path else None}
        for family,p in predictions.items():
            common=[i for i in range(12) if p[i]>=0 and flat[i]>=0]
            arms.setdefault(family,{})
            arms[family].update(metrics=summarize(p,y),
               common_resolved_with_flat={'total':len(common),'flat_correct':sum(flat[i]==y[i] for i in common),'arm_correct':sum(p[i]==y[i] for i in common)},
               cases=[{'case':c['case'],'reference':t,'prediction':v,'evidence_available':f['descriptor'] is not None} for c,t,v,f in zip(part,y,p,x)])
            pool[family]+=p
        groups[batch]=arms
        print({'model':key,'mode':name,'group':batch,'counts':{family:arm['metrics']['correct'] for family,arm in arms.items()},
               'errors':{family:arm.get('error') for family,arm in arms.items() if arm.get('error')}},flush=True)
    pooled={family:summarize(p,all_y) for family,p in pool.items()}
    return {'mode':name,'groups':groups,'pooled':pooled,'normalizations':repairs,
            'valid_evidence':len(valid),'router_ref':digest(router_value),'scope':'Each group fit and scored on its own 12 labels; frozen Sol rules already used these source labels historically.'}


def usage(output,key,m):
    result={};price=m['prices_per_million'][key]
    for arm in ('flat','evidence'):
        jobs=[job_for(output,key,c['case'],arm) for c in m['cases']];responses=[j['response'] for j in jobs if j.get('response')]
        input_tokens=sum(r.get('promptTokens',0) for r in responses);output_tokens=sum(r.get('completionTokens',0) for r in responses)
        result[arm]={'attempts':len(jobs),'outcomes':dict(Counter(j['outcome'] for j in jobs)),
           'returned_input_tokens':input_tokens,'returned_output_tokens':output_tokens,
           'uncached_standard_cost_estimate_usd':(input_tokens*price['input']+output_tokens*price['output'])/1e6,
           'successful_api_latency':latency([r['latencySeconds'] for r in responses if r.get('latencySeconds') is not None])}
    return result


def run(output):
    manifest=read(output/'manifest.json');m=prepare(output,list(manifest['models']));cases=m['cases']
    raw=read(output/'observations.json');observed={(r['model_key'],r['case'],r['arm']):r for r in raw['observations']}
    if len(observed)!=m['max_calls']:raise ValueError('Incomplete planned collection')
    result={'version':'fast-model-calibration-comparison-v1','manifest_ref':digest(m),'observations_ref':fingerprint(output/'observations.json'),
            'models':{},'primary':'strict/local_shared; literal quote normalization is a separate post-hoc format-only diagnostic',
            'scope':'Local fitting, same fixed 48 AURORA cases; not held-out accuracy or repeat robustness.'}
    for key in m['models']:
        model={'identity':m['models'][key],'usage':usage(output,key,m),'modes':{}}
        for normalized in (False,True):
            mode=fit_mode(output,m,key,cases,observed,normalized=normalized);model['modes'][mode['mode']]=mode
        result['models'][key]=model
    verify(output,m)
    if (output/'results.json').exists() and read(output/'results.json')!=result:raise ValueError('Changed saved analysis')
    save_json(output/'results.json',result)
    files=[Path(__file__).resolve(),ROOT/'critical/core/decision/literal_quotes.py',ROOT/'tests/unit/calitree/test_literal_quotes.py',ROOT/'tests/unit/calitree/test_small_models.py']
    files += [ROOT/f'critical/core/calibration/{name}.py' for name in ('semantic_calibration','visibility_calibration')]
    hashes={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'fit_source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);hashes[rel]=fingerprint(p)
    save_json(output/'fit_seal.json',{'code_hashes':hashes,'results_ref':fingerprint(output/'results.json'),'new_api_calls':0})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
