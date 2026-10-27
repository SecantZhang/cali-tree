"""Opt-in independent-judge routing; the extra judge is supplied, never called."""
from .visual_semantic_judge_v69 import VisualSemanticJudge
from .semantic_rubric_judge_v70 import SemanticRubricJudge
from ....calibration.seeded_rubric_v73 import DESCRIPTIONS


class IndependentSemanticJudge(VisualSemanticJudge):
    def judge(self,*args,expert_record=None,**kwargs):
        policy=self.policy
        class BoundRequestPolicy:
            def resolve_bound(self,*inputs):return policy.resolve_bound(*inputs,expert_record=expert_record)
        delegate=SemanticRubricJudge(self.calls,BoundRequestPolicy(),self.encoder,extractor=self.extractor)
        result=delegate.judge(*args,**kwargs)
        if result['route'].get('reason')=='independent_expert_override':
            rule=result['route']['expert_rule']
            clauses=[DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: '+DESCRIPTIONS[t['feature']] for t in rule['conditions']]
            result['judgment']['rationale']=('The semantic review gate selects the independent Sol judgment. '+expert_record['judgment']['rationale']+' Review conditions: '+' AND '.join(clauses))
            result['source']='independent_semantic_expert'
            result['independent_execution_ref']=result['route']['expert_execution_ref']
        return result
