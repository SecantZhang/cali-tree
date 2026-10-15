from copy import deepcopy
import json

import pytest

from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import FEATURES,from_interpreted,synthetic_record,validate_record
from critical.core.calibration.semantic_hierarchy.interpreted_features_v6 import synthetic_record as interpreted_record
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import review,violations


def simple(n=12):
    X=[synthetic_record(meaning_available=True,meaning_progress_requested_endpoint_all=i%3==2,
                       meaning_progress_toward_requested_goal_all=i%3==1) for i in range(n)]
    y=[i%3 for i in range(n)];sources=[f's{i:03}' for i in range(n)]
    m=PortableSemanticTree().fit(X,y,source_groups=sources,source_batches=['g']*n)
    return X,y,m


def test_vocabulary_excludes_cardinality_majority_and_case_literals():
    assert not any('_count_ge_' in k or k.endswith('_majority') for k in FEATURES)
    assert 'requires_spatial_relation' in FEATURES
    with pytest.raises(ValueError):synthetic_record(case_id=True)
    with pytest.raises(ValueError):synthetic_record(outcome_all_count_ge_3=True)
    with pytest.raises(ValueError):synthetic_record(outcome_all_true_majority=True)


def test_projection_ignores_cardinality_changes_and_retains_semantic_kind():
    a=interpreted_record(outcome_spatial_relation_count_ge_1=True,outcome_spatial_relation_true_any=True)
    b=deepcopy(a);b['features'].update(outcome_spatial_relation_count_ge_2=True,outcome_spatial_relation_count_ge_3=True,
                                      outcome_spatial_relation_true_majority=True)
    assert from_interpreted(a)==from_interpreted(b)
    assert from_interpreted(a)['features']['requires_spatial_relation']


def test_deployment_policy_contains_no_fitting_records_or_source_ids():
    X,y,m=simple();executor=PortableRuleExecutor.from_training_policy(m.metadata());a=executor.metadata()
    encoded=json.dumps(a)
    assert all(s not in encoded for s in m.metadata()['training']['source_groups'])
    assert 'source_groups' not in encoded and 'instruction' not in a and 'training' not in a
    assert [r['prediction'] for r in executor.predict_records(X)]==y
    assert PortableRuleExecutor(json.loads(encoded)).predict_records(X)==executor.predict_records(X)


def test_runtime_rejects_rehashed_case_specific_conditions_or_label_inputs():
    X,_,m=simple();a=PortableRuleExecutor.from_training_policy(m.metadata()).metadata()
    a['tree']['feature']='source_image_hash'
    a['artifact_ref']=digest({k:v for k,v in a.items() if k!='artifact_ref'})
    with pytest.raises(ValueError):PortableRuleExecutor(a)
    bad=deepcopy(X[0]);bad['reference']=0
    with pytest.raises(ValueError):validate_record(bad)


def test_missing_record_stays_unresolved():
    _,_,m=simple();executor=PortableRuleExecutor.from_training_policy(m.metadata())
    assert executor.predict_records([None])[0]['prediction']==-1
    x=synthetic_record(meaning_available=False)
    assert executor.predict_records([x])[0]['reason']=='missing_semantic_interpretation'


@pytest.mark.parametrize('n',[12,24,48,96])
def test_portable_fit_and_restore_scale(n):
    X,y,m=simple(n)
    assert [r['prediction'] for r in PortableSemanticTree.restore(m.metadata()).predict_records(X)]==y


def review_fixture():
    # A generic subtype split creates a Yes exception despite a missing core
    # endpoint. Twenty-two other labels can still be fit when it is collapsed.
    y=[0]*6+[1]*4+[2]*14
    X=[]
    for i in range(24):
        X.append(synthetic_record(meaning_available=True,outcome_all_true_all=10<=i<22,outcome_all_true_any=6<=i<22,
            meaning_endpoint_gap_core_endpoint_missing_all=i in (0,1,22,23),requires_contact=i>=22))
    sources=[f's{i:03}' for i in range(24)]
    m=PortableSemanticTree().fit(X,y,source_groups=sources,source_batches=['g']*24);a=m.metadata()
    def leaf(ids):
        counts=[sum(y[i]==k for i in ids) for k in range(3)]
        return {'type':'leaf','prediction':max(range(3),key=lambda k:(counts[k],-k)),'support':len(ids),'counts':counts,
                'source_groups':[sources[i] for i in ids],'source_batches':{'g':len(ids)}}
    def branch(feature,yes,no):return {'type':'split','feature':feature,'true':yes,'false':no,'support':yes['support']+no['support']}
    inner=branch('requires_contact',leaf([22,23]),leaf([0,1]))
    core=branch('meaning_endpoint_gap_core_endpoint_missing_all',inner,leaf([2,3,4,5]))
    progress=branch('outcome_all_true_any',leaf([6,7,8,9]),core)
    a['tree']=branch('outcome_all_true_all',leaf(list(range(10,22))),progress)
    a.pop('artifact_ref');a['artifact_ref']=digest(a);PortableSemanticTree.restore(a)
    return X,y,a


def test_semantic_review_removes_a_subtype_exception_within_fit_floor():
    X,y,a=review_fixture();assert violations(a['tree'])
    reviewed,audit=review(a,X,y)
    assert not violations(reviewed['tree']) and audit['actions']
    assert reviewed['training']['metrics']['correct']==22
    assert reviewed['training']['metrics']['total']==24


def test_review_is_training_time_pruning_not_a_universal_runtime_gate():
    X,y,a=review_fixture();reviewed,_=review(a,X,y)
    x=deepcopy(X[10]);x['features']['meaning_endpoint_gap_core_endpoint_missing_all']=True
    # This field is not tested on the existing affirmative-outcome path.
    assert PortableRuleExecutor.from_training_policy(reviewed).predict_records([x])[0]['prediction']==2


def test_review_refuses_mismatched_training_inputs():
    X,y,a=review_fixture();changed=list(y);changed[0]=2
    with pytest.raises(ValueError):review(a,X,changed)
