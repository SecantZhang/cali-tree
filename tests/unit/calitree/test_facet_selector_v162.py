from itertools import product
import json

import numpy as np
import pytest

from critical.core.calibration.facet_selector_v162 import (FacetSelector, LABELS, project,
    merge_adjacent, execute)
from critical.core.decision.artifacts import digest
from critical.core.decision.outcome_policy_v160 import CONTRACT_REF


def record(**changes):
    return {'new_requested_content': 'some', 'all_material_facets': 'yes', 'operation_fidelity': 'faithful',
        'source_entity_fidelity': 'preserved', 'scope_coverage': 'full', 'evidence': 'fixture', 'material_gap': 'none', **changes}


def test_facet_projection_keeps_unknown_separate_from_negative_outcomes():
    assert not any(project(None).values())
    unknown = project(record(new_requested_content='uncertain', all_material_facets='uncertain'))
    assert unknown['facet_available']
    assert not any(unknown['facet_'+label+'_outcome_ready'] for label in LABELS)
    full = project(record(operation_fidelity='unfaithful', source_entity_fidelity='material_unrequested_change'))
    assert full['facet_yes_outcome_ready'] and not full['facet_partial_outcome_ready']
    assert full['facet_operation_fidelity__unfaithful']
    assert project(record(all_material_facets='no'))['facet_partial_outcome_ready']


def test_selector_retains_local_counterexample_and_exports_identical_decisions():
    names = ['facet_'+label+'_outcome_ready' for label in LABELS]+['facet_operation_fidelity__faithful']
    X = np.zeros((9, 4), dtype=bool); y = np.repeat(np.arange(3), 3)
    for i, grade in enumerate(y):
        X[i, grade] = True; X[i, 3] = True
    protected = np.array([[False, False, True, False]])
    model = FacetSelector(names).fit(X, y, base=np.zeros(9, dtype=int), eligible=np.ones(9, dtype=bool),
        groups=['source'+str(i) for i in range(9)], protected_X=protected, protected_y=np.array([0]),
        protected_base=np.array([0]), protected_eligible=np.array([True]))
    assert np.array_equal(model.predict(X, base=np.zeros(9, dtype=int), eligible=np.ones(9, dtype=bool)), y)
    assert model.predict(protected, base=np.array([0]), eligible=np.array([True])).tolist() == [0]
    artifact = model.artifact()
    assert all(r['support']['gain_sources'] >= 3 for r in artifact['rules'])
    for row, expected in zip(X, y):
        values = {n: bool(v) for n, v in zip(names, row)}
        assert execute(artifact, values, 0, True) == expected
        assert execute(artifact, values, 0, False) == 0
    with pytest.raises(ValueError, match='Complete explicit Boolean'):
        execute(artifact, {}, 0, True)
    # Closed vocabulary rejects source/editor identifiers as runtime features.
    with pytest.raises(ValueError, match='Closed named'):
        FacetSelector(names+['source_group_source0'])


def rule(grade, **conditions):
    return {'from_grade': 0, 'grade': grade, 'conditions': [{'feature': n, 'value': v} for n, v in conditions.items()]}


def flat(rules, values, base):
    for row in rules:
        if base == row['from_grade'] and all(values[t['feature']] == t['value'] for t in row['conditions']):
            return row['grade']
    return base


def test_adjacent_semantic_union_is_exact_on_the_full_boolean_domain():
    before = [rule(2, facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=True),
              rule(2, facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=False)]
    after = merge_adjacent(before)
    assert len(after) == 1 and len(after[0]['conditions']) == 1 and len(before) == 2
    artifact = {'rules': after, 'outcome_contract_ref': CONTRACT_REF}
    artifact['artifact_ref'] = digest(artifact)
    for witness, faithful, eligible, base in product((False, True), (False, True), (False, True), (-1, 0, 1, 2)):
        values = {'facet_yes_outcome_ready': witness, 'facet_operation_fidelity__faithful': faithful}
        assert execute(artifact, values, base, eligible) == (flat(before, values, base) if eligible else base)


def test_merge_never_crosses_an_intervening_different_expert_action():
    rules = [rule(2, facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=True),
             rule(1, facet_partial_outcome_ready=True),
             rule(2, facet_yes_outcome_ready=True, facet_operation_fidelity__faithful=False)]
    assert merge_adjacent(rules) == rules


def test_study_cannot_fit_from_mock_or_incomplete_native_observations(tmp_path):
    from run.calitree_facet_selector_v162 import load_observations
    (tmp_path/'manifest.json').write_text('{}')
    for ready, mock, complete in ((False, True, True), (True, True, True), (True, False, False)):
        (tmp_path/'verification.json').write_text(json.dumps({'passed': True, 'complete': complete,
            'fitting_ready': ready, 'mock_transport_test': mock}))
        with pytest.raises(ValueError, match='Complete real native'):
            load_observations(tmp_path, tmp_path, {})
