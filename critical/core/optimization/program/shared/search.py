"""Bounded local repair search with durable routing and comparable confirmation evidence."""
from copy import deepcopy
from dataclasses import dataclass, asdict
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.optimization.program.base import LeafOptimizer
from critical.core.optimization.program.models import LeafResult

@dataclass(frozen=True)
class ProposerPolicy:
    mode: str = 'luna_only'
    stalled_rounds: int = 3

    def __post_init__(self):
        if self.mode not in ('luna_only','luna_then_sol') or self.stalled_rounds != 3:
            raise ValueError('V4 policy is Luna-only or permanent Sol escalation after three stalled rounds')

def select_confirmed(programs, confirmations, audits, seed_ref, policy, *, require_semantic_audit=True):
    """Only comparable five-draw evidence can replace a measured incumbent."""
    allowed=lambda ref:not require_semantic_audit or audits.get(ref,{}).get('accepted')
    baseline=confirmations.get(seed_ref) if allowed(seed_ref) else None
    pool=[]
    for ref,report in confirmations.items():
        if report['draws']!=policy.repeats or not allowed(ref):continue
        if baseline and (report['agreement']<baseline['agreement'] or report['coverage']<baseline['coverage']):continue
        if baseline is None and ref!=seed_ref and not policy.assess(report,audits[ref])['qualified']:continue
        pool.append(ref)
    qualifying=[r for r in pool if policy.assess(confirmations[r],audits[r])['qualified']]
    pool=qualifying or pool
    return min(pool,key=lambda r:(tuple(-v for v in policy.rank(confirmations[r])),r)) if pool else seed_ref

class LocalLeafOptimizer(LeafOptimizer):
    artifact_version=None
    mode='flat'

    def __init__(self,compiler,proposer,evaluator,gradient,diagnosis,*,proposer_policy=None,seed_audit=None,
                 max_rounds=15,progress=None,semantic_audit=True,apply_edit,
                 validate_program,export_artifact,screen_diagnostics=None,
                 confirm_seed_on_match=False):
        if type(max_rounds) is not int or not 1<=max_rounds<=15:raise ValueError('One to fifteen bounded repair rounds')
        self.compiler,self.proposer,self.evaluator,self.gradient,self.diagnosis=compiler,proposer,evaluator,gradient,diagnosis
        self.proposer_policy=proposer_policy or ProposerPolicy()
        self.seed_audit,self.max_rounds,self.progress=seed_audit,max_rounds,progress
        self.policy=evaluator.policy
        self.apply_edit,self.validate_program,self.export_artifact=apply_edit,validate_program,export_artifact
        self.screen_diagnostics,self.confirm_seed_on_match=screen_diagnostics,confirm_seed_on_match
        if type(semantic_audit) is not bool:raise ValueError('semantic_audit must be boolean')
        self.semantic_audit=semantic_audit
        if not semantic_audit:
            from .metrics import NoAuditRobustPolicy
            self.policy=NoAuditRobustPolicy(**asdict(self.policy))
            self.evaluator.policy=self.policy

    def optimize(self,case,reference_label,*,seed=None,budget=None):
        if reference_label not in ('yes','partial','no'):raise ValueError('Invalid reference label')
        if budget is not None and budget is not self.compiler.calls:raise ValueError('Budget must be the enforced durable case scope')
        result=LeafResult(case.id);programs={};screens={};confirmations={};audits={};events=[];diagnostics=[]
        stall=0;escalated=False;follow=None;followed=set();seed_ref=None;stop='round_limit';completed=0
        calls=self.compiler.calls

        def rank(ref):return self.policy.rank(screens[ref])
        def incumbent():return min(screens,key=lambda r:(tuple(-v for v in rank(r)),r)) if screens else seed_ref
        def screen(p,audit=None):
            ref=p.ref;programs[ref]=p;result.candidates[ref]=self.export_artifact(p)
            audit=(audit if audit is not None else self.compiler.audit(p,slot='audit/'+ref)) if self.semantic_audit else {
                'status':'disabled','performed':False,'reason':'Semantic auditing disabled by configuration'}
            audits[ref]=audit;result.candidates[ref]['audit']=audit
            if self.semantic_audit and not audit.get('accepted'):
                diagnostics.append({'program_ref':ref,'semantic_rejection':audit});return None
            report=self.evaluator.evaluate(p,case,reference_label,repeats=1,namespace='screen/'+ref)
            screens[ref]=report;result.candidates[ref]['screen']=report;return report
        def confirm(ref,namespace):
            report=self.evaluator.evaluate(programs[ref],case,reference_label,repeats=5,namespace=namespace)
            confirmations[ref]=report;result.candidates[ref]['confirmation']=report
            result.candidates[ref]['acceptance']=self.policy.assess(report,audits[ref])
        def success():return any(self.policy.assess(v,audits[r])['qualified'] for r,v in confirmations.items())
        def infra(report):return any(o.get('event') in ('transport_failure','invalid_response','interrupted_attempt')
            for t in (report or {}).get('raw_measurements',report or {}).get('traces',[]) for o in t['observations'])

        try:
            seed=seed or self.compiler.compile(case.instruction,self.compiler.original.rubric,slot='compile')
            self.validate_program(seed,self.compiler.original)
            if seed.instruction!=case.instruction:raise ValueError('Seed instruction mismatch')
            seed_ref=seed.ref;result.seed=result.selected=self.export_artifact(seed)
            screen(seed,self.seed_audit)
            if seed_ref in screens and (not self.confirm_seed_on_match or
                    screens[seed_ref]['agreement']==screens[seed_ref]['coverage']==1):
                confirm(seed_ref,'confirm/seed/'+seed_ref)
            for number in range(self.max_rounds):
                if success():stop='confirmation_qualified';break
                parent_ref=follow or incumbent();follow=None
                parent=programs[parent_ref]
                baseline=rank(incumbent()) if screens else None
                if self.proposer_policy.mode=='luna_then_sol' and stall>=3:escalated=True
                route='sol-proposer' if escalated else 'primary'
                namespace=f'round/{number}'
                event={'round':number,'parent':parent_ref,'stall_before':stall,'route':route,'slot':namespace+'/proposal',
                       'trigger':'three_completed_stalled_rounds' if escalated else 'luna_first',
                       'proposer_policy':asdict(self.proposer_policy)}
                path=calls.directory/'search_events'/digest(getattr(calls,'case_id',case.id))/f'{number}.json'
                if path.exists():
                    import json
                    if json.loads(path.read_text())!=event:raise ValueError('Changed saved escalation/parent decision on resume')
                else:save_json(path,event)
                events.append(event)
                new=[];failed=False
                try:
                    report=confirmations.get(parent_ref) or screens.get(parent_ref)
                    if report is None:
                        report=self.evaluator.evaluate(parent,case,reference_label,repeats=1,namespace='diagnostic/'+parent_ref)
                        result.candidates[parent_ref]['diagnostic']=report
                    discovery=self.diagnosis.discover(parent,case,report,slot=namespace+'/discovery')
                    failed=any(f.get('failure')=='CallFailure' for f in discovery['failures'])
                    try:gradients=self.gradient.feedback(parent,case,reference_label,report,slot=namespace+'/gradient')
                    except (CallFailure,ValueError,TypeError,KeyError) as exc:
                        gradients={};failed=True;diagnostics.append({'stage':'gradient','error':str(exc)})
                    event.update(gradients=gradients,visual_discovery=discovery,rejected_diagnostics=deepcopy(diagnostics))
                    feedback={'textual_gradients':gradients,'report':report,'visual_discovery':discovery,
                              'rejected_diagnostics':deepcopy(diagnostics)}
                    rows=self.proposer.propose(parent,case,reference_label,feedback,slot=namespace+'/proposal',route=route)
                    for index,tx in enumerate(rows):
                        item={'round':number,'parent':parent_ref,'index':index,'route':route,'transaction':tx}
                        result.lineage.append(item)
                        try:
                            applied=self.apply_edit(parent,tx);child=applied.program
                            item.update(program_ref=child.ref,construction=applied.details,structural_valid=True)
                            if child.ref in programs:
                                item['duplicate']=True;diagnostics.append({'duplicate':child.ref});continue
                            screen(child);item['audit']=audits[child.ref]
                            if child.ref in screens:
                                new.append(child.ref);failed=failed or infra(screens[child.ref])
                                if self.screen_diagnostics:
                                    diagnostic=self.screen_diagnostics(tx,screens[child.ref],reference_label)
                                    item['screen_diagnosis']=diagnostic;diagnostics.append({'program_ref':child.ref,**diagnostic})
                        except CallFailure as exc:
                            failed=True;item['error']=str(exc);diagnostics.append(deepcopy(item))
                        except (ValueError,KeyError,TypeError) as exc:
                            item['error']=str(exc);diagnostics.append(deepcopy(item))
                    eligible=[r for r in new if screens[r]['agreement']==1 and screens[r]['coverage']==1 and r not in confirmations]
                    if eligible:
                        chosen=min(eligible,key=lambda r:(tuple(-v for v in rank(r)),r))
                        confirm(chosen,f'confirm/round/{number}/{chosen}');failed=failed or infra(confirmations[chosen])
                    improved=bool(new and (baseline is None or max(rank(r) for r in new)>baseline))
                    if not failed:stall=0 if improved else stall+1;completed+=1
                    event.update(completed=not failed,improved=improved,stall_after=stall,new_candidates=new)
                    if new and not improved:
                        available=[r for r in new if r not in followed]
                        if available:
                            follow=min(available,key=lambda r:(tuple(-v for v in rank(r)),r));followed.add(follow)
                    if self.progress:self.progress(deepcopy(event))
                except CallFailure as exc:
                    event.update(completed=False,error=str(exc),stall_after=stall)
                    diagnostics.append({'stage':'proposal','error':str(exc)})
                    if self.progress:self.progress(deepcopy(event))
                except (ValueError,KeyError,TypeError) as exc:
                    # A completed but malformed proposer response is not visual evidence.
                    event.update(completed=False,error=str(exc),stall_after=stall)
                    diagnostics.append({'stage':'response_validation','error':str(exc)})
                    if self.progress:self.progress(deepcopy(event))
            if success():stop='confirmation_qualified'
        except BudgetExhausted as exc:stop='budget_exhausted: '+str(exc)
        except (CallFailure,ValueError,KeyError,TypeError) as exc:stop='unresolved: '+str(exc)
        if seed_ref:
            selected=select_confirmed(programs,confirmations,audits,seed_ref,self.policy,require_semantic_audit=self.semantic_audit)
            result.selected=self.export_artifact(programs[selected])
            result.status='confirmed_local' if selected in confirmations and self.policy.assess(confirmations[selected],audits[selected])['qualified'] else 'local_unverified'
        else:selected=None
        result.stop_reason=stop
        result.usage=deepcopy(calls.budget.get('cases',{}).get(getattr(calls,'case_id',case.id),{}))
        result.lineage.append({'events':events,'diagnostics':diagnostics,'seed_retained':seed_ref,'selection':selected,
            'policy':asdict(self.policy),'proposer_policy':asdict(self.proposer_policy),'escalated':escalated,
            'semantic_audit':'enabled' if self.semantic_audit else 'disabled',
            'search_schedule':{'rounds_started':len(events),'rounds_completed':completed,'max_rounds':self.max_rounds}})
        return result
