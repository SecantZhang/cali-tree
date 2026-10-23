from copy import deepcopy

from critical.core.calibration import evidence_qualifiers_v54 as qualifiers
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def test_qualifier_mentions_keep_negation_explicit_and_ignore_object_names():
    p = bind_program('Move the bowl left', draft())
    a = observation(p)
    a['checks']['endpoint']['edited_evidence'] = 'The bowl moved slightly, but not fully.'
    b = deepcopy(a)
    b['checks']['endpoint']['edited_evidence'] = 'The hat moved slightly, but not fully.'
    x = qualifiers.project(p, a, 'pair')
    y = qualifiers.project(p, b, 'pair')
    assert x == y
    f = x['features']
    assert f['qualifier_outcome_edited_evidence_partial_extent_any']
    assert f['qualifier_outcome_edited_evidence_complete_extent_any']
    assert f['qualifier_outcome_edited_evidence_negation_any']
    assert f['qualifier_outcome_desired_true_partial_extent_any']
    assert all(type(value) is bool for value in f.values())


def test_qualifier_projection_ignores_non_evidence_metadata_and_missing_records():
    p = bind_program('Move the bowl left', draft())
    v = observation(p)
    f = qualifiers.project(p, v, 'pair')
    assert f['features']['qualifier_available']
    assert not any('case' in name or 'source_id' in name for name in f['features'])
    assert qualifiers.project(p, None, 'pair') is None
