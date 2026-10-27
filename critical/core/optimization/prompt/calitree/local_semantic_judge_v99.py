"""Execute optional local review after the existing semantic/expert policy."""
from .visual_semantic_judge_v69 import VisualSemanticJudge
from .independent_semantic_judge_v87 import IndependentSemanticJudge
from ....calibration.local_warranted_rubric_v97 import DESCRIPTIONS
from ....decision.artifacts import digest

_UNSET = object()


class LocalSemanticJudge(VisualSemanticJudge):
    def __init__(self, *args, observer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if observer is not None and (observer.identity_ref != digest(self.policy.artifact['observer_profile']) or
                                     observer.template_ref != self.policy.artifact['observer_template_ref']):
            raise ValueError('Observer does not match the compiled local policy')
        self.observer = observer

    def judge(self, instruction, evidence, *, local_record=_UNSET, expert_record=None, **kwargs):
        policy, observer = self.policy, self.observer
        context = {}
        class BoundRequestPolicy:
            def resolve_bound(self, *inputs, expert_record=None):
                base = policy.base.resolve_bound(*inputs, expert_record=expert_record)
                if not policy.review_route(base):
                    return base
                record = None if local_record is _UNSET else local_record
                if local_record is _UNSET and observer is not None:
                    try:
                        record = observer.observe(inputs[0], evidence, inputs[2])
                    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                        return {**base, 'local_observation_error': type(exc).__name__}
                context.update(record=record, judgment=inputs[4])
                return policy._resolve_from_base(base, inputs, record)
        delegate = IndependentSemanticJudge(self.calls, BoundRequestPolicy(), self.encoder, extractor=self.extractor)
        result = delegate.judge(instruction, evidence, expert_record=expert_record, **kwargs)
        if result['route'].get('reason') == 'local_semantic_review_override':
            selected = result['route']['local_rule']; record = context['record']
            terms = [DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: '+DESCRIPTIONS[t['feature']] for t in selected['conditions']]
            if selected['action'] == 'regular':
                rationale = 'The learned local review region selects the independent regular visual judgment. '+context['judgment']['rationale']
                result['source'] = 'local_review_regular_judge'
            else:
                rationale = 'The learned task/preservation rule predicts this grade from bound local-model claims. Local comparison: '+record['observation']['evidence']
                result['source'] = 'local_semantic_rule'
            result['judgment']['rationale'] = rationale+' Rule conditions: '+' AND '.join(terms)
            result['local_observation_ref'] = record['record_ref']
        return result
