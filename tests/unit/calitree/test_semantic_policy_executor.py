import pytest
from critical.core.calibration.policy_semantics import SemanticConditionPolicy
from critical.core.decision.semantic_policy_executor import prose_observations,interpreted_record,features
from tests.unit.calitree.test_policy_semantics import teacher
from tests.unit.calitree.test_semantic_evidence import observation


def test_prose_input_whitelist_removes_all_grades_and_keeps_factual_context():
    value=observation();prose=prose_observations(value)
    def keys(x):
        if isinstance(x,dict):
            for k,v in x.items():yield k;yield from keys(v)
        elif isinstance(x,list):
            for v in x:yield from keys(v)
    assert 'grade' not in set(keys(prose))
    assert prose['qualities']['progress']['evidence']==value['qualities']['progress']['evidence']
    assert prose['aspects'][0]['observed']==value['aspects'][0]['observed']
    assert set(prose)=={'contract','aspects','qualities'}


def test_interpreter_cannot_return_labels_or_scores_and_unknown_stays_interval():
    old,_=teacher();p=SemanticConditionPolicy.from_teacher(old.metadata())
    value={'states':{k:'unknown' for k in features(p)},'rationale':'Not enough observable evidence'}
    x=interpreted_record(p,value);assert p.predict_records([x])[0]['prediction']==-1
    value['label']='yes'
    with pytest.raises(ValueError):interpreted_record(p,value)
