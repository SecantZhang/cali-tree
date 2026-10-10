"""Frozen twelve-case typed optimizer comparison; --live alone contacts OpenAI."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess
from threading import Lock

from PIL import Image
from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import restore_program as restore_legacy,save_json
from critical.core.decision.concurrent_calls import ConcurrentDurableCalls
from critical.core.decision.calls import CaseCalls,CallFailure,BudgetExhausted,ProviderStopped
from critical.core.decision.robust.models import RobustProgram,Node,GATES,restore_program,export_program
from critical.core.decision.robust.compiler import template as runtime_template
from critical.core.decision.robust.construction import TypedEvidenceCompiler,PROTOCOL
from critical.core.decision.robust.refinement import validate_refinement,EvidenceRefinementChecker
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.typed import create_typed_evidence_optimizer,nested_nodes
from critical.core.optimization.program.robust.metrics import RobustEvaluator,RobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves,ROBUST_VERSION
from run.calitree_robust_leaf_optimization import ROOT,code_hashes,status_for

SOURCE=ROOT/'logs/exps/261006-optimizer-comparison-v1/manifest.json'
ARMS=('criterion-only','nested-required')


def bridge_reference(artifact):
    """Explicit v2 -> v3 compilation reference; never reinterpret saved inference."""
    p=restore_legacy(artifact)
    if len(p.outcomes)!=1:raise ValueError('Twelve-case study needs one original requested outcome')
    supports=[c for c in p.checks if c.role=='support'];requested=[c for c in p.checks if c.role=='requested']
    if len(requested)!=1:raise ValueError('Need exactly one original fulfillment check')
    nodes=[]
    for c in (*supports,*requested):
        criteria=(f'pass: {c.complete_when}; fail: {c.absent_when}; unknown: {c.unknown_when}; '
                  f'incomplete evidence: {c.partial_when}' if c.role=='support' else
                  f'complete: {c.complete_when}; partial: {c.partial_when}; absent: {c.absent_when}; unknown: {c.unknown_when}')
        outcome=p.outcomes[0]
        nodes.append(Node(c.id,c.role,c.outcome_id if c.role=='requested' else '',nodes[-1].id if nodes else '',
            GATES if nodes else (),c.dependencies,c.question,criteria,
            f'Target: {outcome.target}. Reference: {outcome.reference}.'))
    result=RobustProgram(p.instruction,p.rubric,p.requirements,p.outcomes,tuple(nodes),runtime_template('check'))
    result.ref  # validate identity, ancestor references and frozen coverage
    return result


def preflight(output):
    source=json.loads(SOURCE.read_text());rows=[];groups=set()
    if len(source['cases'])!=12 or Counter(r['target'] for r in source['cases'])!={'yes':4,'partial':4,'no':4}:
        raise ValueError('Expected the exact balanced twelve-case collection')
    for raw in source['cases']:
        row={k:deepcopy(raw[k]) for k in ('id','instruction','target','evidence','image_hashes','group')}
        original=bridge_reference(raw['seed']);row['legacy_seed']=raw['seed'];row['original']=export_program(original);row['rubric']=original.rubric
        if original.instruction!=row['instruction']:raise ValueError('Instruction identity differs')
        for key,path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest()!=row['image_hashes'][key]:raise ValueError('Frozen image changed')
        with Image.open(row['evidence']['source_image']) as image:
            im=image.convert('RGB');group=sha256(str(im.size).encode()+im.tobytes()).hexdigest()
        if group!=row['group'] or group in groups:raise ValueError('Changed/repeated source group')
        groups.add(group);rows.append(row)
    if importlib.metadata.version('textgrad')!='0.1.8':raise ValueError('Expected TextGrad 0.1.8')
    package=Path(importlib.util.find_spec('textgrad').origin).parent
    hashes=code_hashes()
    for path in [Path(__file__),ROOT/'critical/core/decision/concurrent_calls.py']:
        hashes[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
    for folder in ('typed_evidence_v1','evidence_refinement_v1','forced_decomposition_v1'):
        for path in (ROOT/'critical/core/prompts/templates'/folder).glob('*.txt'):
            hashes[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
    manifest={'version':'typed-evidence-twelve-v1','protocol':PROTOCOL,'cases':rows,'arms':list(ARMS),
        'scope':'Twelve previously observed local fitting cases. Four per reference class. No cross-case feedback, atomic correctness or held-out generalization claim.',
        'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none','random_seed':20261008,
        'max_rounds':15,'round_batches':[1]*15,'stop_on_confirmation':True,'repair_failed_candidate':True,
        'proposals_per_batch':2,'policy':asdict(RobustPolicy()),'max_checks':4,'max_depth':4,'initial_supports':2,
        'max_calls':3600,'max_completion_tokens':4608000,'reserve_calls':960,'reserve_tokens':983040,
        'scope_limits':{'search':109,'final':40},'shared_calls_per_case':2,'workers':2,'budget_may_limit_search':True,
        'arm_order':'rotate by case index','source_manifest_sha256':sha256(SOURCE.read_bytes()).hexdigest(),
        'checkpoint_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'code_hashes':hashes,'dependencies':{'textgrad':'0.1.8','hashes':{str(p.relative_to(package)):sha256(p.read_bytes()).hexdigest()
                                          for p in sorted(package.rglob('*.py'))}}}
    output=Path(output);path=output/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('Frozen protocol/code/images changed; use saved runtime')
    else:
        save_json(path,manifest)
        for rel in hashes:
            p=output/'source_snapshot'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    return manifest


def write_report(output,result,manifest):
    summaries={};count=len(manifest['cases']);lines=['# Twelve-case typed evidence optimizer comparison','',manifest['scope'],'',
        'Status: '+result['status'],'','| Method | Mean seed → selected matches / 5 | Selected usable / 5 | Locally robust cases |',
        '|---|---:|---:|---:|']
    for arm in manifest['arms']:
        rows=[result['cases'].get(c['id'],{}).get(arm,{}) for c in manifest['cases']]
        summ={'cases':count,'robust_cases':sum(r.get('support_status')=='locally_robust' for r in rows)}
        for which in ('seed','selected'):
            summ[which]={k:sum(r.get('final',{}).get(which,{}).get(k,0) for r in rows)/count
                         for k in ('agreement','coverage','requirement_consistency','mean_checks','mean_completion_tokens')}
        summaries[arm]=summ
        lines.append(f"| {arm} | {summ['seed']['agreement']*5:.2f} → {summ['selected']['agreement']*5:.2f} | {summ['selected']['coverage']*5:.2f} | {summ['robust_cases']}/{count} |")
    lines+=['','Missing/unattempted/invalid draws are nonmatches in the full twelve-case denominator. Usable means resolved, including wrong labels. Repeats are within cases, not independent cases.','',
        '| Case / reference | Method | Seed → selected matches / 5 | Usable / 5 | Rounds completed | Nested checks | Status / reasons |',
        '|---|---|---:|---:|---:|---|---|']
    for c in manifest['cases']:
        for arm in manifest['arms']:
            r=result['cases'].get(c['id'],{}).get(arm,{});a,b=(r.get('final',{}).get(k,{}) for k in ('seed','selected'))
            lines.append('| '+' | '.join([c['instruction']+' / '+c['target'],arm,
                f"{round(a.get('agreement',0)*5)} → {round(b.get('agreement',0)*5)}",str(round(b.get('coverage',0)*5)),
                str((r.get('search_schedule') or {}).get('rounds_completed','unavailable')),', '.join(r.get('nested_checks',[])) or 'none',
                r.get('support_status','unattempted')+'; '+(', '.join(r.get('acceptance',{}).get('reasons',[])) or str(r.get('error','none')))])+' |')
    lines+=['','Confirmation success is provisional; final verification remains frozen and independent. Negative support is usable evidence. Confidence is self-report; consistency is not atomic correctness.',
        '','Returned models: '+json.dumps(result.get('returned_models',[])),'Usage: '+json.dumps({k:v for k,v in result.get('budget',{}).items() if k not in ('cases','attempted_slots')}),
        'Error: '+str(result.get('error','none'))]
    save_json(Path(output)/'summary.json',summaries);(Path(output)/'report.md').write_text('\n'.join(lines)+'\n')


def execute(output,manifest,engine_factory):
    output=Path(output);policy=RobustPolicy(**manifest['policy'])
    calls=ConcurrentDurableCalls(output,engine_factory,identity={k:manifest[k] for k in ('model','provider','temperature','reasoning_effort')},
        **{k:manifest[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')})
    result={'status':'running','scope':manifest['scope'],'cases':{c['id']:{} for c in manifest['cases']}}
    bundle={'version':ROBUST_VERSION,'nodes':{},'programs':{}};results_lock=Lock();gradient_lock=Lock()

    def persist():
        with calls.lock:
            result['budget']=deepcopy(calls.budget)
            # The requested identity is in the manifest; actual identities are read
            # once at completion to avoid scanning all jobs after every draw.
            save_json(output/'results.json',result)
        if bundle['nodes']:save_json(output/'leaves.json',validate_program_leaves(bundle))
        write_report(output,result,manifest)

    def case_objects(index,raw):
        return Case(raw['id'],raw['instruction'],raw['evidence'],raw['group']),restore_program(raw['original']),CheckpointStore(output/'observations'/f'{index}.jsonl')

    def fit_case(index,raw):
        case,original,checkpoint=case_objects(index,raw);path=output/'prepared'/f'{index}.json'
        if path.exists():prepared=json.loads(path.read_text())
        else:
            compiler=TypedEvidenceCompiler(CaseCalls(calls,'prepare/'+case.id),original,support_count=2);prepared={}
            try:
                seed=compiler.compile(case.instruction,raw['rubric'],slot='compile_common_seed')
                prepared['seed']=export_program(seed);prepared['audit']=compiler.audit(seed,slot='audit_common_seed')
            except (CallFailure,ValueError,TypeError,KeyError,BudgetExhausted) as exc:
                prepared['error']=f'{type(exc).__name__}: {exc}'
                if hasattr(exc,'to_dict'):prepared['validation']=exc.to_dict()
            save_json(path,prepared)
        order=manifest['arms'][index%2:]+manifest['arms'][:index%2]
        for arm in order:
            frozen=output/'frozen'/arm/f'{index}.json'
            if not frozen.exists():
                if 'error' in prepared:save_json(frozen,{'error':prepared['error']})
                else:
                    optimizer=create_typed_evidence_optimizer(CaseCalls(calls,arm+'/'+case.id),original,profile=arm,
                        checkpoint=checkpoint,policy=policy,random_seed=manifest['random_seed']+index,seed_audit=prepared['audit'],max_rounds=15)
                    native=optimizer.gradient
                    class Gradient:
                        def feedback(self,*args,**kw):
                            # TextGrad's global backward singleton is not reentrant.
                            with gradient_lock:return native.feedback(*args,**kw)
                    optimizer.gradient=Gradient()
                    local=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:raw['target']},
                        optimizer_factory=lambda _:optimizer,seeds={case.id:restore_program(prepared['seed'])})
                    save_json(frozen,local)
            with results_lock:
                result['cases'][case.id].setdefault(arm,{})['phase']='frozen'
                persist()
            print(json.dumps({'phase':'frozen','case':index+1,'arm':arm,'calls':calls.budget['calls']}),flush=True)

    def final_case(index,raw):
        case,original,checkpoint=case_objects(index,raw)
        for arm in manifest['arms']:
            local=json.loads((output/'frozen'/arm/f'{index}.json').read_text());row={'support_status':'unresolved','final':{}}
            with results_lock:result['cases'][case.id][arm]=row
            if 'error' in local:
                row['error']=local['error']
                with results_lock:persist()
                continue
            validate_program_leaves(local);node=local['nodes']['leaf:'+case.id];saved=node['result'];seed=restore_program(saved['seed'])
            scoped=CaseCalls(calls,arm+'/'+case.id);evaluator=RobustEvaluator(RobustExecutor(EvidenceRefinementChecker(scoped),checkpoint=checkpoint),policy)
            for which in ('seed','selected'):
                program=restore_program(saved[which]);validate_refinement(program,original)
                report=evaluator.evaluate(program,case,raw['target'],repeats=5,namespace=f'final/{arm}/{which}',final=True)
                with results_lock:row['final'][which]=report;persist()
            selected=restore_program(saved['selected']);candidate=saved['candidates'].get(selected.ref,{})
            audit=candidate.get('audit',{});confirm=candidate.get('confirmation',{})
            confirmed=bool(confirm and policy.assess(confirm,audit)['qualified']);added=nested_nodes(selected,seed)
            status,assessment=status_for(row['final']['selected'],audit,policy)
            structural=arm!='nested-required' or bool(added)
            if arm=='nested-required':
                stats=row['final']['selected']['nodes']
                structural=structural and all(stats[n]['eligible']>=3 and stats[n]['queried']>=3 for n in added)
            if not confirmed:assessment['reasons'].append('confirmation_missing_or_unqualified')
            if not structural:assessment['reasons'].append('no_eligible_executed_nested_check')
            assessment['qualified']=assessment['qualified'] and confirmed and structural
            with results_lock:
                with calls.lock:usage=deepcopy(calls.budget['cases'].get(arm+'/'+case.id,{}))
                row.update(phase='final',acceptance=assessment,confirmed=confirmed,nested_checks=added,checks=len(selected.nodes),
                    search_status=saved['status'],stop_reason=saved['stop_reason'],search_schedule=saved['lineage'][-1].get('search_schedule'),
                    usage=usage,support_status='locally_robust' if assessment['qualified'] else 'structural_failure' if not structural else
                    'unconfirmed' if not confirmed else status)
                node.update(id='leaf:'+arm+'/'+case.id,arm=arm,support_status=row['support_status'],final_comparison=row['final'])
                bundle['nodes'][node['id']]=node;bundle['programs'].update(local['programs']);persist()
            print(json.dumps({'phase':'final','case':index+1,'arm':arm,'status':row['support_status'],'calls':calls.budget['calls']}),flush=True)

    def phase(fn):
        first_error=None
        with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
            futures=[pool.submit(fn,i,raw) for i,raw in enumerate(manifest['cases'])]
            for f in as_completed(futures):
                try:f.result()
                except Exception as exc:
                    if first_error is None:first_error=exc
                    for pending in futures:pending.cancel()
        if first_error:raise first_error

    try:
        phase(fit_case)  # no final calls until every case/arm is frozen
        phase(final_case)
        result['status']='completed'
    except (ProviderStopped,BudgetExhausted,CallFailure,ValueError,KeyError,TypeError,RuntimeError) as exc:
        result.update(status='stopped',error=f'{type(exc).__name__}: {exc}')
    with results_lock:
        result['returned_models']=sorted({j['response'].get('model','unavailable') for p in (output/'jobs').glob('*.json')
            if (j:=json.loads(p.read_text())).get('response')})
        persist()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    modes=p.add_mutually_exclusive_group()
    for mode in ('preflight','live','report'):modes.add_argument('--'+mode,action='store_true')
    p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.report:write_report(a.output_dir,json.loads((a.output_dir/'results.json').read_text()),json.loads((a.output_dir/'manifest.json').read_text()));return
    if a.resume and not (a.output_dir/'manifest.json').exists():p.error('Resume requires existing frozen manifest')
    m=preflight(a.output_dir)
    if not a.live:print(json.dumps({'status':'ready','cases':12,'arms':ARMS,'max_calls':3600}));return
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True);creds=load_creds(engine='gpt',provider='openai')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI required; no substitution')
    history=LLMHistoryWriter(a.output_dir/'llm-histories.log')
    r=execute(a.output_dir,m,lambda cap:get_engine('gpt',model=m['model'],creds=creds,history=history,
        max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
    print(json.dumps({'status':r['status'],'error':r.get('error'),'output':str(a.output_dir)}))


if __name__=='__main__':main()
