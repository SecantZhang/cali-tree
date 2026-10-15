from copy import deepcopy
from fractions import Fraction
from itertools import product
import json
from pathlib import Path

import numpy as np
import pytest

from critical.core.calibration.semantic_hierarchy.features_v2 import (
    FEATURES, SPECS, SCOPES, VERSION, project, scope_record, synthetic_record, validate_record,
)
from critical.core.calibration.semantic_hierarchy.rule_search_v2 import (
    LIMITS, SemanticRuleCalibrator, UnsupportedPolicyError, exact_rank, pack_masks,
    popcount, predict_program,
)
from critical.core.calibration.instruction_semantic_rules import program_prediction as old_scalar_prediction
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def samples(n):
    X, y, groups, batches = [], [], [], []
    for i in range(n):
        label = i % 3
        X.append(synthetic_record(all_requested_grounded='true' if label == 2 else 'false',
                                 all_outcomes_grounded='true' if label == 2 else 'false',
                                 any_outcome_direct='true' if label > 0 else 'false',
                                 any_intermediate='true' if label == 1 else 'false',
                                 preservation_compatible='true' if i % 2 else 'false'))
        y.append(label); groups.append(f'source-{i:04d}'); batches.append(f'batch-{i // 12}')
    return X, y, groups, batches


def test_projection_is_closed_and_preserves_unknown_dependency_semantics():
    instruction = 'Move the bowl left'
    d = draft(instruction); c = deepcopy(d['checks'][0]); c.update(id='identity', role='identity', kind='identity')
    d['checks'].append(c); d['checks'][0]['dependencies'] = ['identity']
    p = bind_program(instruction, d); o = observation(p, endpoint='true', identity='unknown')
    x = project(p, o, 'pair')
    assert set(x) == {'version', 'features'}
    assert set(x['features']) == set(FEATURES)
    assert x['features']['any_outcome_direct'] == 'true'
    assert x['features']['any_outcome_grounded'] == 'unknown'
    assert x['features']['all_requested_grounded'] == 'unknown'
    assert scope_record(p)['requires_identity'] is True
    bad = deepcopy(x); bad['reference'] = 'yes'
    with pytest.raises(ValueError):
        validate_record(bad)


def test_absent_family_cannot_supply_positive_witness_and_names_do_not_enter_features():
    p = bind_program('Move the bowl left', draft()); x = project(p, observation(p), 'pair')
    assert x['features']['any_style_outcome'] == 'not_applicable'
    p2 = bind_program('Move the vase left', draft('Move the vase left'))
    assert x == project(p2, observation(p2), 'pair')
    assert 'bowl' not in json.dumps(x) and 'vase' not in json.dumps(x)


def test_scope_uses_program_only_not_evidence_or_reference():
    p = bind_program('Move the bowl left', draft())
    a = project(p, observation(p), 'pair'); b = project(p, observation(p, endpoint='false'), 'pair')
    assert {k: a['features'][k] for k in SCOPES} == {k: b['features'][k] for k in SCOPES}


def test_all_physical_operation_kinds_have_scope_channels():
    from critical.core.decision.bound_evidence_v2 import KINDS
    from critical.core.calibration.semantic_hierarchy.features_v2 import SCOPE_KINDS
    assert set(SCOPE_KINDS) == set(KINDS) - {'identity'}


@pytest.mark.parametrize('n', [12, 24, 48, 96])
def test_fit_restore_and_support_at_all_required_sizes(n):
    X, y, groups, batches = samples(n)
    model = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    assert [r['prediction'] for r in model.predict_records(X)] == y
    restored = SemanticRuleCalibrator.restore(json.loads(json.dumps(model.metadata())))
    assert restored.predict_records(X) == model.predict_records(X)
    assert model.search_diagnostic['packed_words_per_mask'] == (n + 63) // 64
    assert model.metadata()['training']['metrics']['total'] == n
    for entries in model.metadata()['support'].values():
        for item in entries:
            assert item['distinct_sources'] >= 2
            assert sum(item['originating_batches'].values()) == item['distinct_sources']


def test_row_order_does_not_change_selected_artifacts():
    X, y, groups, batches = samples(24)
    a = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    b = SemanticRuleCalibrator().fit(X[::-1], y[::-1], source_groups=groups[::-1], source_batches=batches[::-1])
    assert a.candidates() == b.candidates()


def test_source_duplicates_are_rejected_and_missing_records_stay_unresolved():
    X, y, groups, batches = samples(12)
    with pytest.raises(ValueError, match='Distinct sources'):
        SemanticRuleCalibrator().fit(X, y, source_groups=['same'] * 12, source_batches=batches)
    X[0] = None
    model = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    assert model.predict_records(X)[0]['prediction'] == -1
    assert model.metadata()['training']['metrics']['total'] == 12
    assert model.metadata()['training']['metrics']['unresolved'] >= 1


def test_collapse_is_reported_instead_of_constant_fallback():
    X, y, groups, batches = samples(12)
    X = [synthetic_record() for _ in X]
    with pytest.raises(UnsupportedPolicyError):
        SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)


def test_batches_are_counted_as_support_not_runtime_predicates():
    X, y, groups, batches = samples(24)
    model = SemanticRuleCalibrator(limits={**LIMITS, 'min_clause_batches': 2}).fit(X, y, source_groups=groups, source_batches=batches)
    for boundary in ('yes', 'partial'):
        for support in model.metadata()['support'][boundary]:
            assert len(support['originating_batches']) >= 2
        for clause in model.metadata()[boundary]:
            assert all(atom['feature'] in FEATURES for atom in clause)


def test_packed_bits_cross_word_boundaries_without_large_lookup():
    values = [0, 1 << 63, 1 << 64, (1 << 96) - 1]
    packed = pack_masks(values, 96)
    assert packed.shape == (4, 2) and packed.dtype == np.uint64
    assert popcount(packed).tolist() == [0, 1, 1, 96]


def test_exact_objective_uses_rational_counts_without_overflow():
    rank = exact_rank([28, 25, 26], [30, 28, 31], [32, 32, 32], 4, 2)
    assert rank[0] == (Fraction(56, 62) + Fraction(50, 60) + Fraction(52, 63)) / 3
    assert rank[1] == Fraction(25, 32) and rank[2:] == (79, -4, -2)


def test_scalar_prediction_matches_legacy_equivalent_grammar_for_all_states():
    yes = [[{'feature': 'all_requested_grounded', 'test': 'true'}, {'feature': 'no_unrelated_disappearance', 'test': 'true'}]]
    partial = [[{'feature': 'any_outcome_direct', 'test': 'true'}], [{'feature': 'any_intermediate', 'test': 'true'}]]
    names = ('all_requested_grounded', 'no_unrelated_disappearance', 'any_outcome_direct', 'any_intermediate')
    convert = lambda clauses: [[{'fact': a['feature'], 'test': a['test']} for a in c] for c in clauses]
    for states in product(('true', 'false', 'unknown', 'not_applicable'), repeat=4):
        x = synthetic_record(**dict(zip(names, states)))
        assert predict_program(x, yes, partial) == old_scalar_prediction({'facts': x['features']}, convert(yes), convert(partial))
    assert predict_program(None, yes, partial) == -1


def test_incidental_preservation_cannot_be_the_only_positive_condition():
    X, y, groups, batches = samples(12)
    model = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    x = synthetic_record(preservation_compatible='true', identity_compatible='true')
    assert model.predict_records([x])[0]['prediction'] == 0
    a = model.metadata(); a['yes'][0][0] = {'feature': 'preservation_compatible', 'test': 'true'}
    from critical.core.decision.artifacts import digest
    a['artifact_ref'] = digest({k: v for k, v in a.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='requested physical witness'):
        SemanticRuleCalibrator.restore(a)


def test_selected_policy_matches_exhaustive_exact_ranking_of_bounded_space():
    X, y, groups, batches = samples(12)
    for i, x in enumerate(X):
        x['features']['requires_style'] = 'true' if i % 2 else 'false'
        x['features']['no_unrelated_disappearance'] = 'true' if i % 4 else 'false'
    X[2]['features']['all_requested_grounded'] = 'unknown'
    X[0]['features']['any_outcome_direct'] = 'true'
    limits = {**LIMITS, 'atoms_per_clause': 2, 'clauses_per_boundary': 2,
              'terms_per_boundary': 12, 'regions_per_boundary': 64}
    model = SemanticRuleCalibrator(limits=limits).fit(X, y, source_groups=groups, source_batches=batches)
    space = model.search_space; best = None; winner = None
    def clauses(indices):
        return [[space['atoms'][a] for a in space['terms'][t]] for t in indices]
    for i, yr in enumerate(space['yes_regions']):
        for j, pr in enumerate(space['partial_regions']):
            yes, part = clauses(yr), clauses(pr)
            p = [predict_program(x, yes, part) for x in X]
            tp = [sum(a == b == k for a, b in zip(p, y)) for k in range(3)]
            if min(tp) < 2:
                continue
            cost = sum(len(c) for c in yes + part)
            rank = exact_rank(tp, [p.count(k) for k in range(3)], [4, 4, 4], cost, len(yes) + len(part))
            if best is None or rank > best:
                best, winner = rank, (yes, part)
    assert winner == (model.metadata()['yes'], model.metadata()['partial'])


def test_evidence_improvement_cannot_reduce_a_resolved_label_with_fixed_scope():
    X, y, groups, batches = samples(24)
    model = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    for x in X:
        old = model.predict_records([x])[0]['prediction']
        improved = deepcopy(x)
        for name in FEATURES:
            if SPECS[name]['role'] != 'context':
                improved['features'][name] = 'true'
        assert model.predict_records([improved])[0]['prediction'] >= old


def test_avoiding_a_duplicate_is_not_edit_progress():
    instruction = 'Move the bowl left without duplicating it'
    d = draft(instruction); c = deepcopy(d['checks'][0])
    c.update(id='duplicate', kind='count', question='Is an extra bowl copy present?', expected_state='false', absence_when='never')
    d['checks'].append(c); p = bind_program(instruction, d)
    x = project(p, observation(p, endpoint='false', duplicate='false'), 'pair')
    assert x['features']['all_requested_grounded'] == 'false'
    assert x['features']['any_outcome_direct'] == 'false'
    assert x['features']['any_outcome_grounded'] == 'false'
    assert x['features']['all_count_outcomes'] == 'not_applicable'
    assert x['features']['any_count_outcome'] == 'not_applicable'


def test_negative_polarity_original_removal_still_is_a_positive_witness():
    instruction = 'Remove the cylinder'; d = draft(instruction, kind='absence')
    d['checks'][0].update(question='Does any of the original cylinder remain?', expected_state='false', absence_when='false', absence_source_anchor='required')
    p = bind_program(instruction, d)
    x = project(p, observation(p, endpoint='false'), 'pair')
    assert x['features']['any_outcome_direct'] == 'true'
    assert x['features']['all_absence_outcomes'] == 'true'
