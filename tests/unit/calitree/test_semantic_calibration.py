from copy import deepcopy
import numpy as np
import pytest

from critical.core.calibration import semantic_calibration as sc
from critical.core.decision.semantic_evidence import DESCRIPTORS


def descriptor(i):
    return [int(j == i) for j in range(len(DESCRIPTORS))]


def records():
    return [{'lower':[v]*8,'upper':[v]*8,'descriptor':descriptor(c)}
            for v in (0,2,4) for c in (0,1)]


def test_router_is_invariant_to_record_order_and_does_not_accept_labels():
    d=[descriptor(i) for i in (0,0,1,1,2,2)]
    a=sc.SemanticRouter().fit(d); b=sc.SemanticRouter().fit(list(reversed(d)))
    assert a.metadata()==b.metadata()
    assert a.predict(d)==sc.SemanticRouter.restore(a.metadata()).predict(d)
    with pytest.raises(TypeError): a.fit(d, [0]*len(d))
    with pytest.raises(ValueError): a.fit([{'instruction':'a case','reference':1}])


def test_cluster_offsets_share_coefficient_budget_and_require_multiple_sources():
    choices=list(sc.coefficients(3,[5,1,4],True))
    assert choices and any(o[2]!=0 for w,o in choices)
    assert all(o[1]==0 for w,o in choices)
    assert all(sum(v!=0 for v in w+o)<=4 and 1<=sum(w)<=6 for w,o in choices)
    assert all(not any(o) for w,o in sc.coefficients(3,[5,5,5],False))


def test_exact_fit_keeps_three_classes_monotone_and_unknown_unresolved():
    x=records(); y=[0,0,1,1,2,2]; router=sc.SemanticRouter().fit([r['descriptor'] for r in x])
    fit=sc.SemanticOrdinalCalibrator(router).fit(x,y,source_groups=list('abcdef'))
    assert [r['prediction'] for r in fit.predict_records(x)]==y
    assert fit.metadata()['active_coefficients']<=4
    unknown={'lower':[0]*8,'upper':[4]*8,'descriptor':None}
    assert fit.predict_records([unknown])[0]['prediction']==-1
    assert np.isnan(fit.predict([unknown])[0])
    restored=sc.SemanticOrdinalCalibrator.restore(fit.metadata())
    assert restored.predict_records(x)==fit.predict_records(x)
    points=[{'lower':[v]*8,'upper':[v]*8,'descriptor':descriptor(0)} for v in range(5)]
    p=[r['prediction'] for r in fit.predict_records(points)]
    assert p==sorted(p)
    damaged=deepcopy(fit.metadata()); damaged['weights'][0]=-1
    with pytest.raises(ValueError):sc.SemanticOrdinalCalibrator.restore(damaged)


def test_forbid_lookup_fields_and_collapsed_fit():
    x=records();router=sc.SemanticRouter().fit([r['descriptor'] for r in x])
    x[0]['id']='memorize'
    with pytest.raises(ValueError):sc.SemanticOrdinalCalibrator(router).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))
    unknown=[{'lower':[0]*8,'upper':[4]*8,'descriptor':None} for _ in range(6)]
    with pytest.raises(ValueError,match='No policy learns'):
        sc.SemanticOrdinalCalibrator(router).fit(unknown,[0,0,1,1,2,2],source_groups=list('abcdef'))
