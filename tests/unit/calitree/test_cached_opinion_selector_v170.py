import numpy as np

from critical.core.calibration import cached_opinion_selector_v170 as cached
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation
from tests.unit.calitree.test_rubric_evidence_v73 import interpreted
from tests.unit.calitree.test_semantic_stability_audit_v14 import requirement


def test_full_goal_opinion_can_compete_with_fidelity_and_regular_verdicts():
    p = bind_program('Change the target', draft('Change the target', kind='attribute')); o = observation(p)
    row = {**requirement(), 'collateral_materiality': 'material_unrequested_change'}
    flags = cached.project(p, o, 'pair', interpreted(p, o, {'r1': row}), {'label': 'no', 'rationale': 'Independent disagreement'})
    assert flags['cached_goal_yes'] and flags['cached_goal_partial']
    assert flags['cached_regular_no'] and flags['cached_no_expert_ready'] and flags['cached_yes_expert_ready']


def test_unknown_goal_evidence_does_not_invent_a_negative_verdict():
    p = bind_program('Change the target', draft('Change the target', kind='attribute')); o = observation(p, endpoint='unknown')
    meaning = interpreted(p, o, {'r1': requirement('uncertain', 'uncertain')})
    flags = cached.project(p, o, 'pair', meaning, {'label': 'unresolved', 'rationale': 'Cannot establish the result'})
    assert not any(flags[cached.SEEDS[k]] for k in range(3))
    flags = cached.project(p, o, 'pair', meaning, {'label': 'partial', 'rationale': 'Explicit visual critic opinion'})
    assert flags['cached_partial_expert_ready'] and not flags['cached_goal_partial']


def test_source_specific_seeds_and_scalar_export_preserve_local_veto():
    names = list(cached.SEEDS.values())+['cached_regular_yes']
    y = np.repeat(np.arange(3), 3); X = np.zeros((9, 4), bool)
    for i, k in enumerate(y):X[i, k] = True; X[i, 3] = k == 2
    model = cached.CachedOpinionSelector(names).fit(X, y, base=np.zeros(9, dtype=int), eligible=np.ones(9, bool),
        groups=list('abcdefghi'), protected_X=[[False, False, True, False]], protected_y=np.array([0]),
        protected_base=np.array([0]), protected_eligible=np.array([True]))
    artifact = model.artifact()
    assert artifact['outcome_contract_ref'] == cached.CONTRACT_REF
    for row, target in zip(X, y):
        assert cached.execute(artifact, {n: bool(v) for n, v in zip(names, row)}, 0, True) == target
    assert model.predict([[False, False, True, False]], base=[0], eligible=np.array([True])).tolist() == [0]
