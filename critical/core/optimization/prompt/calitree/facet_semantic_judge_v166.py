"""Opt-in facet experts around the existing v112 judge and fallback path."""
from ....calibration.facet_runtime_v166 import legacy_values
from ....calibration.facet_selector_v162 import DESCRIPTIONS
from ....decision import facet_observation_v165 as facts
from .semantic_residual_judge_v104 import SemanticResidualJudge
from .visual_semantic_judge_v69 import VisualSemanticJudge

_UNSET = object()


class FacetSemanticJudge(VisualSemanticJudge):
    """A new observation is requested only if a semantic region can still match.

    Caller-supplied observers/call ledgers retain control of live authorization
    and budgets. Construction and explicit retained-None records make no calls.
    The selected public CaliTreeJudge remains v112 until an evaluated promotion.
    """
    def __init__(self, policy, calls=None, encoder=None, *, observer=None, facet_observer=None, extractor=None):
        super().__init__(calls, policy, encoder, extractor=extractor)
        self.observer, self.facet_observer = observer, facet_observer
        if facet_observer is not None:
            facts.validate_profile(facet_observer.profile)
            if facet_observer.profile != policy.artifact['observer_profile']:
                raise ValueError('Facet observer differs from the fitted policy')

    def _legacy_values(self, parent, inputs, prior, local):
        return legacy_values(parent, inputs, prior, local)

    def judge(self, instruction, evidence, *, case_id=None, local_record=_UNSET,
              expert_record=None, facet_record=_UNSET, **kwargs):
        parent = self.policy.parent; captured = {'local_record': None}
        class CaptureBase:
            def resolve_bound(self, *inputs, expert_record=None):
                prior = parent.base.resolve_bound(*inputs, expert_record=expert_record)
                captured.update(inputs=inputs, prior=prior)
                return prior
        class CaptureParent:
            artifact = parent.artifact
            base = CaptureBase()
            def review_route(self, route):
                return parent.review_route(route)
            def _resolve_from_base(self, prior, inputs, record):
                captured['local_record'] = record
                return parent._resolve_from_base(prior, inputs, record)
        delegate = SemanticResidualJudge(self.calls, CaptureParent(), self.encoder,
            observer=self.observer, extractor=self.extractor)
        if local_record is not _UNSET:
            kwargs['local_record'] = local_record
        result = delegate.judge(instruction, evidence, case_id=case_id, expert_record=expert_record, **kwargs)
        result.update(pipeline_version='v166', policy_ref=self.policy.artifact['artifact_ref'],
                      parent_policy_ref=parent.artifact['artifact_ref'])
        if not result['route']['covered'] or 'inputs' not in captured:
            return {**result, 'facet_observation_status': 'parent_fallback'}
        if facet_record is None or (facet_record is _UNSET and self.facet_observer is None):
            return {**result, 'facet_observation_status': 'retained_or_unavailable'}
        inputs, prior, local = captured['inputs'], captured['prior'], captured['local_record']
        try:
            known = self._legacy_values(parent, inputs, prior, local)
            if not self.policy.eligible_from_legacy(result['route'], prior, known):
                return {**result, 'facet_observation_status': 'outside_semantic_region'}
            if facet_record is _UNSET:
                facet_record = self.facet_observer.observe(inputs[0], evidence, inputs[2], case_id=case_id)
            route = self.policy.resolve_after_parent(result['route'], inputs, prior,
                local_record=local, facet_record=facet_record)
        except (ValueError, RuntimeError, KeyError, TypeError, IndexError, OverflowError) as exc:
            return {**result, 'facet_observation_status': 'unavailable_or_invalid', 'facet_error': type(exc).__name__}
        if route.get('reason') != 'semantic_facet_override':
            return {**result, 'route': route, 'facet_observation_status': 'deferred_or_agreed'}
        terms = [DESCRIPTIONS[t['feature']] if t['value'] else 'Not established: '+DESCRIPTIONS[t['feature']]
                 for t in route['facet_conditions']]
        return {**result, 'route': route, 'source': 'semantic_facet_rule', 'facet_observation_status': 'selected',
            'facet_observation_ref': route['facet_observation_ref'],
            'judgment': {'label': ('no', 'partial', 'yes')[route['prediction']],
                'rationale': 'The learned outcome region selects this grade from bound model observations. '+
                    route['facet_evidence']+' Conditions: '+' AND '.join(terms)}}
