from copy import deepcopy
import json
import pytest
from critical.core.calibration.semantic_calibration import SemanticRouter
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator,uninspectable
from critical.core.decision.semantic_evidence import DESCRIPTORS


def rows():
    d=[1]+[0]*(len(DESCRIPTORS)-1)
    return [{'lower':[v]*8,'upper':[v]*8,'descriptor':d} for v in (0,0,2,2,4,4)]


def test_learned_visibility_verdict_does_not_impute_facts_or_predict_transport_failure():
    x=rows()
    for r in x[:2]:r['upper']=[4]*8
    original=deepcopy(x);router=SemanticRouter().fit([r['descriptor'] for r in x])
    fit=VisibilityOrdinalCalibrator(router).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))
    assert x==original
    a=fit.metadata();assert a['uninspectable_label']==0 and a['active_coefficients']<=4
    assert a['uninspectable_correct_support']==2
    assert [r['prediction'] for r in fit.predict_records(x)]==[0,0,1,1,2,2]
    failed={'lower':[0]*8,'upper':[4]*8,'descriptor':None}
    assert not uninspectable(failed)
    assert fit.predict_records([failed])[0]['prediction']==-1
    restored=VisibilityOrdinalCalibrator.restore(json.loads(json.dumps(a)))
    assert restored.predict_records(x)==fit.predict_records(x)
    bad=deepcopy(a);bad['uninspectable_correct_support']=1
    with pytest.raises(ValueError):VisibilityOrdinalCalibrator.restore(bad)


def test_single_unknown_fact_is_not_the_visibility_branch():
    x=rows();x[0]['upper'][0]=4
    assert not uninspectable(x[0])
    x[0]['upper'][1]=4;assert uninspectable(x[0])
