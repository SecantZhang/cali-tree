"""Bound inference features and conditional routing for semantic facet regions."""
from copy import deepcopy
import math

from . import visual_semantic_policy_v69 as visual
from . import rubric_evidence_v73 as old_evidence
from . import local_warranted_rubric_v97 as local
from .facet_selector_v162 import FACETS, allowed, project, execute
from .semantic_residual_runtime_v104 import f32
from ..decision import outcome_policy_v160 as outcome
from ..decision import local_rubric_evidence_v94 as old_facts
from ..decision import facet_observation_v165 as facet_facts
from ..decision.artifacts import digest


def original_support(route):
    """Follow earlier expert decisions to their original numerical teacher."""
    for _ in range(12):
        if 'class_support' in route:
            support = route['class_support']
            if (not isinstance(support, list) or len(support) != 3 or
                any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in support) or
                not math.isclose(sum(support), 1., abs_tol=1e-6)):
                raise ValueError('Normalized original teacher support required')
            return support
        route = route.get('base_route', route.get('teacher_route'))
        if not isinstance(route, dict):
            break
    raise ValueError('Original teacher route unavailable')


def legacy_values(parent, inputs, prior_route, local_record=None):
    """Match the pre-existing fold feature projection, including its old mask.

    The local-Qwen fields are zero outside the ORIGINAL v112 review region,
    even if a cached record happens to exist for that input. New Sol routing
    does not turn old unmeasured fields into negative physical evidence.
    """
    if not prior_route['covered']:
        return None
    program, observation, pair_ref, interpretation, judgment, vision_record = inputs
    support = original_support(prior_route)
    regular = visual.regular_label(judgment)
    bound = visual.shared.evidence.project(program, observation, pair_ref, interpretation)
    previous = old_evidence.project(program, observation, pair_ref, interpretation)
    if previous is None:
        raise ValueError('Existing semantic evidence unavailable')
    values = {**visual.evidence.feature_values(program, bound), **visual.language.project(program, judgment),
              **previous, **old_evidence.views(previous, support, regular)}
    local_flags = dict.fromkeys(local.SPECS, False)
    if parent.review_route(prior_route) and local_record is not None:
        try:
            flags = local.project(program, pair_ref, digest(parent.artifact['observer_profile']),
                digest(old_facts.prompt(program, parent.artifact['observer_template'])), local_record)
            teacher = max(range(3), key=lambda c: (support[c], -c))
            local_flags.update(flags); local_flags.update(local.view_flags(flags, teacher, regular))
        except (ValueError, KeyError, TypeError):
            pass
    values.update(local_flags)
    return {name: bool(f32(value) > f32(.5)) for name, value in values.items() if allowed(name)}


def prior_locked(prior_route, final_route):
    return (not final_route['covered'] or prior_route.get('rubric_rule') is not None or
            prior_route.get('expert_rule') is not None or final_route.get('reason') == 'semantic_residual_override')


class FacetRegionPolicy:
    """Opt-in overlay; loading the policy makes no observation or API call."""
    VERSION = 'bound-facet-semantic-overlay-v166'

    def __init__(self, parent, artifact):
        if (artifact.get('version') != self.VERSION or
            artifact.get('artifact_ref') != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) or
            artifact.get('parent_ref') != parent.artifact['artifact_ref'] or
            artifact.get('priority') not in ('retain_prior_priority', 'learned_semantic_precedence')):
            raise ValueError('Changed semantic facet overlay or parent')
        facet_facts.validate_profile(artifact['observer_profile'])
        binding = artifact.get('training_binding')
        if (not isinstance(binding, dict) or binding.get('fold') != 5 or
            binding.get('deployment_parent_artifact_ref') != parent.artifact['artifact_ref'] or
            binding.get('selector_artifact_ref') != artifact['selector'].get('artifact_ref') or
            binding.get('priority') != artifact['priority'] or binding.get('legacy_float32_border') != .5):
            raise ValueError('Only the matching full-fit selector may be deployed on this parent')
        selector = artifact['selector']
        if (selector.get('artifact_ref') != digest({k: v for k, v in selector.items() if k != 'artifact_ref'}) or
            selector.get('version') != 'source-bound-semantic-facet-selector-v162' or
            selector.get('outcome_contract_ref') != outcome.CONTRACT_REF or len(selector.get('rules', [])) > 4):
            raise ValueError('Changed compact selector')
        used = {t['feature'] for r in selector['rules'] for t in r['conditions']}
        if selector['feature_names'] != sorted(used) or any(not allowed(n) for n in used):
            raise ValueError('Closed named semantic evidence required')
        for rule in selector['rules']:
            target = rule['grade']; source = rule['from_grade']
            if type(target) is not int or type(source) is not int or target not in range(3) or source not in range(3) or target == source:
                raise ValueError('Concrete changed grade required')
            terms = rule['conditions']
            if (len(terms) > 3 or len({t['feature'] for t in terms}) != len(terms) or
                any(type(t['value']) is not bool for t in terms) or
                ('facet_'+('no', 'partial', 'yes')[target]+'_outcome_ready', True) not in {(t['feature'], t['value']) for t in terms}):
                raise ValueError('Positive outcome witness and bounded semantic guards required')
        self.parent, self.artifact = parent, deepcopy(artifact)

    @classmethod
    def export(cls, parent, selector, priority, *, training_binding):
        artifact = {'version': cls.VERSION, 'parent_ref': parent.artifact['artifact_ref'],
            'selector': deepcopy(selector), 'priority': priority, 'observer_profile': facet_facts.make_profile(),
            'training_binding': deepcopy(training_binding)}
        artifact['artifact_ref'] = digest(artifact)
        cls(parent, artifact)
        return artifact

    def eligible_from_legacy(self, parent_route, prior_route, values):
        if not parent_route['covered'] or values is None:
            return False
        if self.artifact['priority'] == 'retain_prior_priority' and prior_locked(prior_route, parent_route):
            return False
        current = parent_route['prediction']
        for rule in self.artifact['selector']['rules']:
            if rule['from_grade'] != current:
                continue
            if all(t['feature'] in FACETS or values[t['feature']] == t['value'] for t in rule['conditions']):
                return True
        return False

    def resolve_after_parent(self, parent_route, inputs, prior_route, *, local_record=None, facet_record=None):
        """Invalid/missing/irrelevant new evidence retains the parent decision."""
        if not parent_route['covered'] or facet_record is None:
            return parent_route
        try:
            values = legacy_values(self.parent, inputs, prior_route, local_record)
            if not self.eligible_from_legacy(parent_route, prior_route, values):
                return parent_route
            value = facet_facts.validate_record(inputs[0], inputs[2], self.artifact['observer_profile'], facet_record)
            values.update(project(value))
            selected = execute(self.artifact['selector'], values, int(parent_route['prediction']), True)
            if selected == parent_route['prediction']:
                return parent_route
            for index, rule in enumerate(self.artifact['selector']['rules']):
                if parent_route['prediction'] == rule['from_grade'] and all(values[t['feature']] == t['value'] for t in rule['conditions']):
                    return {'covered': True, 'prediction': selected, 'reason': 'semantic_facet_override',
                        'facet_rule_index': index, 'facet_conditions': deepcopy(rule['conditions']),
                        'facet_observation_ref': facet_record['record_ref'], 'facet_evidence': value['evidence'],
                        'parent_route': parent_route}
            raise ValueError('Selected facet rule unavailable')
        except (ValueError, KeyError, TypeError, IndexError, OverflowError):
            return {**parent_route, 'facet_review_error': 'invalid_or_unbound_facet_evidence'}
