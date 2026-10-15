from copy import deepcopy
import json

import pytest

from critical.core.decision.semantic_interpretation_v5 import FIELDS,make_input,schema,validate
from critical.core.calibration.semantic_hierarchy.interpreted_features_v6 import project,synthetic_record,validate_record
from critical.core.calibration.semantic_hierarchy.interpreted_tree_v6 import InterpretedSemanticTree
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation


def fixture():
    p=bind_program('Move the bowl left',draft());o=observation(p);payload=make_input(p,o,'pair')
    value={'evidence_ref':payload['evidence_ref'],'requirements':{r['id']:{**{k:v[0] for k,v in FIELDS.items()},
       'support_check_ids':['endpoint'],'explanation':'Interpretation fixture; no human labels.'} for r in payload['requirements']}}
    return p,o,payload,value


def test_payload_is_whitelisted_and_contains_no_label_or_image_fields():
    p,o,payload,value=fixture()
    assert set(payload)=={'instruction','authorized_changes','requirements','checks','evidence_ref'}
    assert 'reference_label' not in json.dumps(payload) and 'image_path' not in json.dumps(payload)
    assert schema(payload)['properties']['evidence_ref']['enum']==[payload['evidence_ref']]
    validate(payload,value)


@pytest.mark.parametrize('mutation',['binding','requirement','check','label','category'])
def test_interpretation_rejects_unbound_or_undeclared_content(mutation):
    _,_,payload,value=fixture();bad=deepcopy(value)
    if mutation=='binding':bad['evidence_ref']='wrong'
    elif mutation=='requirement':bad['requirements']['other']=bad['requirements'].pop('r1')
    elif mutation=='check':bad['requirements']['r1']['support_check_ids']=['not_a_check']
    elif mutation=='label':bad['human_label']=2
    else:bad['requirements']['r1']['progress']='Yes'
    with pytest.raises(ValueError):validate(payload,bad)


def test_semantic_categories_are_preserved_without_case_text():
    p,o,_,value=fixture();value['requirements']['r1'].update(progress='toward_requested_goal',endpoint_gap='core_endpoint_missing')
    x=project(p,o,'pair',value)
    assert x['features']['meaning_progress_toward_requested_goal_all']
    assert x['features']['meaning_endpoint_gap_core_endpoint_missing_any']
    assert 'bowl' not in json.dumps(x) and 'explanation' not in x


def test_missing_interpretation_preserves_physical_input_and_missing_observation_abstains():
    p,o,_,_=fixture();x=project(p,o,'pair',None)
    assert not x['features']['meaning_available'] and x['features']['outcome_all_true_any']
    assert project(None,None,'pair',None) is None


def test_frozen_inference_needs_no_labels_or_case_identifiers():
    X=[];y=[]
    for i in range(12):
        k=i%3;X.append(synthetic_record(meaning_available=True,
            meaning_progress_requested_endpoint_all=k==2,meaning_progress_toward_requested_goal_all=k==1));y.append(k)
    m=InterpretedSemanticTree().fit(X,y,source_groups=[str(i) for i in range(12)],source_batches=['a']*12)
    assert [r['prediction'] for r in m.predict_records(X)]==y
    restored=InterpretedSemanticTree.restore(json.loads(json.dumps(m.metadata())))
    assert restored.predict_records(X)==m.predict_records(X)
    bad=deepcopy(X[0]);bad['reference']=0
    with pytest.raises(ValueError):validate_record(bad)
