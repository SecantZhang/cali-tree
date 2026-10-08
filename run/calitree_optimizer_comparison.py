"""Compare custom, GEPA and TextGrad on identical independently fitted leaf programs."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json, restore_program
from critical.core.decision.calls import DurableCalls, CaseCalls, ProviderStopped, BudgetExhausted, CallFailure
from critical.core.decision.compiler import ProgramCompiler
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.optimization.program import Case, CasewiseOptimizer, RepeatedEvaluator, ModelEditProposer
from critical.core.optimization.program.backends.gepa import GepaProgramOptimizer
from critical.core.optimization.program.backends.textgrad import TextGradProgramOptimizer
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import VERSION, validate_program_leaves
from critical.core.optimization.prompt.calitree.optimization.gepa import resolve_gepa_python
from run.calitree_program_optimization import ROOT, MODEL, code_hashes as runtime_hashes

METHODS = ('custom', 'gepa', 'textgrad')
SOURCE = ROOT / 'logs/exps/261006-casewise-leaf-v2'
SCOPE = ('Exploratory local fitting on twelve previously observed cases. All methods receive identical label-free saved seeds. '
         'No cross-case learning or held-out generalization evaluation.')

def dependency_fingerprints():
    spec = importlib.util.find_spec('textgrad')
    if spec is None or importlib.metadata.version('textgrad') != '0.1.8':
        raise ValueError('Install the pinned textgrad==0.1.8 environment first')
    folder = Path(spec.origin).parent
    textgrad = {'version': '0.1.8', 'source_hashes': {str(p.relative_to(folder)):sha256(p.read_bytes()).hexdigest()
                 for p in sorted(folder.rglob('*.py'))}}
    python = resolve_gepa_python()
    probe = subprocess.run([python, '-I', '-c',
        "import gepa,json; from pathlib import Path; from hashlib import sha256; from importlib.metadata import version; "
        "r=Path(gepa.__file__).parent; print(json.dumps({'version':version('gepa'),'source_hashes':"
        "{str(p.relative_to(r)):sha256(p.read_bytes()).hexdigest() for p in sorted(r.rglob('*.py'))}}))"],
        capture_output=True, text=True, check=True, timeout=20)
    return {'gepa': json.loads(probe.stdout), 'textgrad': textgrad}

def comparison_hashes():
    hashes = runtime_hashes()
    for p in [Path(__file__), * (ROOT/'critical/core/optimization/program/backends').glob('*.py')]:
        hashes[str(p.relative_to(ROOT))] = sha256(p.read_bytes()).hexdigest()
    return hashes

def preflight(output):
    output = Path(output); path = output/'manifest.json'
    hashes, dependencies = comparison_hashes(), dependency_fingerprints()
    if path.exists():
        m = json.loads(path.read_text())
        if m['version'] != 'leaf-optimizer-comparison-v1' or m['code_hashes'] != hashes or m['dependencies'] != dependencies:
            raise ValueError('Frozen implementation/dependencies changed')
        for row in m['cases']:
            restore_program(row['seed'])
            if any(sha256(Path(p).read_bytes()).hexdigest()!=row['image_hashes'][k] for k,p in row['evidence'].items()):
                raise ValueError('Frozen images changed')
        return m
    source = json.loads((SOURCE/'manifest.json').read_text())
    leaves = validate_program_leaves(json.loads((SOURCE/'leaves.json').read_text()))
    rows = []
    for row in source['cases']:
        seed = leaves['nodes']['leaf:'+row['id']]['result']['seed']
        if restore_program(seed).instruction != row['instruction']:
            raise ValueError('Source seed instruction mismatch')
        rows.append({**row, 'seed': seed})
    if len(rows)!=12 or len({r['group'] for r in rows})!=12 or Counter(r['target'] for r in rows)!={'yes':4,'partial':4,'no':4}:
        raise ValueError('Expected the full balanced twelve-case cohort')
    for row in rows:
        if any(sha256(Path(p).read_bytes()).hexdigest()!=row['image_hashes'][k] for k,p in row['evidence'].items()):
            raise ValueError('Source images changed')
    m = {'version':'leaf-optimizer-comparison-v1','scope':SCOPE,'model':MODEL,'temperature':0,'reasoning_effort':'none',
         'methods':list(METHODS),'cases':rows,'source_manifest_hash':sha256((SOURCE/'manifest.json').read_bytes()).hexdigest(),
         'code_hashes':hashes,'dependencies':dependencies,'max_calls':1800,'max_completion_tokens':2304000,
         'reserve_calls':864,'reserve_tokens':884736,'search_calls_per_case_method':26,'final_calls_per_case_method':24,
         'max_checks':4,'final_repeats':3,'native_max_steps':6,'gepa_seed':20261006,
         'gepa_options':{'candidate_selection_strategy':'pareto','use_merge':False,'acceptance_criterion':'strict_improvement'},
         'custom_options':{'rounds':2,'beam_width':2,'proposals_per_parent':2},
         'case_method_order':'rotate custom/gepa/textgrad by case index',
         'proposal_interfaces':'Custom typed transactions; GEPA/TextGrad whole-graph JSON with identical executable fields and invariants.'}
    save_json(path,m)
    for relative in hashes:
        dest=output/'source_snapshot'/relative; dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((ROOT/relative).read_bytes())
    return m

def make_optimizer(method, compiler, evaluator, output, manifest):
    if method=='custom':
        return CasewiseOptimizer(compiler,ModelEditProposer(compiler.calls),evaluator,
                    rubric=manifest['cases'][0]['seed']['program']['rubric'],**manifest['custom_options'])
    if method=='gepa':
        return GepaProgramOptimizer(compiler,evaluator,max_steps=manifest['native_max_steps'],random_seed=manifest['gepa_seed'])
    return TextGradProgramOptimizer(compiler,evaluator,max_steps=manifest['native_max_steps'],log_dir=output/'textgrad')

def summary(result, manifest):
    n=len(manifest['cases']); rows=[]
    counts=result.get('budget',{}).get('cases',{})
    for method in METHODS:
        values=[result.get('cases',{}).get(r['id'],{}).get(method,{}) for r in manifest['cases']]
        costs=[c for key,c in counts.items() if key.startswith(method+'/')]
        rows.append({'method':method,'cases':n,'completed':sum(v.get('completed',False) for v in values),
          'seed_agreement':sum(v.get('final',{}).get('seed',{}).get('agreement',0) for v in values)/n,
          'selected_agreement':sum(v.get('final',{}).get('selected',{}).get('agreement',0) for v in values)/n,
          'coverage':sum(v.get('final',{}).get('selected',{}).get('coverage',0) for v in values)/n,
          'flip_rate':sum(v.get('final',{}).get('selected',{}).get('flip_rate',0) for v in values)/n,
          'locally_fitted':sum(v.get('support_status')=='locally_fitted' for v in values),
          'changed':sum(v.get('changed',False) for v in values),
          'structurally_changed':sum(v.get('structurally_changed',False) for v in values),
          'search_calls':sum(c['search'] for c in costs),'final_calls':sum(c['final'] for c in costs),
          'completion_tokens_or_reserved':sum(c.get('completion_tokens_or_reserved',0) for c in costs)})
    return rows

def write_report(output,result,manifest):
    rows=summary(result,manifest)
    lines=['# CaliTree optimizer comparison','',SCOPE,'','Status: '+result['status'],'',
        '| Method | Seed agreement | Selected agreement | Fitted leaves | Changed programs | Structural changes | Search calls | Final calls |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['method']} | {r['seed_agreement']:.1%} | {r['selected_agreement']:.1%} | {r['locally_fitted']}/{r['cases']} | {r['changed']} | {r['structurally_changed']} | {r['search_calls']} | {r['final_calls']} |")
    lines += ['','| Instruction | Target | Custom | GEPA | TextGrad |','|---|---|---|---|---|']
    for raw in manifest['cases']:
        cells=[]
        for method in METHODS:
            r=result['cases'].get(raw['id'],{}).get(method,{})
            a=r.get('final',{}).get('selected',{}).get('agreement')
            cells.append((f'{a:.1%}' if a is not None else 'unattempted')+' / '+r.get('support_status','unresolved'))
        lines.append('| '+' | '.join([raw['instruction'].replace('|','/'),raw['target'],*cells])+' |')
    lines += ['','All arms use the same seed programs, checker, semantic audit, four-check cap, and 26-call search allowance per case.',
       'Each arm has separate fresh seed and selected comparisons after all selections for that case are frozen.',
       'The wrapper requires three matching confirmation draws and an accepted audit; final fitting status uses three additional fresh draws.',
       'Native GEPA uses Pareto selection with a single case and no merging. TextGrad uses StringBasedFunction.backward and TGD.step on the serialized graph.',
       'This compares constrained integrations, not unrestricted library defaults. Whole-graph updates and typed transactions are different proposal interfaces.',
       'A structural change means outcome count, check count, or dependency edges changed. Criterion-only revisions are reported separately.',
       'Repetitions are not independent cases. These previously observed cases cannot establish generalization or atomic semantic correctness.',
       '', 'Error: '+str(result.get('error','none'))]
    (Path(output)/'report.md').write_text('\n'.join(lines)+'\n')
    save_json(Path(output)/'summary.json',rows)

def is_structural(seed, selected):
    a,b=seed['program'],selected['program']
    return (len(a['outcomes']),len(a['checks']),sorted((c['id'],tuple(c['dependencies'])) for c in a['checks'])) != (
            len(b['outcomes']),len(b['checks']),sorted((c['id'],tuple(c['dependencies'])) for c in b['checks']))

def execute(output,manifest,engine_factory):
    output=Path(output)
    calls=DurableCalls(output,engine_factory,identity={k:manifest[k] for k in ('model','temperature','reasoning_effort')},
                       **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens')})
    result={'status':'running','scope':SCOPE,'cases':{r['id']:{} for r in manifest['cases']}}
    bundle={'version':VERSION,'nodes':{},'programs':{}}
    def persist():
        result['budget']=deepcopy(calls.budget)
        save_json(output/'results.json',result)
        if bundle['nodes']: save_json(output/'leaves.json',bundle)
        write_report(output,result,manifest)
    try:
        for index,raw in enumerate(manifest['cases']):
            case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            order=METHODS[index%3:]+METHODS[:index%3]
            contexts={}
            # Complete and persist all three selections before any final outcome for this case.
            for method in order:
                scoped=CaseCalls(calls,method+'/'+case.id)
                executor=ProgramExecutor(ModelChecker(scoped),checkpoint=CheckpointStore(output/method/'observations.jsonl'))
                evaluator=RepeatedEvaluator(executor); compiler=ProgramCompiler(scoped)
                path=output/'frozen'/method/(str(index)+'.json')
                if path.exists():
                    local=validate_program_leaves(json.loads(path.read_text()))
                else:
                    optimizer=make_optimizer(method,compiler,evaluator,output,manifest)
                    local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                            optimizer_factory=lambda _:optimizer,seeds={case.id:restore_program(raw['seed'])})
                    node=local['nodes']['leaf:'+case.id]
                    node['result']['usage']=deepcopy(calls.budget.get('cases',{}).get(method+'/'+case.id,{}))
                    save_json(path,local)
                contexts[method]=(local,evaluator)
                print(json.dumps({'phase':'frozen','case':index+1,'method':method,'calls':calls.budget['calls']}),flush=True)
            for method in order:
                local,evaluator=contexts[method]; node=local['nodes']['leaf:'+case.id]
                row={'completed':False,'search_status':node['result']['status'],'stop_reason':node['result']['stop_reason'],
                     'final':{},'changed':node['result']['seed']!=node['result']['selected'],
                     'structurally_changed':is_structural(node['result']['seed'],node['result']['selected'])}
                result['cases'][case.id][method]=row
                for arm in ('seed','selected'):
                    try:
                        p=restore_program(node['result'][arm])
                        row['final'][arm]=evaluator.evaluate(p,case,raw['target'],repeats=manifest['final_repeats'],
                                            namespace=f'{method}/{case.id}/final/{arm}',final=True)
                    except (BudgetExhausted,CallFailure,ValueError) as exc:
                        row['error']=str(exc)
                    persist()
                final=row['final'].get('selected',{})
                audit=node['result']['candidates'].get(node['program_ref'],{}).get('audit',{})
                row['support_status']=('locally_fitted' if final.get('agreement')==1 and final.get('coverage')==1 and audit.get('accepted') else
                                       'unresolved' if final.get('coverage',0)<1 else 'unstable' if final.get('flip_rate',0)>0 else 'unmatched')
                row['completed']=True
                row['usage']=deepcopy(calls.budget.get('cases',{}).get(method+'/'+case.id,{}))
                node['id']=f'leaf:{method}/{case.id}'
                node.update(method=method,support_status=row['support_status'],final_comparison=row['final'])
                bundle['nodes'][node['id']]=node; bundle['programs'].update(local['programs'])
                persist()
                print(json.dumps({'phase':'final','case':index+1,'method':method,'status':row['support_status'],'calls':calls.budget['calls']}),flush=True)
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,KeyError,TypeError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    persist()
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'): modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text())); return
    if args.resume and not (args.output_dir/'manifest.json').exists(): parser.error('Resume needs an existing manifest')
    manifest=preflight(args.output_dir)
    if not args.live:
        print(json.dumps({'status':'ready','cases':len(manifest['cases']),'methods':METHODS,'max_calls':manifest['max_calls']})); return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True); history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    result=execute(args.output_dir,manifest,lambda cap:get_engine('gpt',model=MODEL,creds=load_creds(engine='gpt'),
                    history=history,max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))

if __name__=='__main__': main()
