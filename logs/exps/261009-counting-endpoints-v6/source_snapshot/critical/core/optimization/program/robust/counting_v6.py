"""Endpoint diagnostics, predicted edit impact and label-blind recovery selection."""
from copy import deepcopy

from critical.core.decision.compiler import media_inputs
from critical.core.decision.counting_v6 import (EndpointCompiler,EndpointChecker,EndpointExecutor,
    PROPOSAL_SCHEMA,PROTOCOL,template,validate,export_program,apply_transaction)
from .adaptive import AdaptiveLeafOptimizer,ProposerPolicy
from .counting import CountingProposer
from .discovery import VisualEvidenceDiagnosis,VisualReviewer
from .metrics import RobustEvaluator,NoAuditRobustPolicy,summarize
from .proposer import NodeTextGrad


def diagnose(program,report,target):
    labels=report['label_distribution'];rows=[o for t in report['traces'] for o in t['observations']]
    infra=[{'check_id':o['check_id'],'event':o['event']} for o in rows if o['event'] in ('transport_failure','invalid_response','interrupted_attempt')]
    variable=[k for k,v in report['nodes'].items() if v['consistency'] is not None and v['consistency']<.8]
    applicable=[n.id for n in program.nodes if report['nodes'][n.id]['eligible']]
    issues=[]
    if infra:issues.append('infrastructure_or_schema_failure_is_not_visual_evidence')
    if target=='partial' and len(applicable)==1:issues.append('partial_unrepresentable_with_one_binary_condition')
    if report['agreement']<1:
        if target=='partial' and labels.get('yes'):issues.append('all_pass_investigate_missing_required_aspect_or_permissive_criterion')
        elif target=='partial' and labels.get('no'):issues.append('all_fail_investigate_satisfied_aspect_or_overstrict_criterion')
        elif target=='yes':issues.append('investigate_failed_required_endpoints')
        elif target=='no':issues.append('investigate_passing_endpoints_and_source_relative_change')
    if variable:issues.append('inspect_unstable_conditions')
    implicated=[n.id for n in program.nodes if any(o['check_id']==n.id and o['valid'] and
        ((target=='yes' and o['status']=='fail') or (target=='no' and o['status']=='pass') or target=='partial') for o in rows)]
    return {'issues':issues,'implicated_checks':implicated,'variable_checks':variable,'nonsemantic_failures':infra,
            'aggregation':dict(labels),'partial_representable':len(applicable)>1,
            'reminder':'Reference disagreement is not permission to invent or delete a requirement'}


def screen_diagnostics(tx,report,target):
    states={k:dict(v['states']) for k,v in report['nodes'].items()}
    return {'previous_candidate_outcomes':{'reference_label':target,'aggregation':report['label_distribution'],
        'agreement':report['agreement'],'coverage':report['coverage'],'observed_states':states,
        'predicted_states':tx['predicted_states'],'predictions_matched':{
            e['decision_id']:states.get(e['decision_id'],{}).get(e['status'],0)==report['draws'] for e in tx['predicted_states']},
        'semantic_success':report['agreement']==report['coverage']==1}}


class EndpointProposer(CountingProposer):
    def propose(self,p,case,target,feedback,*,slot,limit=2,route='primary'):
        calls=self.sol_calls if route=='sol-proposer' else self.calls
        if calls is None:raise ValueError('Missing explicit proposer route')
        feedback={**feedback,'targeted_diagnosis':diagnose(p,feedback['report'],target)}
        value,_=calls.call('propose_counting',{'instruction':p.instruction,'rubric':p.rubric,'program':p.to_dict(),
            'reference_label':target,'feedback':feedback,'protocol':PROTOCOL,'limit':limit,'semantic_audit':'disabled'},
            PROPOSAL_SCHEMA,template=template('propose'),media=media_inputs(case.evidence),slot=slot,max_tokens=4096)
        rows=value.get('transactions')
        if not isinstance(rows,list) or len(rows)>limit:raise ValueError('Too many or malformed endpoint transactions')
        return rows


class EndpointEvaluator(RobustEvaluator):
    """One recovery check per report, selected without looking at the label or answers."""
    def evaluate(self,program,case,reference_label,*,repeats,namespace,final=False):
        raw=super().evaluate(program,case,reference_label,repeats=repeats,namespace=namespace,final=final)
        effective=deepcopy(raw['traces']);attempt=None
        # Choose the first transport failure in saved execution order, regardless of target.
        for draw,t in enumerate(raw['traces']):
            for index,o in enumerate(t['observations']):
                if o['event']=='transport_failure':
                    attempt={'draw':draw,'check_id':o['check_id'],'original_execution_ref':o['execution_ref'],
                        'slot':f'{namespace}/transport_recovery/{draw}', 'limit':1,'selection':'first_transport_failure_in_order'}
                    effective[draw]=self.executor.recover_transport(program,case.evidence,t,index,
                        repeat=attempt['slot'],final=final)
                    break
            if attempt:break
        report=summarize(program,effective,reference_label,self.policy)
        report.update(raw_measurements=raw,transport_recovery=attempt,
            mean_attempted_calls=(sum(len(o.get('attempts',[o])) for t in effective for o in t['observations'] if o['queried'])/repeats))
        return report


class EndpointTextGrad(NodeTextGrad):
    def feedback(self,program,case,target,report,*,slot):
        visual=deepcopy(report)
        for t in visual['traces']:
            t['observations']=[o for o in t['observations'] if o['valid'] and o['event'] not in ('transport_failure','invalid_response','interrupted_attempt')]
            for o in t['observations']:o.pop('attempts',None)
        return super().feedback(program,case,target,visual,slot=slot)


class EndpointDiagnosis(VisualEvidenceDiagnosis):
    def discover(self,program,case,report,*,slot):
        visual=deepcopy(report)
        for t in visual['traces']:
            t['observations']=[o for o in t['observations'] if o['valid'] and o['event'] not in ('transport_failure','invalid_response','interrupted_attempt')]
            for o in t['observations']:o.pop('attempts',None)
        return super().discover(program,case,visual,slot=slot)


class EndpointLeafOptimizer(AdaptiveLeafOptimizer):
    artifact_version='calitree-casewise-leaves-v6'
    mode='flat'


def create_endpoint_leaf_optimizer(calls,original,*,proposer_policy='luna_only',sol_calls=None,checkpoint=None,
                                   policy=None,max_rounds=15,progress=None):
    if proposer_policy=='luna_then_sol' and sol_calls is None:raise ValueError('Adaptive mode needs an explicit Sol route')
    if sol_calls is not None and (sol_calls.parent is not calls or sol_calls.budget is not calls.budget or sol_calls.case_id!=calls.case_id):
        raise ValueError('Proposer route must share case and ledger')
    return EndpointLeafOptimizer(EndpointCompiler(calls,original),EndpointProposer(calls,sol_calls),
        EndpointEvaluator(EndpointExecutor(EndpointChecker(calls),checkpoint=checkpoint),policy or NoAuditRobustPolicy(agreement=1.0)),
        EndpointTextGrad(calls),EndpointDiagnosis((VisualReviewer('primary',calls.identity['model'],calls),),parent_roles=('decision',)),
        proposer_policy=ProposerPolicy(proposer_policy),max_rounds=max_rounds,progress=progress,semantic_audit=False,
        apply_edit=apply_transaction,validate_program=validate,export_artifact=export_program,
        screen_diagnostics=screen_diagnostics,confirm_seed_on_match=True)
