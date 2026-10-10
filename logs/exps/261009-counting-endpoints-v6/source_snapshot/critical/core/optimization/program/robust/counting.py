"""No semantic auditor and no model readout; local optimization of flat conditions."""
from critical.core.decision.compiler import media_inputs
from critical.core.decision.counting import CountingCompiler, CountingChecker, CountingExecutor, PROPOSAL_SCHEMA, PROTOCOL, template, validate, export_program, apply_transaction
from critical.core.optimization.program.base import EditProposer
from .adaptive import AdaptiveLeafOptimizer, ProposerPolicy
from .discovery import VisualEvidenceDiagnosis, VisualReviewer
from .metrics import RobustEvaluator, NoAuditRobustPolicy
from .proposer import NodeTextGrad


class CountingProposer(EditProposer):
    def __init__(self,calls,sol_calls=None):self.calls,self.sol_calls=calls,sol_calls
    def propose(self,p,case,target,feedback,*,slot,limit=2,route='primary'):
        calls=self.sol_calls if route=='sol-proposer' else self.calls
        if calls is None:raise ValueError('Missing explicit proposer route')
        value,_=calls.call('propose_counting',{'instruction':p.instruction,'program':p.to_dict(),'reference_label':target,
            'feedback':feedback,'protocol':PROTOCOL,'limit':limit,'semantic_audit':'disabled'},PROPOSAL_SCHEMA,
            template=template('propose'),media=media_inputs(case.evidence),slot=slot,max_tokens=4096)
        rows=value.get('transactions')
        if not isinstance(rows,list) or len(rows)>limit:raise ValueError('Too many or malformed transactions')
        return rows


class CountingLeafOptimizer(AdaptiveLeafOptimizer):
    artifact_version='calitree-casewise-leaves-v5'
    mode='flat'


def create_counting_leaf_optimizer(calls,original,*,proposer_policy='luna_only',sol_calls=None,checkpoint=None,
                                   policy=None,max_rounds=15,progress=None):
    if proposer_policy=='luna_then_sol' and sol_calls is None:raise ValueError('Adaptive mode needs an explicit Sol route')
    if sol_calls is not None and (sol_calls.parent is not calls or sol_calls.budget is not calls.budget or sol_calls.case_id!=calls.case_id):
        raise ValueError('Proposer route must share the case scope and ledger')
    return CountingLeafOptimizer(CountingCompiler(calls,original),CountingProposer(calls,sol_calls),
        RobustEvaluator(CountingExecutor(CountingChecker(calls),checkpoint=checkpoint),policy or NoAuditRobustPolicy()),
        NodeTextGrad(calls),VisualEvidenceDiagnosis((VisualReviewer('primary',calls.identity['model'],calls),),parent_roles=('decision',)),
        proposer_policy=ProposerPolicy(proposer_policy),max_rounds=max_rounds,progress=progress,semantic_audit=False,
        apply_edit=apply_transaction,validate_program=validate,export_artifact=export_program)
