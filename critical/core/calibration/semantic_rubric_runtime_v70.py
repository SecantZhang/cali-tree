"""Bound execution of a compact semantic rubric with a frozen v69 fallback."""
from copy import deepcopy

from . import visual_semantic_policy_v69 as visual
from .semantic_rubric_v70 import VERSION, Config, DESCRIPTIONS, SemanticRubric, allowed_feature, anchor
from .semantic_warrants_v71 import WarrantedRubric, warranted
from ..decision.artifacts import digest


class SemanticRubricExecutor:
    def __init__(self, artifact):
        expected = {'version', 'config', 'rules', 'feature_names', 'training', 'teacher_ref',
                    'contract_ref', 'rubric', 'artifact_ref'}
        if set(artifact) != expected or artifact['version'] not in (VERSION, WarrantedRubric.version):
            raise ValueError('Invalid semantic rubric artifact')
        if digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact['artifact_ref']:
            raise ValueError('Changed semantic rubric artifact')
        if artifact['contract_ref'] != digest(DESCRIPTIONS):
            raise ValueError('Changed semantic predicate descriptions')
        config = Config(**artifact['config'])
        if not isinstance(artifact['teacher_ref'], str) or not artifact['teacher_ref']:
            raise ValueError('A pinned teacher is required')
        if not isinstance(artifact['rules'], list) or len(artifact['rules']) > config.max_rules:
            raise ValueError('Rubric rule limit exceeded')
        used = set()
        for rule in artifact['rules']:
            if set(rule) != {'conditions', 'prediction', 'teacher_grade', 'support'}:
                raise ValueError('Invalid semantic rule fields')
            if type(rule['prediction']) is not int or rule['prediction'] not in (0, 1, 2):
                raise ValueError('Invalid semantic grade')
            context = rule['teacher_grade']
            if context is not None and (type(context) is not int or context not in (0, 1, 2)):
                raise ValueError('Invalid teacher context')
            if (config.mode == 'reconstruct') != (context is None):
                raise ValueError('Rubric mode and teacher context differ')
            conditions = rule['conditions']
            if not 1 <= len(conditions) <= config.max_literals or len({c.get('feature') for c in conditions}) != len(conditions):
                raise ValueError('Invalid semantic conjunction')
            for term in conditions:
                if (set(term) != {'feature', 'value'} or type(term['value']) is not bool or
                        not allowed_feature(term['feature'], config.family)):
                    raise ValueError('Undeclared semantic predicate')
                used.add(term['feature'])
            if not anchor(conditions):
                raise ValueError('A positive semantic warrant is required')
            if artifact['version'] == WarrantedRubric.version and not warranted(rule['prediction'], conditions):
                raise ValueError('A grade-specific semantic warrant is required')
            support = rule['support']
            if (set(support) != {'correct_sources', 'correct_cases', 'incorrect_cases'} or
                    any(type(v) is not int or v < 0 for v in support.values()) or
                    support['correct_sources'] < config.min_sources or
                    support['correct_sources'] > support['correct_cases']):
                raise ValueError('Invalid source support')
        if artifact['feature_names'] != sorted(used):
            raise ValueError('Undeclared or unused inference feature')
        renderer = SemanticRubric(artifact['feature_names'] or ['meaning_progress_none_all'], config)
        renderer.rules = artifact['rules']
        if renderer.render() != artifact['rubric']:
            raise ValueError('Rendered rubric differs from executable rules')
        self.artifact = deepcopy(artifact)

    def select(self, values, teacher_grade):
        if type(teacher_grade) is not int or teacher_grade not in (0, 1, 2):
            raise ValueError('A valid current teacher grade is required')
        if any(type(values.get(n)) is not bool for n in self.artifact['feature_names']):
            raise ValueError('Named Boolean evidence is missing')
        for index, rule in enumerate(self.artifact['rules']):
            if rule['teacher_grade'] is not None and rule['teacher_grade'] != teacher_grade:
                continue
            if all(values[t['feature']] == t['value'] for t in rule['conditions']):
                return {'prediction': rule['prediction'], 'rule_index': index, 'conditions': deepcopy(rule['conditions'])}
        return {'prediction': teacher_grade, 'rule_index': None, 'conditions': []}


class SemanticRubricPolicy:
    def __init__(self, teacher, rubric):
        self.teacher, self.rubric = teacher, SemanticRubricExecutor(rubric)
        if teacher.artifact['artifact_ref'] != rubric['teacher_ref']:
            raise ValueError('Semantic rubric belongs to a different teacher')
        self.artifact = {'version': 'bound-semantic-rubric-hybrid-v70',
                         'teacher_ref': rubric['teacher_ref'], 'rubric_ref': rubric['artifact_ref'],
                         'encoder_spec': deepcopy(teacher.artifact['encoder_spec'])}
        self.artifact['artifact_ref'] = digest(self.artifact)

    def resolve_bound(self, program, observation, pair_ref, interpretation, judgment, vision_record):
        base = self.teacher.resolve_bound(program, observation, pair_ref, interpretation, judgment, vision_record)
        if not base['covered']:
            return base
        try:
            record = visual.shared.evidence.project(program, observation, pair_ref, interpretation)
            values = {**visual.evidence.feature_values(program, record),
                      **visual.language.project(program, judgment),
                      **visual.vision.predicates(vision_record['measurements'])}
            result = self.rubric.select(values, base['prediction'])
        except (ValueError, KeyError, TypeError):
            return {**base, 'rubric_error': 'invalid_semantic_evidence'}
        if result['rule_index'] is None:
            return {**base, 'semantic_rubric_match': False}
        if result['prediction'] == base['prediction']:
            return {**base, 'reason': 'semantic_rubric_agreement', 'rubric_rule': result}
        # The teacher's numerical support must not be presented as confidence
        # for a different grade selected by the semantic rubric.
        return {'covered': True, 'prediction': result['prediction'], 'reason': 'semantic_rubric_override',
                'rubric_rule': result, 'teacher_route': base}
