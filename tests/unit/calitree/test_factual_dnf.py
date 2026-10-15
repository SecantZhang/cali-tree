import json
from copy import deepcopy
import pytest
from critical.core.calibration.factual_dnf import ObservableDNFCalibrator,program_prediction
from tests.unit.calitree.test_factual_rules import row


def test_physical_witness_dnf_learns_without_quality_levels():
    x=[row(target_result_visible='false'),row(target_result_visible='false'),
       row(target_result_visible='true',requested_spatial_relation='false'),row(target_result_visible='true',requested_spatial_relation='false'),
       row(target_result_visible='true',requested_spatial_relation='true'),row(target_result_visible='true',requested_spatial_relation='true')]
    model=ObservableDNFCalibrator(('scope','relation')).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))
    assert [r['prediction'] for r in model.predict_records(x)]==[0,0,1,1,2,2]
    restored=ObservableDNFCalibrator.restore(json.loads(json.dumps(model.metadata())))
    assert restored.predict_records(x)==model.predict_records(x)
    assert all(n>=2 for counts in model.metadata()['clause_support'].values() for n in counts)
    x[4]['facts']['requested_spatial_relation']='unknown';assert model.predict_records([x[4]])[0]['prediction']==-1
    assert model.predict_records([None])[0]['prediction']==-1
    bad=deepcopy(model.metadata());bad['yes'][0][0]['fact']='grade'
    with pytest.raises(ValueError):ObservableDNFCalibrator.restore(bad)


def test_na_is_not_observed_contrary_and_positive_witness_does_not_reduce_label():
    yes=[[{'fact':'requested_spatial_relation','test':'true'}]]
    partial=[[{'fact':'target_result_visible','test':'true'}]]
    values=[]
    for state in ['false','true']:
        values.append(program_prediction(row(target_result_visible='true',requested_spatial_relation=state),yes,partial))
    assert values==[1,2]


def test_twelve_case_exact_objective_does_not_overflow_small_count_dtype():
    x=[row(target_result_visible='false') for _ in range(4)]
    x += [row(target_result_visible='true',requested_spatial_relation='false') for _ in range(4)]
    x += [row(target_result_visible='true',requested_spatial_relation='true') for _ in range(4)]
    y=[0]*4+[1]*4+[2]*4
    fit=ObservableDNFCalibrator().fit(x,y,source_groups=list(range(12)))
    assert [r['prediction'] for r in fit.predict_records(x)]==y
