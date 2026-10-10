"""One saved chalk case: criterion-only versus required typed nested insertion."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess

from PIL import Image
from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, CallFailure, BudgetExhausted, ProviderStopped
from critical.core.decision.robust.models import restore_program, export_program
from critical.core.decision.robust.refinement import validate_refinement, EvidenceRefinementChecker
from critical.core.decision.robust.construction import TypedEvidenceCompiler, PROTOCOL
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.typed import create_typed_evidence_optimizer, nested_nodes
from critical.core.optimization.program.robust.metrics import RobustEvaluator, RobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves, ROBUST_VERSION
from run.calitree_robust_leaf_optimization import ROOT, code_hashes, status_for

SOURCE=ROOT/'logs/exps/261008-nested-evidence-small-seeded-v1/manifest.json'
ARMS=('criterion-only','nested-required')


def preflight(output):
    source=json.loads(SOURCE.read_text());raw=deepcopy(source['cases'][0])
    seed=restore_program(source['decomposition_seed']);original=restore_program(raw['broad_seed'])
    validate_refinement(seed,original)
    if len(seed.nodes)!=3 or raw['target']!='partial' or 'chalk' not in raw['instruction']:
        raise ValueError('Expected the original three-check chalk seed')
    for key,path in raw['evidence'].items():
        if sha256(Path(path).read_bytes()).hexdigest()!=raw['image_hashes'][key]:raise ValueError('Image hash changed')
    with Image.open(raw['evidence']['source_image']) as image:
        pixels=image.convert('RGB');group=sha256(str(pixels.size).encode()+pixels.tobytes()).hexdigest()
    if group!=raw['group']:raise ValueError('Source pixels changed')
    if importlib.metadata.version('textgrad')!='0.1.8':raise ValueError('Expected TextGrad 0.1.8')
    package=Path(importlib.util.find_spec('textgrad').origin).parent
    hashes=code_hashes();hashes[str(Path(__file__).relative_to(ROOT))]=sha256(Path(__file__).read_bytes()).hexdigest()
    for folder in ('typed_evidence_v1','evidence_refinement_v1','forced_decomposition_v1'):
        for p in (ROOT/'critical/core/prompts/templates'/folder).glob('*.txt'):
            hashes[str(p.relative_to(ROOT))]=sha256(p.read_bytes()).hexdigest()
    manifest={'version':'typed-evidence-chalk-pilot-v1','protocol':PROTOCOL,'checkpoint_commit':subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_manifest_sha256':sha256(SOURCE.read_bytes()).hexdigest(),
        'scope':'One previously observed chalk case fitted locally. Repeats are within-case measurements. No atomic correctness or generalization claim.',
        'case':raw,'seed':export_program(seed),'arms':list(ARMS),'model':'gpt-6-luna','provider':'openai',
        'temperature':0,'reasoning_effort':'none','random_seed':20261008,'policy':asdict(RobustPolicy()),
        'round_batches':[1]*15,'max_rounds':15,'stop_on_confirmation':True,'repair_failed_candidate':True,
        'proposals_per_batch':2,'max_calls':300,'max_completion_tokens':384000,
        'reserve_calls':80,'reserve_tokens':81920,'scope_limits':{'search':109,'final':40},
        'shared_calls':2,'final_repeats':5,'max_checks':4,'max_depth':4,'code_hashes':hashes,
        'dependencies':{'textgrad':'0.1.8','hashes':{str(p.relative_to(package)):sha256(p.read_bytes()).hexdigest()
                                                  for p in sorted(package.rglob('*.py'))}}}
    manifest['version']='typed-evidence-chalk-pilot-v2'
    manifest['budget_may_limit_search']=True
    output=Path(output);path=output/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('Frozen configuration/source changed; use frozen runtime to resume')
    else:
        save_json(path,manifest)
        for rel in hashes:
            p=output/'source_snapshot'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    return manifest


def write_report(output,result,manifest):
    lines=['# Typed evidence: criterion-only versus nested-required','',manifest['scope'],'',
        'Status: '+result['status'],'','| Method | Seed → selected matches / 5 | Selected usable / 5 | Repair rounds completed | Checks | Inserted nested checks | Robust? |',
        '|---|---:|---:|---:|---:|---|---|']
    for arm in manifest['arms']:
        row=result['arms'].get(arm,{});a,b=(row.get('final',{}).get(k,{}) for k in ('seed','selected'))
        lines.append('| '+' | '.join([arm,f"{round(a.get('agreement',0)*5)} → {round(b.get('agreement',0)*5)}",
            str(round(b.get('coverage',0)*5)),str((row.get('search_schedule') or {}).get('rounds_completed','unavailable')),
            str(row.get('checks','unavailable')),', '.join(row.get('nested_checks',[])) or 'none',
            row.get('support_status','unattempted')])+' |')
    lines+=['','Matches = saved partial-reference agreement; usable = resolved labels, including wrong answers. '
        'Confidence is self-report. Both arms require complete qualifying confirmation and fresh final verification; nested-required also needs an inserted evidence-context check.','']
    for arm,row in result['arms'].items():
        lines += ['## '+arm,'',json.dumps(row,indent=2)]
    lines += ['','## Preparation','',json.dumps(result.get('preparation',{}),indent=2),
        '','Returned model identities: '+json.dumps(result.get('returned_models',[])),
        'Usage: '+json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('cases','attempted_slots')}),
        '','Final outcomes never trigger further optimization. Missing evidence and failure slots remain in denominators.']
    (Path(output)/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output,manifest,engine_factory):
    output=Path(output);raw=manifest['case'];case=Case(raw['id'],raw['instruction'],raw['evidence'],raw['group'])
    seed=restore_program(manifest['seed']);original=restore_program(raw['broad_seed']);policy=RobustPolicy(**manifest['policy'])
    calls=DurableCalls(output,engine_factory,identity={k:manifest[k] for k in ('model','provider','temperature','reasoning_effort')},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    checkpoint=CheckpointStore(output/'observations.jsonl');result={'status':'running','arms':{}}
    bundle={'version':ROBUST_VERSION,'nodes':{},'programs':{}}

    def persist():
        result['budget']=deepcopy(calls.budget)
        result['returned_models']=sorted({j.get('response',{}).get('model','unavailable') for p in (output/'jobs').glob('*.json')
            if (j:=json.loads(p.read_text())).get('response')})
        save_json(output/'results.json',result)
        if bundle['nodes']:save_json(output/'leaves.json',validate_program_leaves(bundle))
        write_report(output,result,manifest)

    try:
        prepared_path=output/'prepared.json'
        if prepared_path.exists():prepared=json.loads(prepared_path.read_text())
        else:
            prepared={};compiler=TypedEvidenceCompiler(CaseCalls(calls,'prepare/'+case.id),original)
            try:prepared['compilation_probe']=export_program(compiler.compile(case.instruction,raw['rubric'],slot='ordered_probe'))
            except (CallFailure,ValueError,TypeError,KeyError) as exc:
                prepared['probe_error']={'error':str(exc),'failure':type(exc).__name__}
                if hasattr(exc,'to_dict'):prepared['probe_error']['validation']=exc.to_dict()
            try:prepared['seed_audit']=compiler.audit(seed,slot='seed_audit')
            except (CallFailure,ValueError,TypeError,KeyError) as exc:
                prepared['audit_error']={'error':str(exc),'failure':type(exc).__name__}
            save_json(prepared_path,prepared)
        result['preparation']=prepared
        for arm in manifest['arms']:
            path=output/'frozen'/f'{arm}.json'
            if not path.exists():
                if 'seed_audit' not in prepared:save_json(path,{'error':prepared.get('audit_error','Missing shared audit')})
                else:
                    scoped=CaseCalls(calls,arm+'/'+case.id)
                    optimizer=create_typed_evidence_optimizer(scoped,original,profile=arm,checkpoint=checkpoint,
                        policy=policy,random_seed=manifest['random_seed'],seed_audit=prepared['seed_audit'],
                        max_rounds=manifest.get('max_rounds',len(manifest.get('round_batches',[1,2]))),
                        round_batches=manifest.get('round_batches',[1,2]),
                        stop_on_confirmation=manifest.get('stop_on_confirmation',False),
                        repair_failed_candidate=manifest.get('repair_failed_candidate',False))
                    local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                        optimizer_factory=lambda _:optimizer,seeds={case.id:seed})
                    save_json(path,local)
            print(json.dumps({'phase':'frozen','arm':arm,'calls':calls.budget['calls']}),flush=True);persist()
        # Both selections are immutable before any final query.
        for arm in manifest['arms']:
            local=json.loads((output/'frozen'/f'{arm}.json').read_text())
            row={'support_status':'unresolved','final':{}};result['arms'][arm]=row
            if 'error' in local:row['error']=local['error'];persist();continue
            validate_program_leaves(local);node=local['nodes']['leaf:'+case.id];saved=node['result']
            scoped=CaseCalls(calls,arm+'/'+case.id)
            evaluator=RobustEvaluator(RobustExecutor(EvidenceRefinementChecker(scoped),checkpoint=checkpoint),policy)
            for which in ('seed','selected'):
                program=restore_program(saved[which]);validate_refinement(program,original)
                row['final'][which]=evaluator.evaluate(program,case,raw['target'],repeats=5,
                    namespace=f'final/{arm}/{which}',final=True);persist()
            selected=restore_program(saved['selected']);candidate=saved['candidates'].get(selected.ref,{})
            audit=candidate.get('audit',{});confirmation=candidate.get('confirmation',{})
            confirmed=bool(confirmation and policy.assess(confirmation,audit)['qualified'])
            final_status,acceptance=status_for(row['final']['selected'],audit,policy)
            added=nested_nodes(selected,seed);structural_ok=arm!='nested-required' or bool(added)
            node_stats=row['final']['selected']['nodes']
            if arm=='nested-required':
                structural_ok=structural_ok and all(node_stats[n]['eligible']>=policy.minimum_eligible and
                    node_stats[n]['queried']>=policy.minimum_eligible for n in added)
            if not confirmed:acceptance['reasons'].append('confirmation_missing_or_unqualified')
            if not structural_ok:acceptance['reasons'].append('no_eligible_executed_nested_check')
            acceptance['qualified']=acceptance['qualified'] and confirmed and structural_ok
            row.update(acceptance=acceptance,checks=len(selected.nodes),nested_checks=added,confirmed=confirmed,
                search_status=saved['status'],stop_reason=saved['stop_reason'],
                search_schedule=deepcopy(saved['lineage'][-1].get('search_schedule')),
                support_status='locally_robust' if acceptance['qualified'] else 'structural_failure' if not structural_ok else
                    'unconfirmed' if not confirmed else final_status,
                usage=deepcopy(calls.budget.get('cases',{}).get(arm+'/'+case.id,{})))
            node.update(id='leaf:'+arm+'/'+case.id,support_status=row['support_status'],final_comparison=row['final'],arm=arm)
            bundle['nodes'][node['id']]=node;bundle['programs'].update(local['programs']);persist()
            print(json.dumps({'phase':'final','arm':arm,'status':row['support_status'],'calls':calls.budget['calls']}),flush=True)
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,KeyError,TypeError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    persist();return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    modes=p.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.report:
        write_report(args.output_dir,json.loads((args.output_dir/'results.json').read_text()),json.loads((args.output_dir/'manifest.json').read_text()));return
    if args.resume and not (args.output_dir/'manifest.json').exists():p.error('Resume requires frozen manifest')
    manifest=preflight(args.output_dir)
    if not args.live:print(json.dumps({'status':'ready','arms':manifest['arms'],'max_calls':300}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI required; no substitution')
    history=LLMHistoryWriter(args.output_dir/'llm-histories.log')
    result=execute(args.output_dir,manifest,lambda cap:get_engine('gpt',model=manifest['model'],creds=creds,
        history=history,max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':result['status'],'error':result.get('error'),'output':str(args.output_dir)}))


if __name__=='__main__':main()
