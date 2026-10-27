import numpy as np

from critical.core.calibration.seeded_rubric_v73 import SeededRubric,Search
from critical.core.calibration.rubric_evidence_v73 import SPECS


def test_constant_mandatory_warrant_survives_guard_search():
    names=['rubric_partial_ready','intent_movement']
    X=[[1,1],[1,1],[1,1],[1,0],[1,0]];y=[1,1,1,0,0]
    model=SeededRubric(names,Search(mode='grades',max_guards=1)).fit(X,y,groups=list('abcde'),base=[0]*5,regular=[0]*5)
    assert model.predict(X,base=[0]*5,regular=[0]*5)==y
    assert all({'feature':'rubric_partial_ready','value':True} in r['conditions'] for r in model.rules)


def test_review_routes_to_an_independent_judge_without_inventing_a_grade():
    names=list(SPECS);X=np.zeros((5,len(names)),dtype=int)
    X[:,names.index('view_disagrees')]=1;X[:3,names.index('rubric_uncertainty_any')]=1
    model=SeededRubric(names,Search(mode='routes')).fit(X,[1,1,1,0,0],groups=list('abcde'),base=[0]*5,regular=[1]*5)
    assert model.rules and all(r['action']=='regular' for r in model.rules)
    assert model.predict(X,base=[0]*5,regular=[1]*5)==[1,1,1,0,0]
    assert model.predict(X[:1],base=[0],regular=[-1])==[0]


def test_actual_original_predictions_are_protected():
    X=[[1,1],[1,1],[1,1],[1,0],[1,0]];y=[1,1,1,0,0]
    model=SeededRubric(['rubric_partial_ready','intent_movement'],Search(mode='grades')).fit(
        X,y,groups=list('abcde'),base=[0]*5,regular=[0]*5,
        protected_X=[[1,1]],protected_y=[0],protected_base=[0],protected_regular=[0])
    assert model.predict([[1,1]],base=[0],regular=[0])==[0]


def test_repeated_editor_outputs_do_not_replace_source_support():
    X=[[1,1],[1,1],[1,1],[1,0]]
    model=SeededRubric(['rubric_partial_ready','intent_movement'],Search(mode='grades')).fit(
        X,[1,1,1,0],groups=['same']*4,base=[0]*4,regular=[0]*4)
    assert model.rules==[]
