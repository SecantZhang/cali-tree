import numpy as np

from critical.core.calibration.decision_flow_strength_v133 import flow,absence_witness,select
from critical.core.calibration.local_warranted_rubric_v97 import claims
from tests.unit.calitree.test_local_rubric_v94 import value
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft


def flags():
    v=value();v.update(target='uncertain',endpoint='absent',progress='none',collateral='none',collateral_affects_goal='no')
    return claims(bind_program('Move the bowl left',draft()),v)


def test_unknown_target_alone_is_not_failure_but_explicit_absence_and_no_progress_is_distinct():
    f=flags();assert absence_witness(f) and not f['local_no_ready']
    f['local_endpoint_absent']=False;assert not absence_witness(f)
    f=flags();f['local_single_requirement']=False;assert not absence_witness(f)


def test_strength_selection_uses_the_actual_guarded_original_decision():
    f=flags();f.update(local_endpoint_absent=False,local_any_uncertainty=False,local_progress_witness=False)
    # Every raw correction is inadmissible. Original retention is evaluated
    # after fallback, so it is preserved rather than vetoing unused scores.
    p=np.array([[.6,.3,.1]]);delta=np.array([[-.4,.1,.3]])
    pred,_,changed=flow(p,delta,2.,[f],[0],'strict')
    assert pred.tolist()==[0] and not changed.any()
    strength,trials=select(p,delta,[0],['source'],[f],[0],p,delta,[0],[f],[0],'strict')
    assert all(t['retained'] for t in trials) and strength==0.
