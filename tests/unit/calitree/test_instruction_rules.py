from copy import deepcopy
import json
import pytest
from critical.core.calibration.instruction_rules import InstructionRuleCalibrator,DEFAULT,GRID
from critical.core.decision.semantic_evidence import DESCRIPTORS,QUALITIES


def record(**grades):
    return {'contract':{k:k=='appearance' for k in DESCRIPTORS},
            'qualities':{k:{'applicable':True,'grade':grades.get(k,4)} for k in QUALITIES}}


def prediction(x,**thresholds):return InstructionRuleCalibrator({**DEFAULT,**thresholds}).predict_records([x])[0]['prediction']


def test_requested_identity_failure_cannot_be_compensated_by_scope():
    x=record(progress=3,scope=4,identity=1);x['contract']['identity_required']=True
    assert prediction(x)==1
    x['contract']['identity_required']=False;assert prediction(x)==2
    x['qualities']['identity']['grade']=0;x['contract']['identity_required']=True;assert prediction(x)==0
    for outcome in GRID['completed_outcome']:
        for fidelity in GRID['required_fidelity']:
            x['qualities']['identity']['grade']=2
            assert prediction(x,completed_outcome=outcome,required_fidelity=fidelity)!=2


@pytest.mark.parametrize('key,flag',[('relation','relation_required'),('quantity','quantity_required')])
def test_only_instruction_required_relation_and_count_gate_yes(key,flag):
    x=record(**{key:1});assert prediction(x)==2
    x['contract'][flag]=True;assert prediction(x)==1


def test_progress_does_not_replace_completed_endpoint_and_preservation_is_material():
    assert prediction(record(progress=4,endpoint=1,scope=4))==1
    assert prediction(record(preservation=2))==1
    assert prediction(record(preservation=0))==0
    x=record();x['contract'].update(appearance=False,replacement=True)
    assert prediction(x)==2 # authorized replacement itself is not a defect


def test_unknown_is_not_absence_and_contract_na_contradiction_is_unknown():
    x=record(identity=None);x['contract']['identity_required']=True;assert prediction(x)==-1
    x['contract']['identity_required']=False;assert prediction(x)==2
    x['contract']['identity_required']=True;x['qualities']['identity']={'applicable':False,'grade':4}
    assert prediction(x)==-1
    x['qualities']['progress']['grade']=0;assert prediction(x)==0
    assert prediction(None)==-1


def test_fit_serialization_and_predict_do_not_accept_lookup_fields():
    x=[record(progress=0),record(progress=0),record(endpoint=1),record(endpoint=1),record(),record()]
    y=[0,0,1,1,2,2];before=deepcopy(x)
    fit=InstructionRuleCalibrator().fit(x,y,source_groups=list('abcdef'))
    assert x==before and [r['prediction'] for r in fit.predict_records(x)]==y
    assert fit.metadata()['search']['candidates']==16
    assert InstructionRuleCalibrator.restore(json.loads(json.dumps(fit.metadata()))).predict_records(x)==fit.predict_records(x)
    frozen=fit.metadata();fit.predict_records(list(reversed(x)));assert fit.metadata()==frozen
    x[0]['case_id']='remember this'
    with pytest.raises(ValueError):fit.predict_records(x)
    bad=deepcopy(frozen);bad['thresholds']['required_fidelity']=2
    with pytest.raises(ValueError):InstructionRuleCalibrator.restore(bad)


def test_no_supported_fit_refuses_to_drop_required_checks():
    x=[record(progress=0),record(progress=0),record(endpoint=1),record(endpoint=1),record(identity=1),record(identity=1)]
    for r in x:r['contract']['identity_required']=True
    with pytest.raises(ValueError,match='semantic gates were not weakened'):
        InstructionRuleCalibrator().fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))


def test_required_grade_improvement_is_monotone():
    for key in QUALITIES:
        x=record();x['contract'].update(identity_required=True,relation_required=True,quantity_required=True)
        values=[]
        for v in range(5):
            x['qualities'][key]['grade']=v;values.append(prediction(x))
        assert values==sorted(values)
