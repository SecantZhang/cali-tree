"""Separately authorized regular baseline for frozen cached forward comparison."""
import argparse
from pathlib import Path
from collections import Counter

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.calitree_aurora_pilot_v29 import read,fingerprint,IDENTITY,ROOT,exact
from run.collect_calitree_aurora_pilot_v29r1 import validate_regular,metrics


def verify(out):
    manifest=read(out/'manifest.json');protocol=read(out/'protocol.json');inputs=read(out/'inputs.json')
    assert digest(protocol)==manifest['protocol_ref'] and digest(inputs)==manifest['input_ref']
    assert digest(read(out/'references.json'))==manifest['references_ref']
    for p,h in {**manifest['source_hashes'],**manifest['code_hashes']}.items():assert fingerprint(p)==h,p
    assert read(out/'prediction_freeze.json')=={'predictions_sha256':fingerprint(out/'frozen_predictions.json'),'inputs_sha256':fingerprint(out/'inputs.json')}
    assert len(inputs)==36 and len({r['source_group']for r in inputs})==36
    for r in inputs:
        for kind,path in r['evidence'].items():assert fingerprint(path)==r['image_hashes'][kind]
    return protocol


def prepare(out):
    protocol=verify(out)
    plan={'protocol_ref':digest(protocol),'collector_sha256':fingerprint(__file__),
          'max_requests':36,'max_completion_tokens':73728,'max_tokens_per_request':2048,
          'official_endpoint':'https://api.openai.com/v1','identity':IDENTITY,
          'inference_scope':'Regular judge only; no refitting or new extraction; one attempt per case.',
          'explicit_paid_authorization_required':True,'new_model_calls':0}
    exact(out/'execution_plan.json',plan)
    print(plan,flush=True)


def collect(out,live=False):
    if not live:raise ValueError('Explicit authorization and --live required')
    protocol=verify(out);plan=read(out/'execution_plan.json')
    assert plan['collector_sha256']==fingerprint(__file__) and plan['protocol_ref']==digest(protocol)
    from critical import config
    from critical.core.decision.calls import DurableCalls,ProviderStopped,BudgetExhausted
    from critical.lm_engine import load_creds,get_engine,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT=Path('/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys');config.CREDENTIALS_FILE=config.PROJECT_ROOT/'.env'
    creds=load_creds(provider='openai',engine='gpt')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official endpoint required')
    def factory(cap):return get_engine('gpt',creds=creds,model=IDENTITY['model'],temperature=0,max_tokens=cap,
        timeout=180,max_http_attempts=1,history=LLMHistoryWriter(out/'ledger/llm-histories.log'))
    calls=DurableCalls(out/'ledger',factory,identity=IDENTITY,max_calls=36,max_completion_tokens=73728,scope_limits={'search':1,'final':0})
    for r in read(out/'inputs.json'):
        path=out/'regular_responses'/(r['case']+'.json')
        if path.exists():continue
        try:
            value,ref=calls.call('flat_judge',{'instruction':r['instruction']},task.SCHEMA,
                template=(task.TEMPLATES/'regular.txt').read_text(),media=media_inputs(r['evidence']),
                case_id=r['case'],slot='once',max_tokens=2048)
            validate_regular(value);result={'judgment':value,'execution_ref':ref,'error':None}
        except(ProviderStopped,BudgetExhausted):raise
        except(ValueError,RuntimeError,KeyError,TypeError)as e:result={'judgment':None,'execution_ref':None,'error':type(e).__name__}
        exact(path,result);print({'case':r['case'],'error':result['error']},flush=True)
    report(out)


def report(out):
    verify(out);inputs=read(out/'inputs.json');preds={r['case']:r for r in read(out/'frozen_predictions.json')};refs=read(out/'references.json');rows=[]
    for e in inputs:
        response=read(out/'regular_responses'/(e['case']+'.json'));value=response['judgment']
        baseline=task.LABELS.index(value['label'])if value and value['label']in task.LABELS else -1
        row={'case':e['case'],'source_group':e['source_group'],'reference':task.LABELS.index(refs[e['case']]),
             'regular':baseline,'routes':preds[e['case']]['routes'],'regular_error':response['error']}
        for name,route in row['routes'].items():row[name]=route['prediction']if route['covered']else baseline
        rows.append(row)
    arms=['regular',*rows[0]['routes']]
    result={'cases':len(rows),'source_groups':len({r['source_group']for r in rows}),'metrics':{a:metrics(rows,a)for a in arms},
            'class_counts':dict(Counter(r['reference']for r in rows)),'new_extraction_calls':0,'new_fitting':False}
    exact(out/'full_predictions.json',rows);exact(out/'full_results.json',result)
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--live',action='store_true');p.add_argument('--report',action='store_true');a=p.parse_args()
    if sum((a.prepare,a.live,a.report))!=1:p.error('Choose exactly one mode')
    if a.prepare:prepare(a.output_dir.resolve())
    elif a.live:collect(a.output_dir.resolve(),live=True)
    else:report(a.output_dir.resolve())
