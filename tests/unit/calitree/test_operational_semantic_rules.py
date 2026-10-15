from copy import deepcopy
import json
import pytest
from critical.core.calibration.operational_semantic_rules import ObservableDNFCalibrator
from critical.core.decision.physical_witness_program import compile_record,CORE,SUPPORT
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_bound_witnesses import program
from tests.unit.calitree.test_physical_witness_program import mid


def test_instruction_bound_physical_rules_learn_residual_attribute_condition():
    p=program();records=[]
    for _ in range(2):records.append(compile_record(row(requested_attribute_visible='false',contradictory_attribute_remains='true'),p,mid()))
    for _ in range(2):records.append(compile_record(row(requested_attribute_visible='true',contradictory_attribute_remains='true'),p,mid()))
    for _ in range(2):records.append(compile_record(row(requested_attribute_visible='true',contradictory_attribute_remains='false'),p,mid()))
    y=[0,0,1,1,2,2]
    fit=ObservableDNFCalibrator(('attribute','scope')).fit(records,y,source_groups=list('abcdef'))
    assert [r['prediction'] for r in fit.predict_records(records)]==y
    a=fit.metadata()
    for boundary,allowed in [('yes',CORE),('partial',SUPPORT)]:
        for clause in a[boundary]:assert any(v['test']=='true' and v['fact'] in allowed for v in clause)
    assert ObservableDNFCalibrator.restore(json.loads(json.dumps(a))).predict_records(records)==fit.predict_records(records)
    bad=deepcopy(records[0]);bad['human_label']='no'
    with pytest.raises(ValueError):fit.predict_records([bad])
    assert fit.predict_records([None])[0]['prediction']==-1


def test_positive_verdict_clause_without_requested_witness_is_rejected():
    from critical.core.calibration.operational_semantic_rules import VERSION,LIMITS,DIRECTIONS,PREDICATES
    a={'version':VERSION,'limits':LIMITS,'predicate_bank':PREDICATES,'directions':DIRECTIONS,
       'yes':[[{'fact':'unrequested_deformation_observed','test':'false'}]],
       'partial':[[{'fact':'unrequested_deformation_observed','test':'false'}]],
       'clause_support':{'yes':[2],'partial':[2]},'training_metrics':{'per_class':{k:{'correct':2} for k in ('no','partial','yes')}}}
    with pytest.raises(ValueError,match='requested physical witness'):ObservableDNFCalibrator.restore(a)
