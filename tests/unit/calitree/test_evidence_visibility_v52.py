from copy import deepcopy

from critical.core.calibration import evidence_visibility_v52 as visibility
from critical.core.decision.bound_evidence_v2 import bind_program, derive_record
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def test_nonabsence_view_confidence_survives_even_when_effective_state_is_unchanged():
    program = bind_program('Move the bowl left', draft())
    clear = observation(program)
    unclear = deepcopy(clear)
    unclear['checks']['endpoint'].update(edited_coverage='occluded', source_anchor='ambiguous')
    assert derive_record(program, clear, 'pair')['checks']['endpoint']['desired_state'] == 'true'
    assert derive_record(program, unclear, 'pair')['checks']['endpoint']['desired_state'] == 'true'
    a = visibility.project(program, clear, 'pair')['features']
    b = visibility.project(program, unclear, 'pair')['features']
    assert not a['visibility_outcome_desired_true_view_inadequate_any']
    assert b['visibility_outcome_desired_true_view_inadequate_any']
    assert b['visibility_outcome_desired_true_source_ambiguous_any']


def test_visibility_is_duplicate_invariant_and_empty_roles_do_not_have_all_support():
    instruction = 'Move the bowl left'
    a = draft()
    p = bind_program(instruction, a)
    expected = visibility.project(p, observation(p), 'pair')
    b = deepcopy(a)
    duplicate = deepcopy(b['checks'][0])
    duplicate['id'] = 'endpoint_copy'
    b['checks'].append(duplicate)
    q = bind_program(instruction, b)
    assert visibility.project(q, observation(q), 'pair') == expected
    assert not expected['features']['visibility_preservation_source_anchor_identified_all']


def test_visibility_couplings_respect_absence_guard_and_missing_evidence():
    instruction = 'Remove the bowl'
    d = draft(instruction, kind='absence')
    d['checks'][0].update(question='Does the original bowl remain?', expected_state='false', absence_when='false')
    p = bind_program(instruction, d)
    v = observation(p, endpoint='false')
    v['checks']['endpoint']['source_anchor'] = 'ambiguous'
    f = visibility.project(p, v, 'pair')['features']
    assert f['visibility_outcome_source_anchor_ambiguous_any']
    assert not f['visibility_outcome_desired_true_source_ambiguous_any']
    assert f['visibility_outcome_desired_unknown_view_adequate_any']
    assert visibility.project(p, None, 'pair') is None
