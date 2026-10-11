"""V4 local search: conservative selection and durable Luna-to-Sol escalation."""
from copy import deepcopy
from dataclasses import asdict, dataclass

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.decision.compiler import media_inputs
from critical.core.decision.robust.v4_models import export_program, validate
from critical.core.decision.robust.v4_construction import EvidenceCompiler, PROPOSAL_SCHEMA, apply_transaction, template
from critical.core.decision.robust.v4_runtime import EvidenceChecker, EvidenceExecutor
from critical.core.optimization.program.base import LeafOptimizer, EditProposer
from critical.core.optimization.program.models import LeafResult
from critical.core.optimization.program.shared.search import LocalLeafOptimizer, ProposerPolicy, select_confirmed
from critical.core.optimization.program.robust.discovery import VisualEvidenceDiagnosis, VisualReviewer
from critical.core.optimization.program.robust.metrics import RobustEvaluator
from critical.core.optimization.program.robust.proposer import NodeTextGrad




class AdaptiveProposer(EditProposer):
    def __init__(self,calls,sol_calls=None):
        self.calls,self.sol_calls = calls,sol_calls

    def propose(self,program,case,target,feedback,*,slot,route='primary',limit=2):
        if limit!=2:raise ValueError('V4 fixes the proposal allowance at two transactions per round')
        calls=self.sol_calls if route=='sol-proposer' else self.calls
        if calls is None:raise ValueError('Missing approved Sol route')
        value,_=calls.call('propose_v4',{'instruction':program.instruction,'rubric':program.rubric,
            'program':program.to_dict(),'reference_label':target,'feedback':feedback,'protocol':'typed-evidence-v2','limit':2},
            PROPOSAL_SCHEMA,template=template('propose'),media=media_inputs(case.evidence),slot=slot,max_tokens=4096)
        rows=value.get('transactions')
        if not isinstance(rows,list) or len(rows)>2:raise ValueError('At most two transactions per round')
        return rows




class AdaptiveLeafOptimizer(LocalLeafOptimizer):
    artifact_version='calitree-casewise-leaves-v4'
    mode='tree'
    def __init__(self,*args,apply_edit=apply_transaction,validate_program=validate,export_artifact=export_program,**kw):
        super().__init__(*args,apply_edit=apply_edit,validate_program=validate_program,export_artifact=export_artifact,**kw)


def create_adaptive_evidence_optimizer(calls,original,*,proposer_policy='luna_only',sol_calls=None,
                                      checkpoint=None,policy=None,seed_audit=None,max_rounds=15,progress=None,semantic_audit=True):
    pp=ProposerPolicy(proposer_policy)
    if pp.mode=='luna_then_sol' and sol_calls is None:raise ValueError('Adaptive mode requires an explicit Sol route')
    if sol_calls is not None:
        routed=sol_calls.parent
        if routed is not calls or sol_calls.budget is not calls.budget or sol_calls.case_id!=calls.case_id:
            raise ValueError('Sol proposer must share primary ledger and case scope')
    compiler=EvidenceCompiler(calls,original)
    return AdaptiveLeafOptimizer(compiler,AdaptiveProposer(calls,sol_calls),
        RobustEvaluator(EvidenceExecutor(EvidenceChecker(calls),checkpoint=checkpoint),policy),NodeTextGrad(calls),
        VisualEvidenceDiagnosis((VisualReviewer('primary',calls.identity['model'],calls),)),
        proposer_policy=pp,seed_audit=seed_audit,max_rounds=max_rounds,progress=progress,semantic_audit=semantic_audit)
