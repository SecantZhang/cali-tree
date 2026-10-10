"""Three saved cases, identical Luna judging, Luna versus Sol 6.1 proposals."""
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
from critical.core.decision.calls import DurableCalls,CaseCalls,RoutedCalls,CallFailure,BudgetExhausted,ProviderStopped
from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.refinement import validate_refinement,EvidenceRefinementChecker
from critical.core.decision.robust.construction import TypedEvidenceCompiler
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.typed import create_typed_evidence_optimizer,nested_nodes
from critical.core.optimization.program.robust.metrics import RobustEvaluator,RobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import ROBUST_VERSION,validate_program_leaves
from run.calitree_robust_leaf_optimization import ROOT,code_hashes,status_for
from run.calitree_resume_typed_twelve import install_failure_replay

SOURCE=ROOT/'logs/exps/261008-typed-twelve-resumed-v2'
INDICES=(1,7,10)
ARMS=('luna-proposer','sol-proposer')
PRIMARY={'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none'}
SOL={'model':'gpt-6.1-sol','provider':'openai','temperature':None,'reasoning_effort':'medium'}


def preflight(output):
    parent=json.loads((SOURCE/'manifest.json').read_text());cases=[];hashes=code_hashes();groups=set()
    source_hashes={'manifest.json':sha256((SOURCE/'manifest.json').read_bytes()).hexdigest()}
    for index in INDICES:
        row=deepcopy(parent['cases'][index]);path=SOURCE/'prepared'/f'{index}.json'
        prepared=json.loads(path.read_text())
        if 'error' in prepared or 'seed' not in prepared:raise ValueError('Expected an executable saved seed')
        row['seed']=prepared['seed'];seed=restore_program(row['seed']);original=restore_program(row['original'])
        validate_refinement(seed,original)
        source_hashes[f'prepared/{index}.json']=sha256(path.read_bytes()).hexdigest()
        for key,path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest()!=row['image_hashes'][key]:raise ValueError('Changed image')
        with Image.open(row['evidence']['source_image']) as im:
            pixels=im.convert('RGB');group=sha256(str(pixels.size).encode()+pixels.tobytes()).hexdigest()
        if group!=row['group'] or group in groups:raise ValueError('Changed or duplicate source group')
        groups.add(group);cases.append(row)
    if Counter(c['target'] for c in cases)!={'yes':1,'no':1,'partial':1}:raise ValueError('Expected the frozen three-case subset')
    for folder,suffix in [('critical/lm_engine','*.py'),('critical/core/prompts/templates/typed_evidence_v1','*.txt'),
                          ('critical/core/prompts/templates/evidence_refinement_v1','*.txt'),
                          ('critical/core/prompts/templates/forced_decomposition_v1','*.txt')]:
        for path in (ROOT/folder).rglob(suffix):hashes[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
    for path in (Path(__file__),ROOT/'run/calitree_resume_typed_twelve.py'):
        hashes[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
    package=Path(importlib.util.find_spec('textgrad').origin).parent
    manifest={'version':'sol-proposer-comparison-v1','cases':cases,'arms':list(ARMS),
        'scope':'Three previously observed local fitting cases: jacket, paper/cup and frog. Only proposer model/configuration varies; no generalization claim.',
        'primary_identity':deepcopy(PRIMARY),'routes':{'sol-proposer':deepcopy(SOL)},'profile':'nested-required','random_seed':20261009,
        'policy':asdict(RobustPolicy()),'max_rounds':15,'proposals_per_round':2,'proposal_max_tokens':4096,
        'max_calls':900,'max_completion_tokens':1152000,'reserve_calls':240,'reserve_tokens':245760,
        'scope_limits':{'search':109,'final':40},'source_hashes':source_hashes,'source_directory':str(SOURCE),
        'code_hashes':hashes,'dependencies':{'textgrad':importlib.metadata.version('textgrad'),
        'hashes':{str(p.relative_to(package)):sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*.py'))}},
        'pricing_per_million_tokens':{'gpt-6-luna':{'input':.1,'output':.5},'gpt-6.1-sol':{'input':2,'output':10}},
        'pricing_source':'https://developers.openai.com/api/docs/models','pricing_date':'2026-10-08',
        'shared_seed_audits':3,'historical_feedback_or_observations_reused':False,'compiler_reused_saved_label_free_seeds':True}
    output=Path(output);path=output/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('Frozen settings/code/images changed')
    else:
        save_json(path,manifest)
        for rel in hashes:
            path=output/'source_snapshot'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/rel).read_bytes())
    return manifest


def write_report(output,result,manifest):
    lines=['# Luna versus Sol 6.1 proposal comparison','',manifest['scope'],'','Status: '+result['status'],'',
        'Both arms retain the forced-added-check policy, transaction format, Luna semantic audit, Luna feedback and Luna image judging. '
        'Sol uses medium reasoning without temperature; Luna uses temperature zero and reasoning none. '
        'Both proposal responses are capped at 4,096 completion tokens, including reasoning tokens.','',
        'Matches means reference-label agreement across five fresh executions. Resolved means a usable answer, including wrong answers. '
        'Confidence is self-report; robustness requires approved audit plus qualifying confirmation and final verification.','',
        '| Case | Proposer | Seed → selected matches / 5 | Selected resolved / 5 | Robustness result |',
        '|---|---|---:|---:|---|']
    for case in manifest['cases']:
        for arm in manifest['arms']:
            row=result['cases'].get(case['id'],{}).get(arm,{});final=row.get('final',{})
            a,b=final.get('seed',{}),final.get('selected',{})
            lines.append('| '+' | '.join([case['instruction'],arm,
                f"{round(a.get('agreement',0)*5)} → {round(b.get('agreement',0)*5)}" if b else 'pending',
                str(round(b.get('coverage',0)*5)) if b else 'pending',row.get('support_status',row.get('phase','pending'))])+' |')
    lines+=['','Usage: '+json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('attempted_slots','cases')}),
        'Returned models: '+json.dumps(result.get('returned_models',[])), 'Error: '+str(result.get('error','none')),
        '', 'No final outcome can reopen search. Failed slots are not retried; three consecutive transport errors stop the whole run.']
    (Path(output)/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output,manifest,engine_factory,proposer_factory):
    install_failure_replay();output=Path(output);policy=RobustPolicy(**manifest['policy'])
    calls=DurableCalls(output,engine_factory,identity=manifest['primary_identity'],
        routes={'sol-proposer':{'identity':manifest['routes']['sol-proposer'],'engine_factory':proposer_factory}},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    result={'status':'running','cases':{c['id']:{} for c in manifest['cases']}}
    bundle={'version':ROBUST_VERSION,'nodes':{},'programs':{}}
    def persist():
        result['budget']=deepcopy(calls.budget);save_json(output/'results.json',result)
        if bundle['nodes']:save_json(output/'leaves.json',validate_program_leaves(bundle))
        write_report(output,result,manifest)
    try:
        for i,raw in enumerate(manifest['cases']):
            case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
            original,seed=restore_program(raw['original']),restore_program(raw['seed'])
            checkpoint=CheckpointStore(output/'observations'/f'{i}.jsonl');path=output/'prepared'/f'{i}.json'
            if path.exists():prepared=json.loads(path.read_text())
            else:
                prepared={};compiler=TypedEvidenceCompiler(CaseCalls(calls,'prepare/'+case.id),original)
                try:prepared['seed_audit']=compiler.audit(seed,slot='shared_seed_audit')
                except (CallFailure,ValueError,TypeError,KeyError) as exc:prepared['error']=str(exc)
                save_json(path,prepared)
            order=manifest['arms'][i%2:]+manifest['arms'][:i%2]
            for arm in order:
                path=output/'frozen'/arm/f'{i}.json'
                if not path.exists():
                    if 'error' in prepared:save_json(path,prepared)
                    else:
                        scoped=CaseCalls(calls,arm+'/'+case.id)
                        optimizer=create_typed_evidence_optimizer(scoped,original,profile=manifest['profile'],checkpoint=checkpoint,
                            policy=policy,seed_audit=prepared['seed_audit'],random_seed=manifest['random_seed']+i,
                            max_rounds=manifest['max_rounds'],proposal_max_tokens=manifest['proposal_max_tokens'],
                            proposer_calls=RoutedCalls(scoped,'sol-proposer') if arm=='sol-proposer' else None)
                        local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                            optimizer_factory=lambda _:optimizer,seeds={case.id:seed})
                        save_json(path,local)
                result['cases'][case.id][arm]={'phase':'frozen'};persist()
                print(json.dumps({'phase':'frozen','case':i+1,'arm':arm,'calls':calls.budget['calls']}),flush=True)
        # All six selections are frozen before either arm receives a final draw.
        for i,raw in enumerate(manifest['cases']):
            case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group']);seed=restore_program(raw['seed'])
            for arm in manifest['arms']:
                local=json.loads((output/'frozen'/arm/f'{i}.json').read_text());row={'final':{}}
                result['cases'][case.id][arm]=row
                if 'error' in local:row.update(error=local['error'],support_status='unresolved');persist();continue
                validate_program_leaves(local);node=local['nodes']['leaf:'+case.id];saved=node['result']
                scoped=CaseCalls(calls,arm+'/'+case.id)
                evaluator=RobustEvaluator(RobustExecutor(EvidenceRefinementChecker(scoped),
                    checkpoint=CheckpointStore(output/'observations'/f'{i}.jsonl')),policy)
                for which in ('seed','selected'):
                    program=restore_program(saved[which]);validate_refinement(program,restore_program(raw['original']))
                    row['final'][which]=evaluator.evaluate(program,case,raw['target'],repeats=5,
                        namespace=f'final/{arm}/{which}',final=True);persist()
                selected=restore_program(saved['selected']);candidate=saved['candidates'].get(selected.ref,{})
                audit=candidate.get('audit',{});confirmation=candidate.get('confirmation',{})
                confirmed=bool(confirmation and policy.assess(confirmation,audit)['qualified'])
                status,assessment=status_for(row['final']['selected'],audit,policy)
                added=nested_nodes(selected,seed);stats=row['final']['selected']['nodes']
                structural=bool(added) and all(stats[n]['eligible']>=3 and stats[n]['queried']>=3 for n in added)
                if not confirmed:assessment['reasons'].append('confirmation_missing_or_unqualified')
                if not structural:assessment['reasons'].append('no_eligible_executed_nested_check')
                assessment['qualified']=assessment['qualified'] and confirmed and structural
                row.update(phase='final',acceptance=assessment,confirmed=confirmed,nested_checks=added,checks=len(selected.nodes),
                    search_status=saved['status'],stop_reason=saved['stop_reason'],
                    search_schedule=saved['lineage'][-1].get('search_schedule'),usage=deepcopy(calls.budget['cases'].get(arm+'/'+case.id,{})),
                    support_status='locally_robust' if assessment['qualified'] else 'structural_failure' if not structural else
                    'unconfirmed' if not confirmed else status)
                node.update(id='leaf:'+arm+'/'+case.id,support_status=row['support_status'],arm=arm,final_comparison=row['final'])
                bundle['nodes'][node['id']]=node;bundle['programs'].update(local['programs']);persist()
                print(json.dumps({'phase':'final','case':i+1,'arm':arm,'status':row['support_status'],'calls':calls.budget['calls']}),flush=True)
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,TypeError,KeyError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    result['returned_models']=sorted({j['response'].get('model','unavailable') for p in (output/'jobs').glob('*.json')
        if (j:=json.loads(p.read_text())).get('response')})
    persist();return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    modes=p.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.report:write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():p.error('Resume requires an existing frozen manifest')
    manifest=preflight(args.output_dir)
    if not args.live:print(json.dumps({'status':'ready','cases':3,'max_calls':900,'max_sol_proposal_calls':45}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI required; no substitution')
    history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    def primary(cap):return get_engine('gpt',model=PRIMARY['model'],creds=creds,history=history,
        max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60)
    def proposer(cap):return get_engine('gpt',model=SOL['model'],creds=creds,history=history,
        max_tokens=cap,temperature=None,reasoning_effort=SOL['reasoning_effort'],max_http_attempts=1,timeout=180)
    result=execute(args.output_dir,manifest,primary,proposer)
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))


if __name__=='__main__':main()
