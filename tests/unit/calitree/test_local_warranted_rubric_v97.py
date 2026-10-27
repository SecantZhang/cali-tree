from copy import deepcopy

import pytest

from critical.core.calibration import local_warranted_rubric_v97 as rubric
from critical.core.calibration.seeded_rubric_v73 import Search
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_local_rubric_v94 import value


def test_unrelated_deletion_does_not_automatically_cap_goal_success():
    p = bind_program('Move the bowl left', draft()); v = value()
    f = rubric.claims(p, v)
    assert f['local_yes_ready'] and not f['local_partial_ready']
    f = rubric.claims(p, {**v, 'collateral_affects_goal': 'yes'})
    assert f['local_partial_ready'] and not f['local_yes_ready']


def test_uncertainty_and_global_multi_requirement_summaries_cannot_prove_failure():
    p = bind_program('Move the bowl left', draft()); unknown = {k: 'uncertain' for k in rubric.facts.FIELDS}; unknown['evidence'] = 'The target is occluded.'
    f = rubric.claims(p, unknown)
    assert not any(f['local_'+label+'_ready'] for label in rubric.LABELS)
    hypothetical = deepcopy(p); hypothetical['requirements'].append(hypothetical['requirements'][0])
    f = rubric.claims(hypothetical, value())
    assert not any(f['local_'+label+'_ready'] for label in rubric.LABELS)


def test_inconsistent_identity_claims_cannot_support_a_success_warrant():
    p = bind_program('Move the bowl left', draft()); f = rubric.claims(p, {**value(), 'target': 'authorized_replacement'})
    assert f['local_claim_conflict'] and not f['local_yes_ready']


def test_goal_directed_progress_can_be_partial_before_the_endpoint_exists():
    p = bind_program('Move the bowl left', draft()); f = rubric.claims(p, {**value(), 'endpoint': 'absent'})
    assert f['local_partial_ready'] and not f['local_no_ready'] and not f['local_yes_ready']


def test_local_rules_keep_grade_warrants_and_actual_original_vetoes():
    names = list(rubric.SPECS); flags = {'local_yes_ready': True}
    X = [[int(flags.get(n, False)) for n in names]]*2
    config = Search(mode='grades', min_sources=1, max_guards=0)
    m = rubric.LocalWarrantedRubric(names, config).fit(X, [2, 2], groups=['a', 'b'], base=[0, 0], regular=[-1, -1],
                protected_X=X[:1], protected_y=[0], protected_base=[0], protected_regular=[-1])
    assert m.rules == []
    m.fit(X, [2, 2], groups=['a', 'b'], base=[0, 0], regular=[-1, -1])
    assert m.rules[0]['warrant'] == [{'feature': 'local_yes_ready', 'value': True}]
    assert 'task/preservation' in m.render() and m.metadata()['evidence_contract_ref'] == rubric.CONTRACT_REF


def test_uncertainty_can_select_an_existing_judge_but_cannot_invent_a_failure_grade():
    names = [*rubric.SPECS, 'view_disagrees']; active = {'local_observation_available', 'local_any_uncertainty', 'view_disagrees'}
    X = [[int(n in active) for n in names]]
    model = rubric.LocalWarrantedRubric(names, Search(mode='hybrid', min_sources=1, max_guards=0))
    model.fit(X, [0], groups=['source'], base=[2], regular=[0])
    assert model.rules[0]['action'] == 'regular'
    assert all(r['action'] == 'regular' for r in model.rules)
    assert model.predict(X, base=[2], regular=[0]) == [0]
    assert model.predict(X, base=[2], regular=[-1]) == [2]
    assert 'independent regular visual judgment' in model.render()
    assert rubric.view_flags({}, 0, 2) == {'local_view_teacher_unwarranted': False, 'local_view_regular_warranted': False}


def test_incomplete_cache_is_rejected_before_any_fitting_or_output(monkeypatch, tmp_path):
    from run import calitree_local_warranted_rules_v97 as runner
    cache = tmp_path/'cache'; cache.mkdir(); output = tmp_path/'fitted'
    def forbidden():
        raise AssertionError('Cannot read fitting labels on incomplete observations')
    monkeypatch.setattr(runner, 'arrays', forbidden)
    with pytest.raises(ValueError, match='complete before fitting'):
        runner.run(cache, output)
    assert not output.exists()
