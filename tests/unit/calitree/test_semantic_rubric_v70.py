from dataclasses import replace

import numpy as np
import pytest

from critical.core.calibration.semantic_rubric_v70 import Config, SemanticRubric, allowed_feature


NAMES = ['meaning_progress_requested_endpoint_all', 'meaning_collateral_materiality_material_unrequested_change_all',
         'intent_finish']


def fixture():
    X = np.asarray([[1, 0, 1], [1, 0, 1], [1, 0, 0], [1, 1, 1], [1, 1, 0], [0, 1, 0], [0, 0, 0]])
    y = np.asarray([2, 2, 2, 1, 1, 0, 0])
    return X, y, list('abcdefg')


def test_reconstruction_has_executable_semantics_and_falls_back_outside_rules():
    X, y, groups = fixture()
    rubric = SemanticRubric(NAMES, Config(min_sources=2)).fit(X, y, groups=groups)
    predicted = rubric.predict(X)
    assert any(p >= 0 for p in predicted)
    assert all(p < 0 or p == gold for p, gold in zip(predicted, y))
    assert all(r['support']['correct_sources'] >= 2 for r in rubric.rules)
    assert 'requested endpoint' in rubric.render()
    assert 'retain the boosted teacher' in rubric.render()
    artifact = rubric.artifact('teacher-contract')
    assert artifact['teacher_ref'] == 'teacher-contract'
    assert not any('source_group' in r for r in artifact['rules'])


def test_protected_actual_predictions_veto_a_locally_plausible_rule():
    X, y, groups = fixture()
    protected = np.asarray([[1, 0, 1]])
    rubric = SemanticRubric(NAMES, Config(min_sources=2)).fit(
        X, y, groups=groups, protected_X=protected, protected_y=[1], protected_base=[1])
    assert rubric.predict(protected, base_predictions=[1]) == [1]


def test_repeated_outputs_from_one_source_do_not_count_as_independent_support():
    X, y, _ = fixture()
    rubric = SemanticRubric(NAMES, Config(min_sources=2)).fit(X, y, groups=['one-source'] * len(X))
    assert rubric.rules == []


def test_task_only_patterns_cannot_become_judging_rules():
    X = [[1, 0], [1, 1], [0, 0], [0, 1]]
    rubric = SemanticRubric(['intent_finish', 'requires_attribute'], Config(min_sources=1)).fit(
        X, [2, 2, 0, 0], groups=list('abcd'))
    assert rubric.rules == []


def test_correction_rule_is_bound_to_the_teacher_grade_it_was_validated_for():
    X, y, groups = fixture()
    baseline = np.asarray([0, 0, 0, 1, 1, 0, 0])
    config = Config(mode='correct', min_sources=2, minimum_precision=.8)
    rubric = SemanticRubric(NAMES, config).fit(X, y, groups=groups, base_predictions=baseline)
    assert rubric.predict(X[:3], base_predictions=baseline[:3]) == [2, 2, 2]
    assert rubric.predict(X[:3], base_predictions=[1, 1, 1]) == [1, 1, 1]


def test_closed_vocabulary_and_boolean_projection_are_enforced():
    assert not allowed_feature('rationale_completion_mentioned', 'auxiliary')
    assert not allowed_feature('case_id', 'auxiliary')
    assert not allowed_feature('vision_target_match_ge_0.9', 'semantic')
    with pytest.raises(ValueError, match='Boolean'):
        SemanticRubric(NAMES).fit([[.5, 0, 1]], [2], groups=['a'])
    with pytest.raises(ValueError, match='configuration'):
        replace(Config(), mode='memorize')
