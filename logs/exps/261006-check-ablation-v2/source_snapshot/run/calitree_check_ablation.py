"""Test identical visual rules in combined and separately executed prompts."""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from critical.core.decision.ablation import (VERSION, TEMPLATES, prepare, execute_draw, draw_metrics,
                                             paired_sign_flip, make_bank)
from critical.core.decision.artifacts import save_json, restore_program, digest
from critical.core.decision.calls import DurableCalls, CaseCalls, ProviderStopped, BudgetExhausted

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/261006-optimizer-comparison-v1/manifest.json'
ARMS = ('combined', 'separated')


def source_hashes():
    paths = [Path(__file__), ROOT/'critical/lm_engine/lm_template/base.py', ROOT/'critical/lm_engine/provider_api.py',
             *(ROOT/'critical/core/decision').glob('*.py'), *TEMPLATES.glob('*.txt')]
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def preflight(output):
    output = Path(output); path = output/'manifest.json'
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest['version'] != VERSION or manifest['code_hashes'] != source_hashes():
            raise ValueError('Frozen implementation changed')
    else:
        source = json.loads(SOURCE.read_text())
        rows = deepcopy(source['cases'])
        if len(rows) != 12 or len({r['group'] for r in rows}) != 12 or Counter(r['target'] for r in rows) != {'yes':4,'partial':4,'no':4}:
            raise ValueError('Expected the twelve distinct balanced prior cases')
        manifest = {'version':VERSION, 'model':'gpt-6-luna', 'temperature':0, 'reasoning_effort':'none',
            'cases':rows, 'code_hashes':source_hashes(), 'source_manifest_hash':sha256(SOURCE.read_bytes()).hexdigest(),
            'repeats':5, 'max_calls':400, 'max_completion_tokens':409600, 'reserve_calls':300, 'reserve_tokens':307200,
            'scope':'Previously observed cases; label-blind shared rule compilation. Execution-format ablation, no optimizer search.',
            'primary_metric':'Mean case-level pairwise final-label inconsistency; any unresolved member counts as inconsistent.',
            'secondary_metrics':['resolved-pair disagreement','atomic inconsistency','reference agreement','coverage','fully matching cases','usage'],
            'order':'Prepare all cases before any evaluation; alternate arms by case index plus repeat index.',
            'criteria':'Two or three atomic facts and complete/partial/absent/unknown outcome criteria, identical between arms.',
            'separated_fulfillment':'One text-only call receives the independent observations; no image access.',
            'planned_maximum_calls':324, 'planned_maximum_completion_tokens':356352}
    for row in manifest['cases']:
        if restore_program(row['seed']).instruction != row['instruction']:
            raise ValueError('Seed instruction mismatch')
        if any(sha256(Path(p).read_bytes()).hexdigest() != row['image_hashes'][key] for key,p in row['evidence'].items()):
            raise ValueError('Image identity changed')
    if not path.exists():
        save_json(path,manifest)
        for relative in manifest['code_hashes']:
            target=output/'source_snapshot'/relative; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/relative).read_bytes())
    return manifest


def summarize(result, manifest):
    complete = [case for case in manifest['cases'] if result['cases'].get(case['id'],{}).get('completed')]
    rows=[]
    for arm in ARMS:
        reports=[draw_metrics(result['cases'][c['id']]['draws'][arm],c['target']) for c in complete]
        costs=[v for k,v in result['budget']['cases'].items() if k.startswith(arm+'/')]
        n=len(reports)
        mean=lambda key: sum(r[key] for r in reports if r[key] is not None)/sum(r[key] is not None for r in reports) if any(r[key] is not None for r in reports) else None
        rows.append({'arm':arm,'completed_cases':n,'eligible_cases':sum(result['cases'][c['id']]['preparation']['status']=='ready' for c in complete),
            **{key:mean(key) for key in ('agreement','coverage','pairwise_inconsistency','resolved_pairwise_disagreement','atomic_inconsistency')},
            'fully_matching':sum(r['all_matching'] for r in reports),'fully_consistent':sum(r['all_resolved_consistent'] for r in reports),
            'failed_draws':sum(r['transport_or_schema_failed_draws'] for r in reports),
            'calls':sum(v['final'] for v in costs),'charged_completion_tokens':sum(v['completion_tokens_or_reserved'] for v in costs),
            'measured_input_tokens':sum(v.get('input_tokens',0) for v in costs)})
    differences=[]
    for case in complete:
        row=result['cases'][case['id']]
        if row['preparation']['status']=='ready':
            a,b=[draw_metrics(row['draws'][arm],case['target'])['pairwise_inconsistency'] for arm in ARMS]
            differences.append(b-a)
    return {'arms':rows, 'paired_inconsistency_separated_minus_combined':paired_sign_flip(differences)}


def write_report(output, result, manifest):
    metrics=summarize(result,manifest);save_json(output/'summary.json',metrics)
    pct=lambda value: 'n/a' if value is None else f'{value:.1%}'
    lines=['# Combined versus separated visual checks','',manifest['scope'],'','Status: '+result['status'],'',
           '| Arm | Cases | Agreement | Coverage | Pairwise inconsistency | Resolved-pair disagreement | Atomic inconsistency | Fully matching | Fully consistent | Calls |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in metrics['arms']:
        lines.append('| '+' | '.join([row['arm'],str(row['completed_cases']),*(pct(row[k]) for k in ('agreement','coverage','pairwise_inconsistency','resolved_pairwise_disagreement','atomic_inconsistency')),
            str(row['fully_matching']),str(row['fully_consistent']),str(row['calls'])])+' |')
    lines += ['','| Instruction | Target | Preparation | Combined agreement / inconsistency | Separated agreement / inconsistency |','|---|---|---|---|---|']
    for case in manifest['cases']:
        row=result['cases'].get(case['id'],{});cells=[]
        for arm in ARMS:
            draws=row.get('draws',{}).get(arm,[])
            metric=draw_metrics(draws,case['target']) if len(draws)==manifest['repeats'] else {}
            cells.append(pct(metric.get('agreement'))+' / '+pct(metric.get('pairwise_inconsistency')))
        lines.append('| '+' | '.join([case['instruction'].replace('|','/'),case['target'],row.get('preparation',{}).get('status','pending'),*cells])+' |')
    lines += ['', 'Paired exact sign-flip diagnostic (case-level; separated minus combined): '+json.dumps(metrics['paired_inconsistency_separated_minus_combined']),
              '', 'Unknown/failed predictions count as incorrect and as inconsistent with any paired draw. Resolved-only disagreement is diagnostic and omits missing observations.',
              'Each case contributes equally; five draws do not create five independent cases. Atomic consistency is not correctness.',
              'Combined returns all fact observations and outcome judgments in one image call. Separated executes each fact in an isolated image call, then applies the same decision criteria in a text-only fulfillment call.',
              'Interpret any difference as an execution-format effect, including context isolation and extra calls, not a pure prompt-length effect. Criteria are identical; separate execution costs more.',
              'Preparation failures remain unresolved in full-cohort metrics and are excluded from the paired execution-effect diagnostic.',
              'No optimization or feedback uses these final results. Historical observation and small case count limit inference.', '', 'Error: '+str(result.get('error','none'))]
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output, manifest, engine_factory):
    output=Path(output)
    calls=DurableCalls(output,engine_factory,identity={k:manifest[k] for k in ('model','temperature','reasoning_effort')},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens')})
    result={'status':'running','cases':{}}
    def event(row):
        with (output/'run.log').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def persist():
        result['budget']=deepcopy(calls.budget);save_json(output/'results.json',result);write_report(output,result,manifest)
    try:
        for index,case in enumerate(manifest['cases']):
            path=output/'preparation'/f'{index}.json'
            if path.exists():
                record=json.loads(path.read_text())
                if record.get('bank'):
                    bank=record['bank']
                    graph={k:bank[k] for k in ('representable','reason','facts','decisions')}
                    if bank != make_bank(restore_program(case['seed']),graph) or digest(bank)!=record['bank_ref']:
                        raise ValueError('Saved bank identity changed')
            else:
                record=prepare(CaseCalls(calls,'prepare/'+case['id']),restore_program(case['seed']),case['evidence'])
                save_json(path,record)
            result['cases'][case['id']]={'preparation':record,'draws':{arm:[] for arm in ARMS},'completed':False}
            persist();event({'phase':'prepare','case':index+1,'status':record['status'],'calls':calls.budget['calls']})
        # Freeze every bank and audit before starting either execution arm.
        for index,case in enumerate(manifest['cases']):
            row=result['cases'][case['id']];record=row['preparation']
            for repeat in range(manifest['repeats']):
                order=ARMS if (index+repeat)%2==0 else ARMS[::-1]
                for arm in order:
                    path=output/'draws'/str(index)/arm/f'{repeat}.json'
                    if path.exists():
                        draw=json.loads(path.read_text())
                        if draw['bank_ref']!=record.get('bank_ref') or draw['arm']!=arm or draw['repeat']!=repeat:
                            raise ValueError('Saved draw identity changed')
                    elif record['status']!='ready':
                        draw={'bank_ref':record.get('bank_ref'),'arm':arm,'repeat':repeat,'facts':{},'outcomes':{},'label':None,
                              'errors':['Preparation '+record['status']],'execution_refs':[]}
                        save_json(path,draw)
                    else:
                        draw=execute_draw(CaseCalls(calls,arm+'/'+case['id']),record['bank'],case['evidence'],arm,repeat)
                        save_json(path,draw)
                    row['draws'][arm].append(draw)
                    persist()
            row['completed']=True;persist()
            event({'phase':'evaluated','case':index+1,'calls':calls.budget['calls']})
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,ValueError,KeyError,TypeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    persist();return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():parser.error('Resume requires an existing manifest')
    manifest=preflight(args.output_dir)
    if not args.live:
        print(json.dumps({'status':'ready','cases':len(manifest['cases']),'max_calls':400,'planned_maximum_calls':324}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    result=execute(args.output_dir,manifest,lambda cap:get_engine('gpt',model='gpt-6-luna',creds=load_creds(engine='gpt'),
        history=history,max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))


if __name__=='__main__':main()
