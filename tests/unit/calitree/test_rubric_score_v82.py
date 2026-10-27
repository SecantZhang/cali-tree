import numpy as np
import pytest

from critical.core.calibration.rubric_score_v82 import RubricScore,log_support


def test_protected_actual_decision_vetoes_every_nonzero_correction():
    X=np.ones((6,1));support=np.tile([.4,.3,.3],(6,1))
    model=RubricScore(['visible_progress'],regularization=.1).fit(X,[2]*6,support=support,groups=['a','a','b','b','c','c'],
        protected_X=np.ones((1,1)),protected_y=[0],protected_support=[[.334,.333,.333]])
    assert model.strength==0
    assert np.allclose(model.predict_proba(X,support=support),support)


def test_runtime_and_explicit_rubric_equation_agree_with_missing_values():
    X=np.asarray([[0.],[1.],[0.],[1.],[np.nan],[.8]])
    support=np.tile([.45,.4,.15],(6,1));y=[0,2,0,2,0,2]
    m=RubricScore(['endpoint_claim'],regularization=.01).fit(X,y,support=support,groups=list('abcdef'),
        protected_X=np.asarray([[0.],[1.]]),protected_y=[0,2],protected_support=[[.99,.005,.005],[.005,.005,.99]])
    a=m.artifact({'endpoint_claim':'The visible description claims the requested endpoint.'})
    logits=log_support(support);extra=np.tile(a['intercept_no_partial_yes'],(len(X),1))
    for term in a['terms']:
        values=np.where(np.isfinite(X[:,0]),X[:,0],term['mean'])
        extra+=np.clip((values-term['mean'])/term['scale'],-5,5)[:,None]*np.asarray(term['coefficients_no_partial_yes'])
    explicit=logits+a['strength']*((a['temperature']-1)*logits+extra)
    assert np.argmax(explicit,axis=1).tolist()==np.argmax(m.predict_proba(X,support=support),axis=1).tolist()


def test_invalid_teacher_support_is_never_called_confidence():
    for bad in ([[1,1,1]],[[float('nan'),0,1]],[[-1,1,1]],[[1,0]]):
        with pytest.raises(ValueError,match='supports'):log_support(bad)
