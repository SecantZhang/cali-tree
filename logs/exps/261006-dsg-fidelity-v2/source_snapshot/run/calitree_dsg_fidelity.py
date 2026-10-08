"""Compare DSG observations read through the original rubric with original scores."""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

from critical.checkpoint import CheckpointStore
from critical.core.decision import dsg
from critical.core.decision.artifacts import digest, restore_program, save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, ProviderStopped, BudgetExhausted
from critical.core.decision.executor import ModelChecker, ProgramExecutor

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json'
SCORES={'no':0.0,'partial':0.5,'yes':1.0}


def code_hashes():
    files=[Path(__file__),ROOT/'critical/lm_engine/lm_template/base.py',ROOT/'critical/lm_engine/provider_api.py',
           *(ROOT/'critical/core/decision').glob('*.py'),*dsg.TEMPLATES.glob('*.txt')]
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def preflight(output):
    output=Path(output);path=output/'manifest.json'
    if path.exists():
        m=json.loads(path.read_text())
        if m['version']!=dsg.VERSION or m['code_hashes']!=code_hashes():raise ValueError('Frozen implementation changed')
    else:
        rows=json.loads(SOURCE.read_text())['cases']
        if len(rows)!=12 or len({r['group'] for r in rows})!=12 or Counter(r['target'] for r in rows)!={'yes':4,'partial':4,'no':4}:
            raise ValueError('Expected twelve balanced distinct source cases')
        m={'version':dsg.VERSION,'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','cases':rows,
           'code_hashes':code_hashes(),'source_manifest_hash':sha256(SOURCE.read_bytes()).hexdigest(),
           'repeats':5,'max_calls':450,'max_completion_tokens':512000,'reserve_calls':370,'reserve_tokens':378880,
           'planned_max_calls':418,'planned_max_tokens':477184,'max_tuples':4,
           'scope':'Score fidelity to saved original seed programs on previously observed cases; no optimization or score-guided repair.',
           'method':'DSG-inspired tuples/questions/dependencies; dependency-masked binary fraction plus text-only original-rubric readout.',
           'reference':'https://arxiv.org/abs/2310.18235','audit_policy':'Diagnostic, not a scoring-dependent selection gate.',
           'primary':'Exact label match with original at corresponding repeat slots; unresolved is not a match.',
           'score_encoding':SCORES,'order':'Freeze all graphs before evaluation; alternate original and DSG by case plus repeat.',
           'budget_scopes':'Original per case; DSG per case/draw (at most four VQA calls plus one readout). Overall cap is cumulative.'}
    for case in m['cases']:
        if restore_program(case['seed']).instruction!=case['instruction']:raise ValueError('Seed instruction mismatch')
        if any(sha256(Path(p).read_bytes()).hexdigest()!=case['image_hashes'][k] for k,p in case['evidence'].items()):raise ValueError('Image changed')
    if not path.exists():
        save_json(path,m)
        for relative in m['code_hashes']:
            p=output/'source_snapshot'/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/relative).read_bytes())
    return m


def mode(values):
    counts=Counter(v for v in values if v is not None)
    if not counts:return None
    ranked=counts.most_common()
    return ranked[0][0] if len(ranked)==1 or ranked[0][1]>ranked[1][1] else None


def case_metrics(row,target):
    original=[d['label'] for d in row['draws']['original']];other=[d['label'] for d in row['draws']['dsg']]
    n=len(original)
    if n==0 or len(other)!=n:raise ValueError('Need equal nonempty repeat sets')
    pairs=list(zip(original,other));resolved=[(a,b) for a,b in pairs if a is not None and b is not None]
    matches=sum(a is not None and a==b for a,b in pairs)
    cross=sum(a is not None and a==b for a in original for b in other)/(n*n)
    self_pairs=list(combinations(original,2))
    native=[(SCORES[a],d['dsg_score']) for a,d in zip(original,row['draws']['dsg']) if a is not None and d.get('dsg_score') is not None]
    om,dm=mode(original),mode(other)
    return {'independent_cases':1,'repeats':n,'paired_agreement':matches/n,
        'resolved_pair_agreement':matches/len(resolved) if resolved else None,'paired_coverage':len(resolved)/n,
        'all_pairs_agreement':cross,'all_five_match':matches==n,
        'original_mode':om,'dsg_mode':dm,'mode_match':om is not None and om==dm,
        'original_coverage':sum(v is not None for v in original)/n,'dsg_coverage':sum(v is not None for v in other)/n,
        'ordinal_mae':sum(abs(SCORES[a]-SCORES[b]) for a,b in resolved)/len(resolved) if resolved else None,
        'native_dsg_vs_original_ordinal_mae':sum(abs(a-b) for a,b in native)/len(native) if native else None,
        'original_self_disagreement':sum(a is None or b is None or a!=b for a,b in self_pairs)/len(self_pairs) if self_pairs else None,
        'original_reference_agreement':sum(v==target for v in original)/n,'dsg_reference_agreement':sum(v==target for v in other)/n}


def summary(result,m):
    rows=[case_metrics(result['cases'][c['id']],c['target']) for c in m['cases'] if result['cases'].get(c['id'],{}).get('completed')]
    def average(key):
        values=[r[key] for r in rows if r[key] is not None]
        return sum(values)/len(values) if values else None
    return {'completed_cases':len(rows),'structurally_valid_graphs':sum(r.get('preparation',{}).get('status')=='ready' for r in result['cases'].values()),
        'audit_approved_graphs':sum((r.get('preparation',{}).get('audit') or {}).get('accepted',False) for r in result['cases'].values()),
        **{key:average(key) for key in ('paired_agreement','resolved_pair_agreement','paired_coverage','all_pairs_agreement','ordinal_mae',
            'native_dsg_vs_original_ordinal_mae','original_coverage','dsg_coverage','original_self_disagreement','original_reference_agreement','dsg_reference_agreement')},
        'all_five_matching_cases':sum(r['all_five_match'] for r in rows),'matching_modes':sum(r['mode_match'] for r in rows)}


def report(output,result,m):
    metrics=summary(result,m);save_json(output/'summary.json',metrics)
    pct=lambda v:'n/a' if v is None else f'{v:.1%}'
    lines=['# DSG score fidelity to original programs','',m['scope'],'','Status: '+result['status'],'',
        'Original means the exact saved label-free seed program, not a human label or an optimized program.',
        'Main comparison: dependency-aware DSG observations, read through the original rubric without image access, versus fresh original execution.',
        '',f"Paired exact agreement: {pct(metrics['paired_agreement'])}; paired coverage: {pct(metrics['paired_coverage'])}.",
        f"Matching case modes: {metrics['matching_modes']}/{metrics['completed_cases']}; all repeats match: {metrics['all_five_matching_cases']}/{metrics['completed_cases']}.",
        '', '| Instruction | Graph / audit | Original labels | DSG readout labels | Exact agreement |','|---|---|---|---|---|']
    for case in m['cases']:
        row=result['cases'].get(case['id'],{});prep=row.get('preparation',{});draws=row.get('draws',{})
        labels=lambda arm:', '.join(d['label'] or '?' for d in draws.get(arm,[]))
        metric=case_metrics(row,case['target']) if row.get('completed') else {}
        lines.append('| '+' | '.join([case['instruction'].replace('|','/'),prep.get('status','pending')+' / '+str((prep.get('audit') or {}).get('accepted')),
            labels('original'),labels('dsg'),pct(metric.get('paired_agreement'))])+' |')
    lines+=['','Native DSG fraction and ordinal label score (no=0, partial=0.5, yes=1) are different constructs; their numerical difference is diagnostic, not a calibrated equivalence test.',
        'The text-only rubric readout is an explicit CaliTree adaptation, not the published DSG aggregate. It receives no original prediction or reference label.',
        'Audits are diagnostic and all structurally valid graphs execute. No score feedback changes the questions or thresholds. Global style may remain one tuple.',
        'Negative prerequisites suppress dependent questions with score zero. Unknown prerequisites remain unresolved. Supporting tuples contribute to the native DSG fraction but do not count as completed edits in the rubric readout.',
        'All statistics weight cases equally. Matching two unresolved labels never counts as score agreement. Reference accuracy is secondary, separate from original-score fidelity.',
        '', 'Error: '+str(result.get('error','none'))]
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output,m,engine_factory):
    output=Path(output);calls=DurableCalls(output,engine_factory,identity={k:m[k] for k in ('model','temperature','reasoning_effort')},
        **{k:m[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens')})
    result={'status':'running','cases':{}}
    def persist():
        result['budget']=deepcopy(calls.budget);save_json(output/'results.json',result);report(output,result,m)
    def event(value):
        with (output/'run.log').open('a') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    try:
        for index,case in enumerate(m['cases']):
            path=output/'preparation'/f'{index}.json'
            if path.exists():
                prep=json.loads(path.read_text())
                if prep.get('graph'):
                    graph=dsg.build_graph(restore_program(case['seed']),prep['tuples'],prep['questions'],prep['dependencies'])
                    if graph!=prep['graph'] or digest(graph)!=prep['graph_ref']:raise ValueError('Saved graph changed')
            else:
                prep=dsg.prepare(CaseCalls(calls,'prepare/'+case['id']),restore_program(case['seed']));save_json(path,prep)
            result['cases'][case['id']]={'preparation':prep,'draws':{'original':[],'dsg':[]},'completed':False}
            persist();event({'phase':'prepared','case':index+1,'status':prep['status'],'audit':(prep.get('audit') or {}).get('accepted'),'calls':calls.budget['calls']})
        for index,case in enumerate(m['cases']):
            row=result['cases'][case['id']];prep=row['preparation']
            original_executor=ProgramExecutor(ModelChecker(CaseCalls(calls,'original/'+case['id'])),checkpoint=CheckpointStore(output/'original_observations.jsonl'))
            for repeat in range(m['repeats']):
                for arm in (('original','dsg') if (index+repeat)%2==0 else ('dsg','original')):
                    path=output/'draws'/str(index)/arm/f'{repeat}.json'
                    if path.exists():draw=json.loads(path.read_text())
                    elif arm=='original':
                        draw=original_executor.execute(restore_program(case['seed']),case['evidence'],repeat=f'{case["id"]}/original/{repeat}',final=True).to_dict()
                        save_json(path,draw)
                    elif prep['status']=='ready':
                        draw=dsg.execute(CaseCalls(calls,f'dsg/{case["id"]}/draw/{repeat}'),prep['graph'],case['evidence'],repeat);save_json(path,draw)
                    else:
                        draw={'label':None,'graph_ref':None,'repeat':repeat,'observations':[],'outcomes':{},'dsg_score':None,'requested_fraction':None,
                              'errors':['Preparation unresolved'],'execution_refs':[]};save_json(path,draw)
                    if arm=='original' and draw['program_ref']!=case['seed']['program_ref']:raise ValueError('Original draw identity mismatch')
                    if arm=='dsg' and (draw['graph_ref']!=prep.get('graph_ref') or draw['repeat']!=repeat):raise ValueError('DSG draw identity mismatch')
                    row['draws'][arm].append(draw);persist()
            row['completed']=True;persist();event({'phase':'evaluated','case':index+1,'calls':calls.budget['calls']})
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,ValueError,KeyError,TypeError) as exc:result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    persist();return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if args.report:
        report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():parser.error('Resume requires a manifest')
    m=preflight(args.output_dir)
    if not args.live:
        print(json.dumps({'status':'ready','cases':len(m['cases']),'planned_max_calls':m['planned_max_calls'],'max_calls':m['max_calls']}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    result=execute(args.output_dir,m,lambda cap:get_engine('gpt',model='gpt-6-luna',creds=load_creds(engine='gpt'),history=history,
        max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))


if __name__=='__main__':main()
