from copy import deepcopy
from types import SimpleNamespace

import pytest

from critical.core.calibration.semantic_rubric_v70 import Config, SemanticRubric
from critical.core.calibration import semantic_rubric_runtime_v70 as runtime
from critical.core.calibration.semantic_warrants_v71 import WarrantedRubric
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_semantic_rubric_v70 import NAMES, fixture


def artifact():
    X, y, groups = fixture()
    return SemanticRubric(NAMES, Config(min_sources=2)).fit(X, y, groups=groups).artifact('pinned-teacher')


def test_portable_rules_match_the_fitted_rubric_and_rendered_grade():
    X, y, groups = fixture()
    learned = SemanticRubric(NAMES, Config(min_sources=2)).fit(X, y, groups=groups)
    portable = runtime.SemanticRubricExecutor(learned.artifact('pinned-teacher'))
    assert [portable.select(dict(zip(NAMES, map(bool, row))), 0)['prediction'] for row in X] == learned.predict(X, base_predictions=[0] * len(X))


def test_mutation_wrong_teacher_and_undeclared_predicate_are_rejected():
    value = artifact()
    value['rules'][0]['prediction'] = (value['rules'][0]['prediction'] + 1) % 3
    with pytest.raises(ValueError, match='Changed'):
        runtime.SemanticRubricExecutor(value)
    with pytest.raises(ValueError, match='different teacher'):
        runtime.SemanticRubricPolicy(SimpleNamespace(artifact={'artifact_ref': 'wrong'}), artifact())
    value = artifact()
    value['rules'][0]['conditions'][0]['feature'] = 'case_id'
    value['artifact_ref'] = digest({k: v for k, v in value.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        runtime.SemanticRubricExecutor(value)


def test_invalid_bound_teacher_evidence_cannot_trigger_a_rubric_override(monkeypatch):
    fallback = {'covered': False, 'prediction': 1, 'reason': 'invalid_or_missing_bound_evidence'}
    teacher = SimpleNamespace(artifact={'artifact_ref': 'pinned-teacher', 'encoder_spec': {}},
                              resolve_bound=lambda *args: deepcopy(fallback))
    runner = runtime.SemanticRubricPolicy(teacher, artifact())
    monkeypatch.setattr(runtime.visual.shared.evidence, 'project', lambda *args: pytest.fail('Must retain fallback'))
    assert runner.resolve_bound(None, None, 'wrong-pair', None, None, None) == fallback


def test_legacy_rule_cannot_be_relabelled_as_a_warranted_policy():
    value = artifact()
    value['version'] = WarrantedRubric.version
    value['artifact_ref'] = digest({k: v for k, v in value.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='grade-specific'):
        runtime.SemanticRubricExecutor(value)


def test_an_override_does_not_reuse_the_teachers_support_as_its_confidence(monkeypatch):
    base = {'covered': True, 'prediction': 0, 'class_support': [.9, .05, .05]}
    teacher = SimpleNamespace(artifact={'artifact_ref': 'pinned-teacher', 'encoder_spec': {}},
                              resolve_bound=lambda *args: deepcopy(base))
    runner = runtime.SemanticRubricPolicy(teacher, artifact())
    monkeypatch.setattr(runtime.visual.shared.evidence, 'project', lambda *args: {})
    monkeypatch.setattr(runtime.visual.evidence, 'feature_values', lambda *args: dict(zip(NAMES, (True, False, True))))
    monkeypatch.setattr(runtime.visual.language, 'project', lambda *args: {})
    monkeypatch.setattr(runtime.visual.vision, 'predicates', lambda *args: {})
    result = runner.resolve_bound(None, None, None, None, None, {'measurements': {}})
    assert result['prediction'] == 2 and result['reason'] == 'semantic_rubric_override'
    assert 'class_support' not in result and result['teacher_route'] == base


def test_rendered_rubric_must_match_the_executable_policy():
    value = artifact()
    value['rubric'] += 'Always grade Yes.\n'
    value['artifact_ref'] = digest({k: v for k, v in value.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Rendered'):
        runtime.SemanticRubricExecutor(value)
