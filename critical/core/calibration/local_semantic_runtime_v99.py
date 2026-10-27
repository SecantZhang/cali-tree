"""Bound local semantic grading/review layered after the verified v87 policy."""
from copy import deepcopy
import math

from . import visual_semantic_policy_v69 as visual
from . import rubric_evidence_v73 as old_evidence
from . import local_warranted_rubric_v97 as local
from .seeded_rubric_v73 import Search
from ..decision import local_rubric_evidence_v94 as facts
from ..decision.artifacts import digest

VERSION = 'bound-local-semantic-review-v99'


def content_ref(value):
    return digest({k: v for k, v in value.items() if k != 'artifact_ref'})


def checkpoint_compute_ref(identity):
    """The same model files can live at another path without changing inference."""
    return digest({k: identity[k] for k in ('model', 'revision', 'weight_bytes', 'weights', 'file_sha256')})


class LocalRuleExecutor:
    def __init__(self, artifact):
        if (artifact.get('version') != local.LocalWarrantedRubric.version or artifact.get('artifact_ref') != content_ref(artifact) or
                artifact.get('evidence_contract_ref') != local.CONTRACT_REF or artifact.get('local_fact_contract_ref') != local.CONTRACT_REF):
            raise ValueError('Changed or incompatible local rubric')
        config = Search(**artifact['config']); names = artifact['feature_names']
        if config.max_rules > 8 or config.max_guards > 2 or len(artifact['rules']) > config.max_rules:
            raise ValueError('Local rubric exceeds its compact bounds')
        model = local.LocalWarrantedRubric(names or ['local_no_ready'], config)
        if any(not model.accepts_feature(n) for n in names):
            raise ValueError('Undeclared local rubric vocabulary')
        used = set()
        for rule in artifact['rules']:
            if set(rule) != {'teacher_grade', 'action', 'conditions', 'warrant', 'support'}:
                raise ValueError('Invalid local rule fields')
            context, action = rule['teacher_grade'], rule['action']
            if type(context) is not int or context not in (0, 1, 2):
                raise ValueError('Valid teacher context required')
            if (action == 'regular' and config.mode == 'grades') or (type(action) is int and (action not in (0, 1, 2) or action == context or config.mode == 'routes')):
                raise ValueError('Rule action differs from its grading/review mode')
            if action != 'regular' and type(action) is not int:
                raise ValueError('Concrete grade or independent judge action required')
            conditions = rule['conditions']
            if any(set(t) != {'feature', 'value'} or t['feature'] not in names or type(t['value']) is not bool for t in conditions):
                raise ValueError('Named Boolean conditions required')
            terms = {(t['feature'], t['value']) for t in conditions}
            seed = tuple((t['feature'], t['value']) for t in rule['warrant'])
            if (len(terms) != len(conditions) or len({t['feature'] for t in conditions}) != len(conditions) or
                    seed not in model.rule_seeds(action) or not set(seed) <= terms or len(conditions) > len(seed)+config.max_guards):
                raise ValueError('Affirmative grading or review seed required')
            support = rule['support']
            if (set(support) != {'gain_sources', 'gains', 'losses'} or any(type(v) is not int or v < 0 for v in support.values()) or
                    support['gain_sources'] < config.min_sources or support['gains'] < support['gain_sources'] or
                    support['gains']-config.loss_cost*support['losses'] <= 0):
                raise ValueError('Invalid source support for local rule')
            used.update(t['feature'] for t in conditions)
        model.rules = deepcopy(artifact['rules'])
        if names != sorted(used) or model.render() != artifact['rubric']:
            raise ValueError('Rendered local policy differs from executable clauses')
        if artifact.get('review_threshold') != .8 or artifact.get('prior_rules_keep_original_context') is not True:
            raise ValueError('Changed review region or prior-rule priority')
        self.artifact, self.model = deepcopy(artifact), model

    def select(self, values, teacher, regular):
        if type(teacher) is not int or teacher not in (0, 1, 2) or type(regular) is not int or regular not in (-1, 0, 1, 2):
            raise ValueError('Current teacher and optional regular grade required')
        if any(type(values.get(n)) is not bool for n in self.artifact['feature_names']):
            raise ValueError('Required local predicates unavailable')
        for i, rule in enumerate(self.artifact['rules']):
            if teacher == rule['teacher_grade'] and all(values[t['feature']] == t['value'] for t in rule['conditions']):
                prediction = regular if rule['action'] == 'regular' else rule['action']
                if prediction >= 0:
                    return {'prediction': prediction, 'action': rule['action'], 'rule_index': i, 'conditions': deepcopy(rule['conditions'])}
        return None


def export_policy(base, rubric, profile, template, checkpoint):
    """Caller must first prove native/full teacher equivalence in its audit."""
    if digest(checkpoint) != profile['checkpoint_ref']:
        raise ValueError('Training checkpoint identity differs')
    compiled = {k: deepcopy(v) for k, v in rubric.items() if k not in ('artifact_ref', 'fit_cases')}
    compiled['native_teacher_ref'] = compiled['teacher_ref']; compiled['teacher_ref'] = base.artifact['base_teacher_ref']
    compiled['artifact_ref'] = content_ref(compiled)
    artifact = {'version': VERSION, 'base_ref': base.artifact['artifact_ref'], 'base_teacher_ref': base.artifact['base_teacher_ref'],
                'rubric': compiled, 'observer_profile': deepcopy(profile), 'observer_template': template, 'observer_template_ref': digest(template),
                'observer_checkpoint_compute_ref': checkpoint_compute_ref(checkpoint), 'local_contract_ref': local.CONTRACT_REF,
                'encoder_spec': deepcopy(base.artifact['encoder_spec'])}
    artifact['artifact_ref'] = content_ref(artifact)
    LocalSemanticPolicy(base, artifact)
    return artifact


class LocalSemanticPolicy:
    def __init__(self, base, artifact):
        if (artifact.get('version') != VERSION or artifact.get('artifact_ref') != content_ref(artifact) or
                artifact.get('base_ref') != base.artifact['artifact_ref'] or artifact.get('base_teacher_ref') != base.artifact['base_teacher_ref'] or
                artifact.get('local_contract_ref') != local.CONTRACT_REF):
            raise ValueError('Local policy belongs to a different base or contract')
        profile, rubric = artifact['observer_profile'], artifact['rubric']
        if (rubric['teacher_ref'] != artifact['base_teacher_ref'] or rubric['observer_identity_ref'] != digest(profile) or
                rubric['observer_template_ref'] != artifact['observer_template_ref'] or digest(artifact['observer_template']) != artifact['observer_template_ref'] or
                profile['contract_ref'] != facts.CONTRACT_REF or profile['schema_ref'] != digest(facts.schema()) or
                profile['engine'] != 'local_qwen_grammar_v95' or artifact['encoder_spec'] != base.artifact['encoder_spec']):
            raise ValueError('Changed observer, template or teacher binding')
        self.base, self.artifact, self.rubric = base, deepcopy(artifact), LocalRuleExecutor(rubric)

    def review_route(self, base):
        if not base['covered'] or base.get('rubric_rule') is not None or base.get('expert_rule') is not None:
            return False
        support = base.get('class_support')
        if (not isinstance(support, list) or len(support) != 3 or
                any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in support) or
                not math.isclose(sum(support), 1., abs_tol=1e-6)):
            return False
        return max(support) < self.rubric.artifact['review_threshold']

    def review_bound(self, *inputs, expert_record=None):
        base = self.base.resolve_bound(*inputs, expert_record=expert_record)
        return {'review_needed': self.review_route(base), 'base_route': base}

    def _values(self, program, observation, pair_ref, interpretation, judgment, vision_record, base, record):
        prompt_ref = digest(facts.prompt(program, self.artifact['observer_template']))
        flags = local.project(program, pair_ref, digest(self.artifact['observer_profile']), prompt_ref, record)
        regular = visual.regular_label(judgment)
        bound = visual.shared.evidence.project(program, observation, pair_ref, interpretation)
        previous = old_evidence.project(program, observation, pair_ref, interpretation)
        if previous is None:
            raise ValueError('Missing existing semantic evidence')
        return {**visual.evidence.feature_values(program, bound), **visual.language.project(program, judgment),
                **visual.vision.predicates(vision_record['measurements']), 'evidence_missing': False,
                **{'judge_predicts_'+n: regular == k for n, k in zip(('unresolved', *local.LABELS), (-1, 0, 1, 2))},
                **previous, **old_evidence.views(previous, base['class_support'], regular),
                **flags, **local.view_flags(flags, int(base['prediction']), regular)}

    def _resolve_from_base(self, base, inputs, local_record):
        if not self.review_route(base) or local_record is None:
            return base
        try:
            program, observation, pair_ref, interpretation, judgment, vision_record = inputs
            values = self._values(*inputs, base, local_record)
            selected = self.rubric.select(values, int(base['prediction']), visual.regular_label(judgment))
        except (ValueError, KeyError, TypeError, IndexError):
            return {**base, 'local_review_error': 'invalid_or_unbound_local_observation'}
        if selected is None:
            return base
        if selected['prediction'] == base['prediction']:
            return {**base, 'local_rule_agreement': selected}
        return {'covered': True, 'prediction': selected['prediction'], 'reason': 'local_semantic_review_override',
                'local_rule': selected, 'local_observation_ref': local_record['record_ref'],
                'observer_identity_ref': digest(self.artifact['observer_profile']), 'base_route': base}

    def resolve_bound(self, *inputs, local_record=None, expert_record=None):
        base = self.base.resolve_bound(*inputs, expert_record=expert_record)
        return self._resolve_from_base(base, inputs, local_record)
