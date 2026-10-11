"""Canonical fulfillment pipeline: offline demo, preflight, live, resume and report."""
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
from critical.core.decision.calls import DurableCalls,CaseCalls,CallFailure,BudgetExhausted,ProviderStopped
from critical.core.decision.robust.models import restore_program as restore_original
from critical.core.decision.fulfillment import FulfillmentCompiler,FulfillmentChecker,FulfillmentExecutor,restore_program as restore_saved,export_program,variant as fulfillment_variant,validate
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.fulfillment import create_fulfillment_leaf_optimizer,FulfillmentEvaluator
from critical.core.optimization.program.shared.metrics import NoAuditRobustPolicy
from critical.core.optimization.program.shared.experiments import ROOT,code_hashes,status_for,bridge_reference,install_failure_replay
from critical.core.optimization.program.shared.reporting import write_report
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import FULFILLMENT_VERSION,validate_program_leaves
SOURCE=ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json'
ARMS=('binary','fulfillment')
PRIMARY={'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none'}

def preflight(output, *, scoring='fulfillment'):
    if scoring!='fulfillment':raise ValueError('Unknown scoring mode')
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
    package=Path(importlib.util.find_spec('textgrad').origin).parent
    manifest={'version': 'fulfillment-comparison-twelve-v7',
 'protocol': 'typed-fulfillment-v1',
 'arms': ['binary', 'fulfillment'],
 'scope': 'Twelve previously observed local fitting cases, four per class. Repeats are within-case '
          'measurements. No held-out generalization or atomic correctness claim.',
 'primary_identity': {'model': 'gpt-6-luna',
                      'provider': 'openai',
                      'temperature': 0,
                      'reasoning_effort': 'none'},
 'routes': {},
 'random_seed': 20261009,
 'policy': {'repeats': 5,
            'agreement': 1.0,
            'consistency': 0.8,
            'confidence': 0.8,
            'minimum_eligible': 3},
 'stall_threshold': 3,
 'max_rounds': 15,
 'proposals_per_round': 2,
 'max_calls': 3600,
 'max_completion_tokens': 4608000,
 'reserve_calls': 1008,
 'reserve_tokens': 1032192,
 'scope_limits': {'search': 107, 'final': 42},
 'shared_preparation_calls_per_case': 1,
 'max_sol_proposal_calls': 0,
 'checker_cap': 1024,
 'proposal_cap': 4096,
 'other_cap': 2048,
 'workers': 1,
 'max_checks': 4,
 'max_depth': 1,
 'arm_order': 'rotate by case index',
 'historical_observations_reused': False,
 'historical_feedback_reused': False,
 'scoring': 'fulfillment',
 'semantic_audit': False,
 'model_readout': False,
 'aggregation': 'protected-weighted-fulfillment-bounds-v1',
 'preferred_decisions': 2,
 'transport_recovery_per_report': 1,
 'confirm_seed_on_match': True,
 'metric': 'five_final_draws_all_match_reference',
 'raw_measurements_preserved': True,
 'thresholds': {'yes': 0.9, 'no': 0.1},
 'weight_policy': 'equal requirement budgets; equal seed facets; equal conserved splits; auxiliary '
                  'zero',
 'binary_rule': 'strict endpoint fulfillment score == 1; all/some/none; unknown unresolved',
 'observer_excludes': ['labels', 'feedback', 'weights', 'scoring_mode', 'thresholds'],
 'same_observation_counterfactual_readouts': True}
    manifest.update(cases=cases,code_hashes=hashes,source_manifest_hash=sha256(SOURCE.read_bytes()).hexdigest(),
        dependencies={'textgrad':importlib.metadata.version('textgrad'),'hashes':{str(p.relative_to(package)):sha256(p.read_bytes()).hexdigest() for p in package.rglob('*.py')}})
    path=Path(output)/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('Frozen settings, code, dependency or images changed')
    else:
        save_json(path,manifest)
        for rel in hashes:
            p=Path(output)/'source_snapshot'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    return manifest

def execute(output,manifest,primary_factory,sol_factory=None,*,progress=True):
    if manifest.get('scoring')!='fulfillment':raise ValueError('Use the legacy runner for historical scoring protocols')
    install_failure_replay();output=Path(output)
    policy=NoAuditRobustPolicy(**manifest['policy'])
    compiler_type,checker_type,executor_type=FulfillmentCompiler,FulfillmentChecker,FulfillmentExecutor
    calls=DurableCalls(output,primary_factory,identity=manifest['primary_identity'],
        routes={k:{'identity':v,'engine_factory':sol_factory} for k,v in manifest['routes'].items()},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    result={'status':'running','cases':{c['id']:{} for c in manifest['cases']}}
    bundle={'version':FULFILLMENT_VERSION,'nodes':{},'programs':{}}
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
            prepared['semantic_audit']={'status':'disabled','performed':False};save_json(prep,prepared)
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
                        options=dict(proposer_policy='luna_only',
                            sol_calls=None,
                            checkpoint=CheckpointStore(output/'observations'/arm/f'{i}.jsonl'),policy=policy,
                            max_rounds=manifest['max_rounds'],progress=on_round)
                        options['scoring_mode']=arm
                        opt=create_fulfillment_leaf_optimizer(scoped,original,**options)
                        seed=restore_saved(prepared['seed'])
                        seed=fulfillment_variant(seed,arm)
                        local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                            optimizer_factory=lambda _:opt,seeds={case.id:seed})
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
                evaluator=FulfillmentEvaluator(executor_type(checker_type(scoped),checkpoint=CheckpointStore(output/'observations'/arm/f'{i}.jsonl')),policy)
                for which in ('seed','selected'):
                    program=restore_saved(saved[which])
                    validate(program,restore_original(raw['original']))
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

def run_fulfillment_demo(output):
    """Measure actual red pixel coverage; no model or test-helper dependencies."""
    from fractions import Fraction
    from critical.core.decision.fulfillment import FulfillmentProgram,FulfillmentDecision,WeightRoot,template as grade_template
    from critical.core.optimization.program.robust.demo import example_program
    original=example_program();quote=original.requirements[0].source_phrase
    nodes=tuple(FulfillmentDecision(id=f'd{i}',requirement_id='r',question=f'Is the {part} half red?',
        criteria='Measure requested red coverage',binding=part,source_quote=quote,aspect=part,endpoint=f'The {part} half is red',
        necessity='Both halves are included in the requested whole square',zero_when='No red pixels',half_when='Half the pixels are red',
        full_when='All pixels are red',root_id=f'root.d{i}',weight_numerator=1,weight_denominator=2) for i,part in [(1,'upper'),(2,'lower')])
    p=FulfillmentProgram(original.instruction,original.rubric,original.requirements,original.outcomes,nodes,grade_template('check'),
        decomposition_reason='Observable spatial extents of the requested square',
        weight_roots=tuple(WeightRoot(n.root_id,'r',quote,n.endpoint,1,2) for n in nodes))
    output=Path(output);output.mkdir(parents=True,exist_ok=True);source=output/'source.png';Image.new('RGB',(20,20),'blue').save(source)
    class PixelChecker:
        identity={'checker':'offline-red-coverage'}
        def check(self,p,n,evidence,**kw):
            with Image.open(evidence['edited_image']) as im:
                pixels=im.convert('RGB').crop((0,0,20,10) if n.id=='d1' else (0,10,20,20)).getcolors(200)
                f=sum(count for count,(red,green,blue) in pixels if red>green and red>blue)/200
            return {'fulfillment_score':f,'binary_status':'pass' if f==1 else 'fail',
                'status':'pass' if f>=.9 else 'fail' if f<=.1 else 'partial','confidence':1,
                'evidence':'Requested red coverage counted directly from synthetic pixels','completion_tokens':0}
    rows={}
    for name,width in [('none',0),('half',10),('almost',19),('full',20)]:
        im=Image.new('RGB',(20,20),'blue')
        if width:im.paste('red',(0,0,width,20))
        path=output/(name+'.png');im.save(path)
        rows[name]=FulfillmentExecutor(PixelChecker()).execute(p,{'source_image':str(source),'edited_image':str(path)},repeat=name)
    save_json(output/'program.json',export_program(p));save_json(output/'fulfillment_demo.json',rows)
    return {'synthetic':True,'model_calls':0,'labels':{k:{'score':v['fulfillment']['score'],
        'binary':v['fulfillment']['binary_label'],'fulfillment':v['fulfillment']['fulfillment_label']} for k,v in rows.items()}}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    for mode in ('offline-demo','preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--scoring',choices=('fulfillment',),help='fulfillment compares binary versus weighted graded fulfillment using the same Luna observer; stored runs retain their mode')
    parser.add_argument('--release-transport-stop',action='store_true',help='Explicitly authorize one transport continuation; preserve all attempted slots and charges')
    args=parser.parse_args()
    if args.offline_demo:
        print(json.dumps(run_fulfillment_demo(args.output_dir)));return
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():parser.error('Resume needs a frozen manifest')
    saved_manifest=args.output_dir/'manifest.json'
    prior=json.loads(saved_manifest.read_text()) if saved_manifest.exists() else {}
    scoring=args.scoring or prior.get('scoring','fulfillment')
    m=preflight(args.output_dir,scoring=scoring)
    if args.release_transport_stop:
        if not args.resume or not args.live:parser.error('Transport continuation requires --resume --live')
        release_transport_stop(args.output_dir)
    if not args.live:print(json.dumps({'status':'ready','cases':12,'arms':m['arms'],'max_calls':m['max_calls'],'max_completion_tokens':m['max_completion_tokens']}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI required; no substitution')
    history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    def primary(cap):return get_engine('gpt',model=PRIMARY['model'],creds=creds,history=history,max_tokens=cap,
        temperature=0,max_http_attempts=1,timeout=60)
    r=execute(args.output_dir,m,primary)
    print(json.dumps({'status':r['status'],'error':r.get('error'),'output':str(args.output_dir)}))

if __name__=='__main__':main()
