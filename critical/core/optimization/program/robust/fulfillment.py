"""Same local optimizer, protected score roots and independent paired scoring arms."""
from copy import deepcopy
from statistics import mean

from critical.core.decision.compiler import media_inputs
from critical.core.decision.fulfillment import (FulfillmentCompiler,FulfillmentChecker,FulfillmentExecutor,
    PROPOSAL_SCHEMA,PROTOCOL,template,validate,export_program,apply_transaction)
from .adaptive import AdaptiveLeafOptimizer,ProposerPolicy
from .counting_v6 import EndpointEvaluator,EndpointTextGrad,EndpointDiagnosis
from .discovery import VisualReviewer
from .metrics import NoAuditRobustPolicy
from critical.core.optimization.program.base import EditProposer


def diagnosis(p,report,target):
    scores={n.id:[o.get('fulfillment_score') for t in report['traces'] for o in t['observations'] if o['check_id']==n.id] for n in p.nodes}
    return {'reference_label':target,'mode':p.scoring_mode,'aggregate_labels':report['label_distribution'],
        'fulfillment_bounds':[t['fulfillment'] for t in report['traces']], 'condition_scores':scores,
        'nonsemantic_failures':[{'check_id':o['check_id'],'event':o['event']} for t in report.get('raw_measurements',report)['traces']
            for o in t['observations'] if not o['valid']],
        'instruction':'Locate an omitted aspect, mistaken binding or score anchor; never alter mass or thresholds to match the label'}


def screen_diagnostics(tx,report,target):
    values={k:[o.get('fulfillment_score') for t in report['traces'] for o in t['observations'] if o['check_id']==k] for k in report['nodes']}
    return {'previous_candidate_outcomes':{'reference_label':target,'aggregate':report['label_distribution'],
        'agreement':report['agreement'],'coverage':report['coverage'],'actual_scores':values,'predicted_scores':tx['predicted_scores'],
        'bounds':[t['fulfillment'] for t in report['traces']]}}


class FulfillmentProposer(EditProposer):
    def __init__(self,calls):self.calls=calls
    def propose(self,p,case,target,feedback,*,slot,route='primary',limit=2):
        if route!='primary':raise ValueError('Paired fulfillment comparison uses Luna-only proposals')
        feedback={**feedback,'targeted_diagnosis':diagnosis(p,feedback['report'],target)}
        value,_=self.calls.call('propose_fulfillment',{'instruction':p.instruction,'rubric':p.rubric,'program':p.to_dict(),
            'reference_label':target,'feedback':feedback,'protocol':PROTOCOL,'limit':limit,'semantic_audit':'disabled'},
            PROPOSAL_SCHEMA,template=template('propose'),media=media_inputs(case.evidence),slot=slot,max_tokens=4096)
        rows=value.get('transactions')
        if not isinstance(rows,list) or len(rows)>limit:raise ValueError('Invalid proposal batch')
        return rows


class FulfillmentEvaluator(EndpointEvaluator):
    def evaluate(self,p,case,target,**kw):
        report=super().evaluate(p,case,target,**kw)
        for rep in (report,report['raw_measurements']):
            traces=rep['traces'];rep['fulfillment_bounds']=[t['fulfillment'] for t in traces]
            rep['scoring_mode']=p.scoring_mode
            rep['counterfactual_agreement']={mode:sum(t['fulfillment'][mode+'_label']==target for t in traces)/len(traces) for mode in ('binary','fulfillment')}
            known=[t['fulfillment']['score'] for t in traces if t['fulfillment']['score'] is not None]
            rep['mean_fulfillment']=mean(known) if known else None
        return report


class FulfillmentLeafOptimizer(AdaptiveLeafOptimizer):
    artifact_version='calitree-casewise-leaves-v7'
    mode='flat'


def create_fulfillment_leaf_optimizer(calls,original,*,scoring_mode='fulfillment',checkpoint=None,policy=None,
                                     max_rounds=15,progress=None,proposer_policy='luna_only',sol_calls=None):
    if proposer_policy!='luna_only' or sol_calls is not None:raise ValueError('The scoring comparison holds proposer family fixed')
    if scoring_mode not in ('binary','fulfillment'):raise ValueError('Unknown scoring mode')
    class ModeCompiler(FulfillmentCompiler):
        def compile(self,*args,**kwargs):
            from critical.core.decision.fulfillment import variant
            return variant(super().compile(*args,**kwargs),scoring_mode)
    def validate_mode(p,original=None):
        validate(p,original)
        if p.scoring_mode!=scoring_mode:raise ValueError('Seed scoring mode differs from optimizer configuration')
        return p
    return FulfillmentLeafOptimizer(ModeCompiler(calls,original),FulfillmentProposer(calls),
        FulfillmentEvaluator(FulfillmentExecutor(FulfillmentChecker(calls),checkpoint=checkpoint),policy or NoAuditRobustPolicy(agreement=1)),
        EndpointTextGrad(calls),EndpointDiagnosis((VisualReviewer('primary',calls.identity['model'],calls),),parent_roles=('decision','evidence')),
        proposer_policy=ProposerPolicy('luna_only'),max_rounds=max_rounds,progress=progress,semantic_audit=False,
        apply_edit=apply_transaction,validate_program=validate_mode,export_artifact=export_program,
        screen_diagnostics=screen_diagnostics,confirm_seed_on_match=True)
