"""Explicitly authorized collection for the sealed AURORA pilot; prepare is free."""
import argparse
from collections import Counter
from pathlib import Path
import random

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_compiler_v3 import BoundInstructionCompilerV3
from critical.core.optimization.prompt.calitree.evidence_covered_judge import BoundEvidencePipeline
from critical.core.optimization.prompt.calitree import task_coverage as task
from critical.core.decision.compiler import media_inputs
from run.calitree_aurora_pilot_v29 import verify, read, fingerprint, exact, IDENTITY, CAPS, ROOT


def prepare_execution(out):
    verify(out)
    code=list((ROOT/'critical/core/calibration').glob('*.py'))
    code+=list((ROOT/'critical/lm_engine').rglob('*.py'))
    code+=list((ROOT/'critical/core/optimization/prompt/calitree').rglob('*.py'))
    code+=[ROOT/'critical/config.py']
    plan={'version':'aurora-pilot-collection-v29','collector_sha256':fingerprint(__file__),
          'preflight_seal_sha256':fingerprint(out/'preflight_seal.json'),
          'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p)for p in sorted(set(code))},
          'requests':read(out/'estimate.json')['stage_requests_without_repairs'],
          'max_requests':read(out/'estimate.json')['max_requests'],
          'max_completion_tokens':read(out/'estimate.json')['max_completion_tokens'],
          'new_model_calls':0,'concurrency':1,'http_attempts_per_slot':1,'fitting':False,
          'approval_required':'Explicit user authorization to run paid collection, followed by --live.',
          'labels':'Hash-verified during preflight, used for scoring only after frozen inference, and never sent to the model.'}
    exact(out/'execution_plan.json',plan)
    print(plan,flush=True)


def verify_execution(out):
    verify(out);plan=read(out/'execution_plan.json')
    if plan['collector_sha256']!=fingerprint(__file__) or plan['preflight_seal_sha256']!=fingerprint(out/'preflight_seal.json'):
        raise ValueError('Execution plan changed after review')
    for name,expected in plan['code_hashes'].items():
        if fingerprint(ROOT/name)!=expected:raise ValueError('Changed execution dependency: '+name)
    return plan


def validate_regular(value):
    if (not isinstance(value,dict) or set(value)!={'label','rationale'} or value['label'] not in (*task.LABELS,'unresolved')
            or not isinstance(value['rationale'],str) or not value['rationale'].strip()):
        raise ValueError('Invalid regular response')


def collect_with_calls(out,calls):
    """Stage execution takes only label-free inputs and frozen instructions."""
    cases=read(out/'inputs.json');instructions=read(out/'instructions.json')
    compiler=BoundInstructionCompilerV3(calls);pipeline=BoundEvidencePipeline(calls)
    from critical.core.decision.calls import ProviderStopped,BudgetExhausted
    for key,item in sorted(instructions.items()):
        path=out/'collection/compilations'/(key+'.json')
        if path.exists():continue
        try:
            compilation=compiler.compile(item['instruction'],case_id='compile-'+key,max_tokens=CAPS['compile'])
            result={'compilation':compilation,'error':None}
        except (ProviderStopped,BudgetExhausted):raise
        except (ValueError,RuntimeError,KeyError,TypeError) as e:
            result={'compilation':None,'error':type(e).__name__}
        exact(path,result)
    for index,case in enumerate(cases,1):
        path=out/'collection/cases'/(case['case']+'.json')
        if path.exists():continue
        result={'case':case['case'],'regular':None,'regular_execution_ref':None,'regular_error':None,
                'program':None,'observation':None,'interpretation':None,'pair_ref':None,'extraction_error':None}
        try:
            value,ref=calls.call('flat_judge',{'instruction':case['instruction']},task.SCHEMA,
                template=(task.TEMPLATES/'regular.txt').read_text(),media=media_inputs(case['evidence']),
                case_id=case['case'],slot='once',max_tokens=CAPS['regular'])
            validate_regular(value);result.update(regular=value,regular_execution_ref=ref)
        except (ProviderStopped,BudgetExhausted):raise
        except (ValueError,RuntimeError,KeyError,TypeError) as e:result['regular_error']=type(e).__name__
        compilation=read(out/'collection/compilations'/(case['compilation_ref']+'.json'))
        if compilation['compilation'] is None:
            result['extraction_error']='CompilationFailed:'+str(compilation['error'])
        else:
            program=compilation['compilation']['program'];result['program']=program
            try:
                obs,interpretation,pair=pipeline.extract(program,case['evidence'],case_id=case['case'])
                result.update(observation=obs,interpretation=interpretation,pair_ref=pair)
            except (ProviderStopped,BudgetExhausted):raise
            except (ValueError,RuntimeError,KeyError,TypeError) as e:result['extraction_error']=type(e).__name__
        exact(path,result)
        print({'completed_cases':index,'total':len(cases),'case':case['case'],
               'regular_error':result['regular_error'],'extraction_error':result['extraction_error']},flush=True)


def collect(out,live=False):
    if not live:raise ValueError('Explicit paid-run authorization and --live are required')
    plan=verify_execution(out)
    from critical import config
    from critical.core.decision.calls import DurableCalls
    from critical.lm_engine import load_creds,get_engine,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT=Path(read(out/'manifest.json')['source_root']);config.CREDENTIALS_FILE=config.PROJECT_ROOT/'.env'
    creds=load_creds(provider='openai',engine='gpt')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:
        raise ValueError('Official OpenAI endpoint required')
    def factory(cap):
        return get_engine('gpt',creds=creds,model=IDENTITY['model'],temperature=0,reasoning_effort='none',
                          max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(out/'ledger/llm-histories.log'))
    calls=DurableCalls(out/'ledger',factory,identity=IDENTITY,max_calls=plan['max_requests'],
                       max_completion_tokens=plan['max_completion_tokens'],scope_limits={'search':3,'final':0})
    collect_with_calls(out,calls)
    report(out)


def metrics(rows,arm):
    correct=sum(r[arm]==r['reference']for r in rows);f1=[];recall={}
    for label in range(3):
        tp=sum(r[arm]==label and r['reference']==label for r in rows)
        fp=sum(r[arm]==label and r['reference']!=label for r in rows)
        fn=sum(r[arm]!=label and r['reference']==label for r in rows)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
        recall[task.LABELS[label]]=tp/(tp+fn) if tp+fn else None
    accepted=[r for r in rows if arm!='regular' and r['routes'][arm]['covered']]
    return {'total':len(rows),'correct':correct,'accuracy':correct/len(rows) if rows else None,
            'macro_f1':sum(f1)/3 if rows else None,'class_recall':recall,
            'unresolved':sum(r[arm]<0 for r in rows),'tree_accepted':len(accepted),
            'tree_coverage':len(accepted)/len(rows) if rows else None,
            'accepted_accuracy':sum(r[arm]==r['reference']for r in accepted)/len(accepted) if accepted else None}


def bootstrap_accuracy(rows,arm,draws=2000):
    groups={k:[r for r in rows if r['source_group']==k]for k in sorted({r['source_group']for r in rows})}
    keys=list(groups);rng=random.Random(20261020);values=[]
    for _ in range(draws):
        sampled=[r for k in rng.choices(keys,k=len(keys)) for r in groups[k]]
        values.append(sum(r[arm]==r['reference']for r in sampled)/len(sampled))
    values.sort()
    return {'source_clusters':len(keys),'draws':draws,'percentile_95':[values[int(.025*draws)],values[int(.975*draws)-1]],
            'note':'Small 16-source pilot; sibling outputs and bank replicas are not independent examples.'}


def report(out):
    verify_execution(out)
    from critical.core.calibration.shared_regions_v27 import SharedRegionGate
    from critical.core.calibration.semantic_region_merge_v28 import SemanticMergedRegionGate
    cases=read(out/'inputs.json');references=read(out/'references.json');gates={}
    for version,klass in (('v27',SharedRegionGate),('v28',SemanticMergedRegionGate)):
        for i in (1,2,3):gates[f'{version}_split{i}']=klass(read(out/f'gates/{version}_split{i}.json'))
    records=[]
    for case in cases:
        saved=read(out/'collection/cases'/(case['case']+'.json'));regular=saved['regular']
        baseline=task.LABELS.index(regular['label']) if regular and regular['label'] in task.LABELS else -1
        row={'case':case['case'],'source_group':case['source_group'],'task':case['task'],'editor':case['editor'],
             'historical_exposure':case['historical_exposure'],'reference':task.LABELS.index(references[case['case']]['reference']),
             'regular':baseline,'routes':{},'regular_execution_ref':saved['regular_execution_ref'],
             'extraction_error':saved['extraction_error'],'regular_error':saved['regular_error']}
        for name,gate in gates.items():
            route={'covered':False,'prediction':-1,'reason':'missing_or_invalid_evidence','matches':[]}
            if saved['extraction_error'] is None:
                try:
                    route=gate.select_bound(saved['program'],saved['observation'],saved['pair_ref'],saved['interpretation'])
                except (ValueError,KeyError,TypeError) as e:
                    route['reason']='gate_error:'+type(e).__name__
            row['routes'][name]=route;row[name]=route['prediction'] if route['covered'] else baseline
        records.append(row)
    arms=['regular',*sorted(gates)]
    result={'version':'aurora-pilot-report-v29','source_groups':len({r['source_group']for r in records}),'outputs':len(records),
            'arms':{a:{**metrics(records,a),'cluster_accuracy_interval':bootstrap_accuracy(records,a)}for a in arms},
            'breakdowns':{field:{value:{a:metrics([r for r in records if r[field]==value],a)for a in arms}
                                for value in sorted({r[field]for r in records})}for field in ('task','editor','historical_exposure')},
            'new_v28_acceptances':{}}
    for i in (1,2,3):
        v27,v28=f'v27_split{i}',f'v28_split{i}'
        newly=[r for r in records if r['routes'][v28]['covered'] and not r['routes'][v27]['covered']]
        result['new_v28_acceptances'][str(i)]={'cases':[r['case']for r in newly],'metrics':metrics(newly,v28),
            'wins_vs_regular':sum(r[v28]==r['reference'] and r['regular']!=r['reference']for r in newly),
            'losses_vs_regular':sum(r[v28]!=r['reference'] and r['regular']==r['reference']for r in newly)}
    exact(out/'collection/predictions.json',records);exact(out/'collection/results.json',result)
    print({'outputs':len(records),'arms':result['arms']},flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--live',action='store_true');p.add_argument('--report',action='store_true')
    a=p.parse_args();out=a.output_dir.resolve()
    if sum((a.prepare,a.live,a.report))!=1:p.error('Choose exactly one of --prepare, --live or --report')
    if a.prepare:prepare_execution(out)
    elif a.report:report(out)
    else:collect(out,live=a.live)
