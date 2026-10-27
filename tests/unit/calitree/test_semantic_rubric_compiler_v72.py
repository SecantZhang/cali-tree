from itertools import product

from critical.core.calibration.semantic_rubric_v70 import Config
from critical.core.calibration.semantic_warrants_v71 import WarrantedRubric
from critical.core.calibration.semantic_rubric_compiler_v72 import simplify
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor
from critical.core.decision.semantic_interpretation_v5 import FIELDS


def artifact(terms):
    model = WarrantedRubric([t['feature'] for t in terms], Config(mode='correct', min_sources=2, max_literals=4))
    model.rules = [{'conditions': terms, 'prediction': 1, 'teacher_grade': 0,
                    'support': {'correct_sources': 2, 'correct_cases': 2, 'incorrect_cases': 0}}]
    model.fit_stats = {'rules': 1, 'fitting_rows': 2}
    return model.artifact('teacher')


def test_all_implies_any_is_compiled_without_changing_valid_semantic_decisions():
    progress = 'meaning_progress_toward_requested_goal_all'
    all_name = 'meaning_retention_need_replacement_authorized_all'
    any_name = 'meaning_retention_need_replacement_authorized_any'
    original = artifact([{'feature': n, 'value': True} for n in (progress, all_name, any_name)])
    compiled, certificate = simplify(original)
    assert certificate['literals_before'] == 3 and certificate['literals_after'] == 2
    before, after = SemanticRubricExecutor(original), SemanticRubricExecutor(compiled)
    for n in (1, 2, 3):
        for states in product(FIELDS['retention_need'], repeat=n):
            flags = {progress: True, all_name: all(s == 'replacement_authorized' for s in states),
                     any_name: any(s == 'replacement_authorized' for s in states)}
            assert before.select(flags, 0)['prediction'] == after.select(flags, 0)['prediction']


def test_mutually_exclusive_progress_states_remove_a_redundant_negative():
    original = artifact([{'feature': 'meaning_progress_toward_requested_goal_all', 'value': True},
                         {'feature': 'meaning_progress_none_all', 'value': False}])
    compiled, proof = simplify(original)
    assert len(compiled['rules'][0]['conditions']) == 1
    assert proof['proof_steps'][0]['field'] == 'progress'


def test_physical_measurements_are_not_equated_with_semantic_judgments():
    original = artifact([{'feature': 'meaning_progress_toward_requested_goal_all', 'value': True},
                         {'feature': 'meaning_retention_need_replacement_authorized_all', 'value': True},
                         {'feature': 'intent_replacement', 'value': True}])
    compiled, proof = simplify(original)
    assert proof['literals_before'] == proof['literals_after'] == 3
    assert compiled['rules'] == original['rules']
