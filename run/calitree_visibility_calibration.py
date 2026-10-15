"""Fit and audit reusable observability policies on the unchanged fixed groups."""
import argparse
from pathlib import Path
import shutil

from critical.core.calibration.semantic_calibration import SemanticRouter
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import save_json,digest
from run.calitree_single_call import ROOT,read,fingerprint
from run.calitree_semantic_evidence import prepare

BASE=ROOT/'logs/exps/261014-semantic-cluster-calibration-v5-r1'
EVIDENCE=ROOT/'logs/exps/261014-semantic-contract-evidence-v5'


def run(output):
    if not (output/'plan.json').exists():raise ValueError('Missing declared comparison plan')
    m=prepare(EVIDENCE);cases=m['cases'];cached=read(EVIDENCE/'results.json')
    bycase={r['case']:r for r in cached['observations']}
    saved=read(BASE/'features.json')
    if [r['case'] for r in saved]!=[c['case'] for c in cases]:raise ValueError('Changed fixed group')
    x=[{k:r[k] for k in ('lower','upper','descriptor')} for r in saved]
    router=SemanticRouter.restore(read(BASE/'router.json')['router'])
    if SemanticRouter().fit([r['descriptor'] for r in x]).metadata()!=router.metadata():raise ValueError('Router changed')
    registry=CalibrationRegistry(output/'registry');groups={};old=read(ROOT/'logs/exps/261013-four-groups-local-v4/results.json')
    for batch in sorted({c['batch'] for c in cases}):
        idx=[i for i,c in enumerate(cases) if c['batch']==batch];part=[cases[i] for i in idx];features=[x[i] for i in idx]
        y=[('no','partial','yes').index(c['reference']) for c in part];arms={}
        for name,clustered in [('unclustered',False),('clustered',True)]:
            fit=VisibilityOrdinalCalibrator(router,clustered=clustered)
            try:fit.fit(features,y,source_groups=[c['group'] for c in part])
            except ValueError as exc:raise RuntimeError(f'{batch} {name} infeasible: {exc}') from exc
            records=fit.predict_records(features);artifact=fit.metadata()
            if VisibilityOrdinalCalibrator.restore(artifact).predict_records(features)!=records:raise ValueError('Restore changed predictions')
            version,path=registry.publish(artifact);metric,_,_=classification_metrics([r['prediction'] for r in records],y)
            metrics_old=old['batches'][batch]['flat_metrics']
            prior_rows=old['batches'][batch]['flat_cases']
            flat_bycase={r['case']:r for r in prior_rows}
            # Legacy rows contain flat as a label string; inspect/assert the schema.
            flat=[]
            for c in part:
                value=flat_bycase[c['case']]['prediction']
                flat.append(('no','partial','yes').index(value) if value in ('no','partial','yes') else -1)
            common=[i for i,(a,b) in enumerate(zip(flat,records)) if a>=0 and b['prediction']>=0]
            arms[name]={'metrics':metric,'artifact':str(path),'registry_version':version,'policy':artifact,
                        'flat_metrics':metrics_old,
                        'common_resolved':{'total':len(common),'flat_correct':sum(flat[i]==y[i] for i in common),
                                           'calibrated_correct':sum(records[i]['prediction']==y[i] for i in common)},
                        'cases':[{'case':c['case'],'instruction':c['instruction'],'reference':t,
                                  'flat_prediction':f,'transport_error':bycase[c['case']]['error'],**r}
                                 for c,t,f,r in zip(part,y,flat,records)]}
            print({'batch':batch,'family':name,**metric},flush=True)
        groups[batch]=arms
    plan=read(output/'plan.json');cost=read(BASE/'results.json')['evidence_cost']
    result={'version':'visibility-cluster-comparison-v6','plan_ref':digest(plan),'groups':groups,
            'evidence_ref':fingerprint(EVIDENCE/'results.json'),'router_ref':fingerprint(BASE/'router.json'),
            'evidence_cost':cost,'fit_api_calls':0,
            'near_perfect_all_groups':all(a['metrics']['correct']>=10 for g in groups.values() for a in g.values())}
    if (output/'results.json').exists() and read(output/'results.json')!=result:raise ValueError('Replay changed results')
    save_json(output/'results.json',result)
    code=[Path(__file__).resolve(),ROOT/'critical/core/calibration/visibility_calibration.py',ROOT/'critical/core/calibration/semantic_calibration.py',ROOT/'tests/unit/calitree/test_visibility_calibration.py']
    hashes={str(p.relative_to(ROOT)):fingerprint(p) for p in code}
    for p in code:
        target=output/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    save_json(output/'fit_seal.json',{'code_hashes':hashes,'plan_ref':fingerprint(output/'plan.json'),
              'results_ref':fingerprint(output/'results.json'),'router_ref':fingerprint(BASE/'router.json'),'evidence_ref':fingerprint(EVIDENCE/'results.json')})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
