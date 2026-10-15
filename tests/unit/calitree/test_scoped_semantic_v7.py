from copy import deepcopy
import json

import pytest

from critical.core.calibration.semantic_hierarchy.interpreted_features_v6 import synthetic_record
from critical.core.calibration.semantic_hierarchy.interpreted_tree_v6 import InterpretedSemanticTree
from critical.core.calibration.semantic_hierarchy.scoped_policy_v7 import ScopedSemanticPolicy,mask_record
from critical.core.decision.artifacts import digest


def fixture(profile='physical_baseline'):
    rows=[]
    for i in range(18):
        label=i%3
        x=synthetic_record(outcome_attribute_count_ge_1=True,outcome_all_true_any=label>0,
            outcome_all_true_all=label==2,meaning_available=True,
            meaning_progress_requested_endpoint_all=label==2,meaning_progress_toward_requested_goal_all=label==1)
        rows.append({'features':x,'reference':label,'source_group':f's{i:02d}','batch':'g'})
    local=InterpretedSemanticTree().fit([mask_record(r['features'],profile) for r in rows],[r['reference'] for r in rows],
                source_groups=[r['source_group'] for r in rows],source_batches=['g']*len(rows))
    return rows,ScopedSemanticPolicy().fit(rows,local.metadata(),profile)


def test_scopes_preserve_every_fitting_prediction_and_restore():
    rows,m=fixture();ps=m.predict_records([r['features'] for r in rows])
    assert [p['prediction'] for p in ps]==[r['reference'] for r in rows]
    assert not any(p['fallback'] for p in ps)
    assert ScopedSemanticPolicy.restore(json.loads(json.dumps(m.metadata()))).predict_records([r['features'] for r in rows])==ps


def test_scope_not_most_favorable_label_selects_the_answer():
    rows,m=fixture();x=deepcopy(rows[0]['features'])
    x['features']['meaning_progress_requested_endpoint_all']=True
    a=m.predict_records([x])[0]
    assert a['prediction']==0 and not a['fallback']
    x['features']['outcome_attribute_count_ge_1']=False;x['features']['outcome_style_count_ge_1']=True
    b=m.predict_records([x])[0]
    assert b['fallback'] and b['prediction']==2 and b['local_prediction']==0


def test_missing_physical_or_required_interpretation_abstains():
    rows,m=fixture('meaning_depth5_support3');x=deepcopy(rows[0]['features']);x['features']['meaning_available']=False
    result=m.predict_records([None,x])
    assert [r['prediction'] for r in result]==[-1,-1]
    assert result[1]['reason']=='missing_semantic_interpretation'


def test_physical_policy_can_execute_without_interpretation_but_fallback_cannot():
    rows,m=fixture();x=deepcopy(rows[0]['features']);x['features']['meaning_available']=False
    assert m.predict_records([x])[0]['prediction']==0
    x['features']['outcome_attribute_count_ge_1']=False;x['features']['outcome_style_count_ge_1']=True
    assert m.predict_records([x])[0]['prediction']==-1


def test_new_labels_cannot_enter_prediction_record():
    rows,m=fixture();x=deepcopy(rows[0]['features']);x['human_label']=2
    with pytest.raises(ValueError):m.predict_records([x])


def test_rehashed_undeclared_scope_or_fallback_is_rejected():
    _,m=fixture();a=m.metadata();first=next(iter(a['scopes']))
    a['scopes'][first]['operation_scopes'][0]['kinds']=['case_123']
    a['artifact_ref']=digest({k:v for k,v in a.items() if k!='artifact_ref'})
    with pytest.raises(ValueError):ScopedSemanticPolicy.restore(a)
