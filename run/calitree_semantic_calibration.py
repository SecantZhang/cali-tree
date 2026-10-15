"""Offline matched-budget clustering comparison on the fixed 48 AURORA cases."""
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

from critical.core.calibration.registry import CalibrationRegistry
from critical.core.calibration.semantic_calibration import SemanticRouter,SemanticOrdinalCalibrator
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.semantic_evidence import feature_record,QUALITIES,DESCRIPTORS
from run.calitree_single_call import ROOT,read,fingerprint
from run.calitree_semantic_evidence import prepare

EVIDENCE=ROOT/'logs/exps/261014-semantic-contract-evidence-v5'


def run(evidence,output):
    manifest=prepare(evidence); observed=read(evidence/'results.json'); output.mkdir(parents=True,exist_ok=True)
    bycase={r['case']:r for r in observed['observations']}
    cases=manifest['cases']; features=[]
    for c in cases:
        row=bycase[c['case']]
        if row['id']!=c['id'] or row['instruction']!=c['instruction']:raise ValueError('Changed case join')
        features.append(feature_record(row['extraction']['observations'],c['instruction']) if row['extraction'] else
                        {'lower':[0]*8,'upper':[4]*8,'descriptor':None})
    # Persist the label-blind router before any supervised fitting.
    router=SemanticRouter().fit([r['descriptor'] for r in features]); routing=router.predict([r['descriptor'] for r in features])
    router_data={'router':router.metadata(),'input_columns':list(DESCRIPTORS),
                 'memberships':[{'case':c['case'],'cluster':r} for c,r in zip(cases,routing)],
                 'labels_or_evidence_grades_used':False,'frozen_before_supervised_fit':True}
    if (output/'router.json').exists() and read(output/'router.json')!=router_data:raise ValueError('Changed frozen router')
    save_json(output/'router.json',router_data)
    registry=CalibrationRegistry(output/'registry'); groups={}
    for batch in sorted({c['batch'] for c in cases}):
        indices=[i for i,c in enumerate(cases) if c['batch']==batch]
        part=[cases[i] for i in indices]; x=[features[i] for i in indices]
        y=[('no','partial','yes').index(c['reference']) for c in part]; result={}
        for name,clustered in [('unclustered',False),('clustered',True)]:
            fit=SemanticOrdinalCalibrator(router,clustered=clustered)
            try:
                fit.fit(x,y,source_groups=[c['group'] for c in part]); records=fit.predict_records(x)
            except ValueError as exc:
                error=str(exc); records=[{'prediction':-1} for _ in x]; version=path=artifact=None
            else:
                version,path=registry.publish(fit.metadata()); artifact=fit.metadata()
                if SemanticOrdinalCalibrator.restore(artifact).predict_records(x)!=records:raise AssertionError('Restore changed predictions')
                error=None
            metric,_,_=classification_metrics([r['prediction'] for r in records],y)
            result[name]={'metrics':metric,'registry_version':version,'artifact':str(path) if path else None,
                          'policy':artifact,'error':error,
                          'cases':[{'case':c['case'],'reference':t,'instruction':c['instruction'],
                                    'features':f,'transport_error':bycase[c['case']]['error'],**r}
                                   for c,t,f,r in zip(part,y,x,records)]}
            print({'group':batch,'family':name,'correct':metric['correct'],'macro_f1':metric['macro_f1'],
                   'unresolved':metric['unresolved'],'error':error},flush=True)
        groups[batch]=result
    # Flat results use exactly the same fixed cases, with their original failures.
    old=read(ROOT/'logs/exps/261013-four-groups-local-v4/results.json')
    result={'version':'semantic-cluster-comparison-v5','evidence_ref':fingerprint(evidence/'results.json'),
            'fixed_manifest_ref':digest(manifest),'router_ref':digest(router_data),'groups':groups,
            'old_comparison':old,'evidence_cost':{'new_calls':observed['attempts'],
                'outcomes':observed['outcomes'],'input_tokens':observed['input_tokens'],
                'completion_tokens':observed['completion_tokens'],
                'usage_list_price_usd':observed['input_tokens']*2/1e6+observed['completion_tokens']*10/1e6,
                'note':'Returned usage at standard rates; failed requests may have unreturned usage; not an invoice.'},
            'scope':'Fit and score each fixed 12-case group locally; all failures remain denominator; one cached extraction per case.'}
    result_path=output/'results.json'
    if result_path.exists() and read(result_path)!=result:raise ValueError('Changed saved fit result')
    save_json(result_path,result)
    save_json(output/'features.json',[{'case':c['case'],**f} for c,f in zip(cases,features)])
    files=[Path(__file__).resolve(),ROOT/'critical/core/calibration/semantic_calibration.py',ROOT/'tests/unit/calitree/test_semantic_calibration.py']
    save_json(output/'fit_seal.json',{'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in files},
               'evidence_ref':fingerprint(evidence/'results.json'),'results_ref':fingerprint(result_path),
               'router_ref':fingerprint(output/'router.json'),'new_calls_in_fitting':0})
    lines=['# Semantic evidence and clustering: fixed four-group local fitting','',
           'Each group contains four No, four Partial, and four Yes cases. These are LOCAL fitting results.',
           'Both policy families use at most four nonzero coefficients (including cluster offsets) and two shared thresholds.',
           'Cluster routing uses instruction-contract booleans only; no labels, evidence grades, words, or case IDs.','',
           '| Group | Policy | Correct / 12 | Macro-F1 | No recall | Partial recall | Yes recall | Resolved / 12 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for b,arms in groups.items():
        for name,arm in arms.items():
            m=arm['metrics'];r=[m['per_class'][c]['recall'] for c in ('no','partial','yes')]
            lines.append(f"| {b} | {name} | {m['correct']}/12 | {m['macro_f1']:.3f} | {r[0]:.0%} | {r[1]:.0%} | {r[2]:.0%} | {12-m['unresolved']}/12 |")
    lines+=['','## Learned policies','', 'Score = weighted quality grades + cluster offset. No below the first cut; Partial between cuts; Yes at or above the second cut. Uncertain bounds must agree.','']
    for b,arms in groups.items():
        for name,arm in arms.items():
            a=arm['policy']
            if not a:lines.append(f"- {b} {name}: infeasible ({arm['error']}).");continue
            terms=' + '.join(f'{v} × {q}' for q,v in zip(QUALITIES,a['weights']) if v)
            lines.append(f"- {b} {name}: score = {terms}; cluster offsets {a['offsets']}; cuts {a['cutpoints']}; active coefficients {a['active_coefficients']}/4.")
    lines+=['','## Costs and limitations','',f"48 new evidence attempts; outcomes {observed['outcomes']}. Returned usage {observed['input_tokens']:,} input and {observed['completion_tokens']:,} output tokens, ${result['evidence_cost']['usage_list_price_usd']:.4f} at standard rates. Offline fitting made zero API calls.",
            'The evidence representation was designed after inspecting earlier failures. These are training results, not an unbiased estimate of generalization or repeat robustness.',
            'Four failed new responses remain unresolved. Cached flat results have a different failure pattern; compare common resolved cases separately before attributing gains to reasoning.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-dir',type=Path,default=EVIDENCE)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.evidence_dir.resolve(),a.output_dir.resolve())


if __name__=='__main__': main()
