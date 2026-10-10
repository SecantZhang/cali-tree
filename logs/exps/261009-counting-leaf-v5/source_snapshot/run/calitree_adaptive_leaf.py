"""Fresh 12-case v4 Luna-only/adaptive comparison. Only --live contacts OpenAI."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path

from PIL import Image
from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, RoutedCalls, CallFailure, BudgetExhausted, ProviderStopped
from critical.core.decision.robust.models import restore_program as restore_original
from critical.core.decision.robust.v4_models import export_program, restore_program, validate
from critical.core.decision.robust.v4_construction import EvidenceCompiler
from critical.core.decision.robust.v4_runtime import EvidenceChecker, EvidenceExecutor
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.adaptive import create_adaptive_evidence_optimizer
from critical.core.optimization.program.robust.metrics import RobustEvaluator, RobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import ADAPTIVE_VERSION, validate_program_leaves
from critical.core.optimization.prompt.calitree.node.program_leaf import COUNTING_VERSION
from critical.core.decision.counting import CountingCompiler, CountingChecker, CountingExecutor, restore_program as restore_counting
from critical.core.optimization.program.robust.counting import create_counting_leaf_optimizer
from critical.core.optimization.program.robust.metrics import NoAuditRobustPolicy
from run.calitree_robust_leaf_optimization import ROOT, code_hashes, status_for
from run.calitree_typed_twelve import bridge_reference
from run.calitree_resume_typed_twelve import install_failure_replay

SOURCE=ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json'
ARMS=('luna_only','luna_then_sol')
PRIMARY={'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none'}
SOL={'model':'gpt-6.1-sol','provider':'openai','temperature':None,'reasoning_effort':'medium'}


def preflight(output, *, scoring='semantic'):
    if scoring not in ('semantic','counting'):raise ValueError('Unknown scoring mode')
    old=json.loads(SOURCE.read_text());cases=[];groups=set()
    if len(old['cases'])!=12 or Counter(c['target'] for c in old['cases'])!={'yes':4,'partial':4,'no':4}:
        raise ValueError('Expected the exact balanced original twelve-case collection')
    for raw in old['cases']:
        c={k:deepcopy(raw[k]) for k in ('id','instruction','target','evidence','image_hashes','group')}
        original=bridge_reference(raw['seed']);c.update(original={'program_ref':original.ref,'program':original.to_dict()},rubric=original.rubric)
        for key,path in c['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest()!=c['image_hashes'][key]:raise ValueError('Changed frozen image')
        with Image.open(c['evidence']['source_image']) as im:
            pixels=im.convert('RGB');group=sha256(str(pixels.size).encode()+pixels.tobytes()).hexdigest()
        if group!=c['group'] or group in groups:raise ValueError('Changed/repeated source group')
        groups.add(group);cases.append(c)
    hashes=code_hashes()
    for directory,pattern in [('critical/lm_engine','*.py'),('critical/core/prompts/templates','*.txt')]:
        for p in (ROOT/directory).rglob(pattern):hashes[str(p.relative_to(ROOT))]=sha256(p.read_bytes()).hexdigest()
    for p in (Path(__file__),ROOT/'run/calitree_typed_twelve.py',ROOT/'run/calitree_resume_typed_twelve.py',ROOT/'run/calitree_resume_frozen.py'):
        hashes[str(p.relative_to(ROOT))]=sha256(p.read_bytes()).hexdigest()
    counting_source=ROOT/'critical/core/decision/counting.py'
    hashes[str(counting_source.relative_to(ROOT))]=sha256(counting_source.read_bytes()).hexdigest()
    package=Path(importlib.util.find_spec('textgrad').origin).parent
    manifest={'version':'adaptive-leaf-twelve-v4','protocol':'typed-evidence-v2','cases':cases,'arms':list(ARMS),
        'scope':'Twelve previously observed local fitting cases, four per class. Repeats are within-case measurements. No held-out generalization or atomic correctness claim.',
        'primary_identity':deepcopy(PRIMARY),'routes':{'sol-proposer':deepcopy(SOL)},'random_seed':20261009,
        'policy':asdict(RobustPolicy()),'stall_threshold':3,'max_rounds':15,'proposals_per_round':2,
        'max_calls':3600,'max_completion_tokens':4608000,'reserve_calls':960,'reserve_tokens':983040,
        'scope_limits':{'search':109,'final':40},'shared_preparation_calls_per_case':2,'max_sol_proposal_calls':144,
        'checker_cap':1024,'proposal_cap':4096,'other_cap':2048,'workers':1,'initial_supports':2,
        'max_checks':4,'max_depth':4,'arm_order':'rotate by case index','source_manifest_hash':sha256(SOURCE.read_bytes()).hexdigest(),
        'historical_observations_reused':False,'historical_feedback_reused':False,'code_hashes':hashes,
        'dependencies':{'textgrad':importlib.metadata.version('textgrad'),'hashes':{str(p.relative_to(package)):sha256(p.read_bytes()).hexdigest() for p in package.rglob('*.py')}}}
    if scoring=='counting':
        manifest.update(version='counting-leaf-twelve-v5',protocol='typed-counting-v1',scoring='counting',
            semantic_audit=False,model_readout=False,aggregation='required-condition-all-some-none-count-v1',
            shared_preparation_calls_per_case=1,max_depth=1)
        manifest.pop('initial_supports')
    path=Path(output)/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('Frozen settings, code, dependency or images changed')
    else:
        save_json(path,manifest)
        for rel in hashes:
            p=Path(output)/'source_snapshot'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    return manifest


def write_report(output,result,manifest):
    n=len(manifest['cases']);summaries={};lines=['# '+('Counting-only leaf experiment' if manifest.get('scoring')=='counting' else 'V4 uncertainty handling and adaptive proposer experiment'),'',manifest['scope'],'',
        'Status: '+result['status'],'',
        'Agreement means reference matches; coverage means a resolved answer, including wrong answers. Each case has five fresh final draws. '
        'Missing or unresolved draws count as nonmatches; repeated draws are not additional cases. Both arms use the corrected runtime and strict gates.','',
        '| Arm | Seed → selected matches | Selected resolved | Locally robust cases | Escalated cases |',
        '|---|---:|---:|---:|---:|']
    if manifest.get('scoring')=='counting':
        lines.insert(6,'Semantic auditing is disabled. All independent required conditions pass → yes; all fail → no; mixed → partial; any unknown → unresolved. No model readout runs. The confidence/repeat gates still govern empirical robust status.')
    for arm in manifest['arms']:
        rows=[result['cases'].get(c['id'],{}).get(arm,{}) for c in manifest['cases']]
        s={'cases':n,'robust':sum(r.get('support_status')=='locally_robust' for r in rows),
            'escalated':sum(r.get('escalated',False) for r in rows)}
        for which in ('seed','selected'):
            s[which]={k:sum(r.get('final',{}).get(which,{}).get(k,0)*5 for r in rows) for k in ('agreement','coverage')}
        summaries[arm]=s
        lines.append(f"| {arm} | {round(s['seed']['agreement'])} → {round(s['selected']['agreement'])} / {n*5} | {round(s['selected']['coverage'])} / {n*5} | {s['robust']} / {n} | {s['escalated']} / {n} |")
    lines+=['','| Instruction / reference | Arm | Seed → selected matches / 5 | Resolved / 5 | Mean executed checks | Confidence gate | Status / failure reason |',
            '|---|---|---:|---:|---:|---|---|']
    for c in manifest['cases']:
        for arm in manifest['arms']:
            r=result['cases'].get(c['id'],{}).get(arm,{});a=r.get('final',{}).get('seed',{});b=r.get('final',{}).get('selected',{})
            lines.append('| '+' | '.join([c['instruction'].replace('|','/')+' / '+c['target'],arm,
                f"{round(a.get('agreement',0)*5)} → {round(b.get('agreement',0)*5)}" if b else 'unavailable',
                str(round(b.get('coverage',0)*5)) if b else '0',f"{b['mean_checks']:.1f}" if b else '—',
                'passed' if b.get('confidence_pass') else 'failed/unavailable',
                r.get('support_status',r.get('phase','pending'))+'; '+', '.join(r.get('acceptance',{}).get('reasons',[]))+(('; '+r['error']) if r.get('error') else '')])+' |')
    class_metrics={};by_model={}
    for arm in manifest['arms']:
        class_metrics[arm]={}
        for label in ('yes','partial','no'):
            cases=[c for c in manifest['cases'] if c['target']==label]
            class_metrics[arm][label]={'cases':len(cases),'planned_draws':len(cases)*5}
            for which in ('seed','selected'):
                finals=[result['cases'].get(c['id'],{}).get(arm,{}).get('final',{}).get(which,{}) for c in cases]
                class_metrics[arm][label][which]={'matches':round(sum(v.get('agreement',0)*5 for v in finals)),
                    'resolved':round(sum(v.get('coverage',0)*5 for v in finals))}
    for p in (Path(output)/'jobs').glob('*.json'):
        j=json.loads(p.read_text());model=j.get('response',{}).get('model',j.get('requested_identity',manifest['primary_identity'])['model'])
        u=by_model.setdefault(model,{'calls':0,'input_tokens':0,'charged_completion_tokens':0,'failures':0})
        response=j.get('response',{});u['calls']+=1;u['input_tokens']+=int(response.get('promptTokens',0))
        u['charged_completion_tokens']+=int(response.get('completionTokens',j['max_tokens']))
        u['failures']+=j['outcome']!='completed'
    lines+=['','## Per-case execution details','',
        'Consistency is measured separately from reference agreement. An uncertain answer can repeat consistently yet fail the known-answer stability gate. '
        'Skipped checks remain untested. The observation counts below count checks across five runs, not independent cases.']
    for c in manifest['cases']:
        for arm in manifest['arms']:
            r=result['cases'].get(c['id'],{}).get(arm,{})
            if not r.get('final'):continue
            lines+=['','### '+c['instruction']+' — '+arm,'',
                '| Measurement | Seed | Selected |','|---|---:|---:|']
            for label,key,scale in [('Reference matches / 5','agreement',5),('Resolved draws / 5','coverage',5),
                ('Final-label consistency','label_consistency',1),('Minimum requirement consistency','requirement_consistency',1),
                ('Mean executed checks','mean_checks',1),('Mean charged completion tokens','mean_completion_tokens',1)]:
                lines.append('| '+label+' | '+' | '.join(f"{r['final'].get(w,{}).get(key,0)*scale:.2f}" if w in r['final'] else 'pending' for w in ('seed','selected'))+' |')
            for which in ('seed','selected'):
                if which not in r['final']:continue
                final=r['final'][which];counts=Counter(o.get('event','unknown') for t in final['traces'] for o in t['observations'])
                lines+=['',which.capitalize()+' labels: '+json.dumps(final['label_distribution'])+'. Observation events: '+json.dumps(dict(counts))+'.',
                        'Confidence per check: '+json.dumps({k:v['confidence'] for k,v in final['nodes'].items()})+'.',
                        'Known-answer consistency per check: '+json.dumps({k:v['consistency'] for k,v in final['nodes'].items()})+'.']
            lines+=['','Search schedule: '+json.dumps(r.get('search_schedule',{}))+'. Stop: '+r.get('stop_reason','')+'.',
                'Escalated: '+str(r.get('escalated',False))+'. Usage: '+json.dumps(r.get('usage',{}))+'.']
    lines+=['','## Accounting','',json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('attempted_slots','cases','limits')},indent=2),
        '', 'Returned models: '+', '.join(result.get('returned_models',[])), 'Error: '+str(result.get('error','none')),
        '', 'Historical results are descriptive. This comparison isolates proposer escalation under the same new runtime. '
        'Confidence is self-report, semantic audit is fallible, and unvisited alternatives remain untested. '
        'A reference-conflict flag requests review; it does not certify that the saved label is wrong.']
    Path(output).mkdir(parents=True,exist_ok=True)
    (Path(output)/'report.md').write_text('\n'.join(lines)+'\n');save_json(Path(output)/'summary.json',summaries)
    save_json(Path(output)/'class_metrics.json',class_metrics);save_json(Path(output)/'usage_by_model.json',by_model)


def execute(output,manifest,primary_factory,sol_factory,*,progress=True):
    install_failure_replay();output=Path(output);counting=manifest.get('scoring')=='counting'
    policy=(NoAuditRobustPolicy if counting else RobustPolicy)(**manifest['policy'])
    restore_saved=restore_counting if counting else restore_program
    compiler_type=CountingCompiler if counting else EvidenceCompiler
    checker_type=CountingChecker if counting else EvidenceChecker
    executor_type=CountingExecutor if counting else EvidenceExecutor
    calls=DurableCalls(output,primary_factory,identity=manifest['primary_identity'],
        routes={'sol-proposer':{'identity':manifest['routes']['sol-proposer'],'engine_factory':sol_factory}},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    result={'status':'running','cases':{c['id']:{} for c in manifest['cases']}}
    bundle={'version':COUNTING_VERSION if counting else ADAPTIVE_VERSION,'nodes':{},'programs':{}}
    def emit(value):
        if progress:print(json.dumps(value),flush=True)
    def persist():
        result['budget']=deepcopy(calls.budget);save_json(output/'results.json',result)
        if bundle['nodes']:save_json(output/'leaves.json',validate_program_leaves(bundle))
        write_report(output,result,manifest)
    try:
        for i,raw in enumerate(manifest['cases']):
            original=restore_original(raw['original']);case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            prep=output/'prepared'/f'{i}.json';prepared=json.loads(prep.read_text()) if prep.exists() else {}
            compiler=compiler_type(CaseCalls(calls,'prepare/'+case.id),original)
            if 'seed' not in prepared and 'error' not in prepared:
                try:prepared['seed']=export_program(compiler.compile(case.instruction,raw['rubric'],slot='common_seed'))
                except (CallFailure,BudgetExhausted,ValueError,TypeError,KeyError) as exc:prepared.update(error=str(exc),failure=type(exc).__name__)
                save_json(prep,prepared)
            if counting:
                prepared['semantic_audit']={'status':'disabled','performed':False};save_json(prep,prepared)
            if not counting and 'seed' in prepared and 'seed_audit' not in prepared and 'audit_error' not in prepared:
                try:prepared['seed_audit']=compiler.audit(restore_saved(prepared['seed']),slot='common_seed_audit')
                except (CallFailure,BudgetExhausted,ValueError,TypeError,KeyError) as exc:prepared.update(audit_error=str(exc),audit_failure=type(exc).__name__)
                save_json(prep,prepared)
            emit({'phase':'prepared','case':i+1,'valid_seed':'seed' in prepared,'calls':calls.budget['calls']})
            order=manifest['arms'][i%2:]+manifest['arms'][:i%2]
            for arm in order:
                frozen=output/'frozen'/arm/f'{i}.json'
                if not frozen.exists():
                    if 'error' in prepared:save_json(frozen,prepared)
                    else:
                        scoped=CaseCalls(calls,arm+'/'+case.id)
                        def on_round(e):emit({'phase':'round','case':i+1,'arm':arm,'round':e['round']+1,
                            'route':e['route'],'stall':e.get('stall_after',e['stall_before']),'completed':e.get('completed',False),'calls':calls.budget['calls']})
                        options=dict(proposer_policy=arm,
                            sol_calls=RoutedCalls(scoped,'sol-proposer') if arm=='luna_then_sol' else None,
                            checkpoint=CheckpointStore(output/'observations'/arm/f'{i}.jsonl'),policy=policy,
                            max_rounds=manifest['max_rounds'],progress=on_round)
                        if not counting:options['seed_audit']=prepared.get('seed_audit',{'accepted':False,'reason':'Shared seed audit unavailable; '+prepared.get('audit_error','')})
                        opt=(create_counting_leaf_optimizer if counting else create_adaptive_evidence_optimizer)(scoped,original,**options)
                        local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                            optimizer_factory=lambda _:opt,seeds={case.id:restore_saved(prepared['seed'])})
                        save_json(frozen,local)
                result['cases'][case.id][arm]={'phase':'frozen'};persist()
                emit({'phase':'frozen','case':i+1,'arm':arm,'calls':calls.budget['calls']})
        freeze={'all_selections_frozen':True,'calls_before_final':calls.budget['calls'],
            'hashes':{str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'frozen').rglob('*.json')}}
        freeze_path=output/'selection_freeze.json'
        if freeze_path.exists():
            if json.loads(freeze_path.read_text())['hashes']!=freeze['hashes']:raise ValueError('Frozen selection changed before final replay')
        else:save_json(freeze_path,freeze)
        for i,raw in enumerate(manifest['cases']):
            case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            for arm in manifest['arms']:
                local=json.loads((output/'frozen'/arm/f'{i}.json').read_text());row={'final':{}}
                result['cases'][case.id][arm]=row
                if 'error' in local:
                    row.update(support_status='unresolved',error=local['error']);persist();continue
                validate_program_leaves(local);node=local['nodes']['leaf:'+case.id];saved=node['result']
                scoped=CaseCalls(calls,arm+'/'+case.id)
                evaluator=RobustEvaluator(executor_type(checker_type(scoped),checkpoint=CheckpointStore(output/'observations'/arm/f'{i}.jsonl')),policy)
                for which in ('seed','selected'):
                    program=restore_saved(saved[which])
                    if counting:
                        from critical.core.decision.counting import validate as validate_counting
                        validate_counting(program,restore_original(raw['original']))
                    else:validate(program,restore_original(raw['original']))
                    row['final'][which]=evaluator.evaluate(program,case,raw['target'],repeats=5,namespace='final/'+which,final=True);persist()
                candidate=saved['candidates'].get(saved['selected']['program_ref'],{});audit=candidate.get('audit',{})
                status,assessment=status_for(row['final']['selected'],audit,policy)
                confirmation=candidate.get('confirmation');confirmed=bool(confirmation and policy.assess(confirmation,audit)['qualified'])
                if not confirmed:assessment['reasons'].append('confirmation_missing_or_unqualified')
                assessment['qualified']=assessment['qualified'] and confirmed
                history=saved['lineage'][-1]
                row.update(phase='final',support_status='locally_robust' if assessment['qualified'] else status,
                    acceptance=assessment,confirmed=confirmed,escalated=history['escalated'],search_schedule=history['search_schedule'],
                    escalation_events=[{k:e[k] for k in ('round','route','stall_before','trigger')} for e in history['events']],
                    stop_reason=saved['stop_reason'],usage=deepcopy(calls.budget['cases'].get(arm+'/'+case.id,{})))
                if not confirmed and status=='locally_robust':row['support_status']='unconfirmed'
                node.update(id='leaf:'+arm+'/'+case.id,arm=arm,support_status=row['support_status'],final_comparison=row['final'])
                bundle['nodes'][node['id']]=node;bundle['programs'].update(local['programs']);persist()
                emit({'phase':'final','case':i+1,'arm':arm,'status':row['support_status'],'calls':calls.budget['calls']})
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,KeyError,TypeError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    jobs=[json.loads(p.read_text()) for p in (output/'jobs').glob('*.json')]
    result['returned_models']=sorted({j['response'].get('model','unavailable') for j in jobs if j.get('response')})
    result['route_calls']=dict(Counter(j.get('route','primary') for j in jobs))
    if result['route_calls'].get('sol-proposer',0)>manifest.get('max_sol_proposal_calls',144):raise ValueError('Sol route ceiling exceeded')
    persist();return result


def run_demo(output):
    """Synthetic production example: independent closure survives uncertain progress."""
    from critical.core.optimization.program.robust.demo import example_program
    from critical.core.decision.robust.v4_construction import construct
    output=Path(output);output.mkdir(parents=True,exist_ok=True);original=example_program()
    spec={'supports':[{'requirement_id':'r','question':'Did red increase?','criteria':'Compare progress','binding':'square',
        'evidence_from':[],'required_evidence_from':[],'activation_source':0,'activation_states':[]},
        {'requirement_id':'r','question':'Is the square fully red?','criteria':'Inspect the edited square','binding':'square',
        'evidence_from':[1],'required_evidence_from':[],'activation_source':0,'activation_states':[]}],
        'fulfillment_criteria':'Complete if s2 passes even if s1 unknown; otherwise unresolved.','fulfillment_required':[]}
    program=construct(original,spec);images={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        p=output/f'{key}.png';Image.new('RGB',(8,8),color).save(p);images[key]=str(p)
    class Checker:
        identity={'model':'offline-synthetic'}
        def check(self,p,n,o,e,d,**kw):return {'status':{'s1':'unknown','s2':'pass','fulfillment':'complete'}[n.id],
            'evidence':'Synthetic observation, not a model result','confidence':.99,'completion_tokens':0}
    trace=EvidenceExecutor(Checker()).execute(program,images)
    save_json(output/'program.json',export_program(program));save_json(output/'trace.json',trace)
    return {'synthetic':True,'label':trace['label'],'queried':[o['check_id'] for o in trace['observations'] if o['queried']]}


def run_counting_demo(output):
    from critical.core.decision.counting import CountingProgram,Decision,template as counting_template
    from critical.core.optimization.program.robust.demo import example_program
    output=Path(output);output.mkdir(parents=True,exist_ok=True);original=example_program()
    program=CountingProgram(original.instruction,original.rubric,original.requirements,original.outcomes,
        (Decision('d1','r','Is the upper half red?','Pass if upper half is red','upper half of square'),
         Decision('d2','r','Is the lower half red?','Pass if lower half is red','lower half of square')),counting_template('check'))
    source=output/'source.png';Image.new('RGB',(8,8),'blue').save(source)
    class PixelChecker:
        identity={'checker':'offline-pixel-ground-truth'}
        def check(self,p,n,evidence,**kw):
            with Image.open(evidence['edited_image']) as im:
                box=(0,0,8,4) if n.id=='d1' else (0,4,8,8)
                colors=im.convert('RGB').crop(box).getcolors(64)
                passed=all(r>g and r>b for _,(r,g,b) in colors)
            return {'status':'pass' if passed else 'fail','evidence':'Synthetic uniform region checked directly from pixels',
                    'confidence':1.0,'completion_tokens':0}
    rows={}
    for name,upper,lower in [('all_pass','red','red'),('mixed','red','blue'),('all_fail','blue','blue')]:
        edited=Image.new('RGB',(8,8),lower);edited.paste(upper,(0,0,8,4));path=output/f'{name}.png';edited.save(path)
        rows[name]=CountingExecutor(PixelChecker()).execute(program,{'source_image':str(source),'edited_image':str(path)},repeat=name)
    save_json(output/'program.json',export_program(program));save_json(output/'counting_demo.json',rows)
    return {'synthetic':True,'semantic_audit':'disabled','model_readout':False,'labels':{k:v['label'] for k,v in rows.items()}}


def release_transport_stop(output):
    """Explicit CLI authorization releases one stop, never retries attempted slots."""
    path=Path(output)/'budget.json';budget=json.loads(path.read_text())
    if budget.get('stopped')!='Three consecutive transport failures':
        raise ValueError('Only an explicitly requested transport continuation can release this latch')
    record={'version':'v4-authorized-transport-continuation','calls':budget['calls'],
        'charged_completion_tokens':budget['completion_tokens_or_reserved'],
        'prior_budget_sha256':sha256(path.read_bytes()).hexdigest(),'failed_slots_retried':False,
        'authorization':'Explicit --resume --release-transport-stop invocation'}
    destination=Path(output)/'transport_resumes'/f"{budget['calls']}.json"
    if destination.exists():raise ValueError('This transport stop was already released')
    save_json(destination,record)
    budget.update(stopped=None,consecutive_errors=0,authorized_resumes=[*budget.get('authorized_resumes',[]),record])
    save_json(path,budget)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('offline-demo','preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--scoring',choices=('counting','semantic'),help='New runs default to counting without semantic audits or model readout; stored runs retain their mode')
    parser.add_argument('--release-transport-stop',action='store_true',help='Explicitly authorize one transport continuation; preserve all attempted slots and charges')
    args=parser.parse_args()
    if args.offline_demo:
        print(json.dumps((run_demo if args.scoring=='semantic' else run_counting_demo)(args.output_dir)));return
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():parser.error('Resume needs a frozen manifest')
    saved_manifest=args.output_dir/'manifest.json'
    prior=json.loads(saved_manifest.read_text()) if saved_manifest.exists() else {}
    scoring=args.scoring or prior.get('scoring', 'semantic' if prior else 'counting')
    m=preflight(args.output_dir,scoring=scoring)
    if args.release_transport_stop:
        if not args.resume or not args.live:parser.error('Transport continuation requires --resume --live')
        release_transport_stop(args.output_dir)
    if not args.live:print(json.dumps({'status':'ready','cases':12,'arms':list(ARMS),'max_calls':m['max_calls'],'max_completion_tokens':m['max_completion_tokens']}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI required; no substitution')
    history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    def primary(cap):return get_engine('gpt',model=PRIMARY['model'],creds=creds,history=history,max_tokens=cap,
        temperature=0,max_http_attempts=1,timeout=60)
    def sol(cap):return get_engine('gpt',model=SOL['model'],creds=creds,history=history,max_tokens=cap,
        temperature=None,reasoning_effort='medium',max_http_attempts=1,timeout=180)
    r=execute(args.output_dir,m,primary,sol)
    print(json.dumps({'status':r['status'],'error':r.get('error'),'output':str(args.output_dir)}))


if __name__=='__main__':main()
