from copy import deepcopy
from itertools import product
import json
import pytest

from critical.core.calibration.policy_semantics import SemanticConditionPolicy,semantic_record,frontier
from critical.core.calibration.semantic_calibration import SemanticRouter
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.decision.semantic_evidence import DESCRIPTORS


def teacher():
    x=[{'lower':[v]*8,'upper':[v]*8,'descriptor':[1]+[0]*(len(DESCRIPTORS)-1)} for v in (0,0,2,2,4,4)]
    router=SemanticRouter().fit([r['descriptor'] for r in x])
    return VisibilityOrdinalCalibrator(router).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef')),x


def test_minimal_semantic_frontier_for_progress_and_scope():
    w=[1,0,0,0,0,1,0,0]
    assert frontier(w,7)==[
        [{'feature':'progress','minimum_state':'near_complete'},{'feature':'scope','minimum_state':'complete'}],
        [{'feature':'progress','minimum_state':'complete'},{'feature':'scope','minimum_state':'near_complete'}]]


def test_semantic_execution_matches_teacher_without_scores_or_identifiers():
    old,x=teacher();new=SemanticConditionPolicy.from_teacher(old.metadata())
    assert [r['prediction'] for r in old.predict_records(x)]==[r['prediction'] for r in new.predict_records(map(semantic_record,x))]
    a=new.metadata();assert 'weights' not in a and 'cutpoints' not in a
    assert SemanticConditionPolicy.restore(json.loads(json.dumps(a))).predict_records(map(semantic_record,x))==new.predict_records(map(semantic_record,x))
    bad=semantic_record(x[0]);bad['case_id']='lookup'
    with pytest.raises(ValueError):new.predict_records([bad])
    bad=deepcopy(a);bad['yes'][0][0]['feature']='instruction'
    with pytest.raises(ValueError):SemanticConditionPolicy.restore(bad)


def test_unknown_and_missing_response_semantics_are_preserved():
    old,x=teacher();new=SemanticConditionPolicy.from_teacher(old.metadata())
    unknown={'lower':[0]*8,'upper':[4]*8,'descriptor':[1]+[0]*(len(DESCRIPTORS)-1)}
    missing={**unknown,'descriptor':None}
    for row in (unknown,missing):
        assert old.predict_records([row])[0]['prediction']==new.predict_records([semantic_record(row)])[0]['prediction']==-1


def test_uninspectability_branch_is_preserved_without_imputing_facts():
    old,x=teacher()
    for row in x[:2]:row['upper']=[4]*8
    old.fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'));new=SemanticConditionPolicy.from_teacher(old.metadata())
    assert old.metadata()['uninspectable_label']==0
    assert new.predict_records([semantic_record(x[0])])[0]['prediction']==0
    assert x[0]['upper']==[4]*8


def test_frontier_matches_weighted_boundary_over_full_four_feature_domain():
    weights=[3,1,0,1,0,1,0,0];cut=10;clauses=frontier(weights,cut)
    for values in product(range(5),repeat=4):
        grades=dict(zip(('progress','endpoint','relation','scope'),values))
        reference=3*values[0]+values[1]+values[2]+values[3]>=cut
        from critical.core.calibration.policy_semantics import STATES
        translated=any(all(grades[t['feature']]>=STATES[t['feature']].index(t['minimum_state']) for t in clause) for clause in clauses)
        assert translated==reference
