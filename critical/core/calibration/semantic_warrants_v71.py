"""Semantic obligations for an interpretable grading rubric.

These constrain which learned clauses may justify a grade. Uncertainty, task
type and neural similarity alone are never affirmative grading warrants.
"""


def warranted(label, conditions):
    positive = {c['feature'] for c in conditions if c['value']}
    def any_state(field, states, quantifiers=('all', 'any')):
        return any('meaning_' + field + '_' + state + '_' + q in positive
                   for state in states for q in quantifiers)
    if label == 0:
        required_instance = any_state('retention_need', ('same_instance_essential',), ('all',))
        lost_instance = (any_state('identity_evidence', ('replacement_or_loss',), ('all',)) or
                         'identity_all_false_all' in positive)
        return (any_state('progress', ('none', 'incidental_change_only'), ('all',)) or
                any_state('endpoint_gap', ('wrong_direction_or_target',), ('all',)) or
                (required_instance and lost_instance))
    if label == 1:
        progress = any_state('progress', ('toward_requested_goal',))
        endpoint = any_state('progress', ('requested_endpoint',))
        shortfall = (any_state('collateral_materiality', ('material_unrequested_change',)) or
                     any_state('identity_materiality', ('material_shortfall',)) or
                     any_state('endpoint_gap', ('core_endpoint_missing', 'minor_detail', 'wrong_direction_or_target')))
        return progress or (endpoint and shortfall)
    if label == 2:
        return (any_state('progress', ('requested_endpoint',), ('all',)) and
                any_state('identity_materiality', ('no_shortfall', 'not_relevant', 'immaterial_difference'), ('all',)) and
                any_state('collateral_materiality', ('none', 'minor_incidental'), ('all',)))
    return False


from .semantic_rubric_v70 import SemanticRubric


class WarrantedRubric(SemanticRubric):
    version = 'warranted-teacher-semantic-rubric-v71'

    def accepts_clause(self, label, conditions):
        return super().accepts_clause(label, conditions) and warranted(label, conditions)
