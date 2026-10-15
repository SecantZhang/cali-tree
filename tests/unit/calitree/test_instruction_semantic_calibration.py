import json
from critical.core.calibration.instruction_semantic_rules import ObservableDNFCalibrator
from critical.core.decision.instruction_role_facts import compile_record,CORE,SUPPORT
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_physical_witness_program import mid


def program(relocation=True):
    return {'postconditions':[{'source_quote':'requested placement','physical_test':'The intended counterpart is at the requested relative position',
        'required_present':['requested_spatial_relation','counterpart_at_destination'],'required_absent':[]}],
        'supporting_witnesses':['requested_direction_change'],
        'identity_witnesses':['original_instance_displaced'] if relocation else [],'collateral_witnesses':[]}


def test_actual_calibration_distinguishes_relocation_duplication_from_authorized_addition():
    p=program();x=[]
    for _ in range(2):x.append(compile_record(row(requested_spatial_relation='false',counterpart_at_destination='false',target_instance_count_increased='false'),p,mid()))
    for _ in range(2):x.append(compile_record(row(requested_spatial_relation='true',counterpart_at_destination='true',target_instance_count_increased='true'),p,mid()))
    for _ in range(2):x.append(compile_record(row(requested_spatial_relation='true',counterpart_at_destination='true',target_instance_count_increased='false'),p,mid()))
    fit=ObservableDNFCalibrator(('relation','identity')).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))
    assert [r['prediction'] for r in fit.predict_records(x)]==[0,0,1,1,2,2]
    addition=compile_record(row(requested_spatial_relation='true',counterpart_at_destination='true',target_instance_count_increased='true'),program(False),mid())
    assert fit.predict_records([addition])[0]['prediction']==2
    assert ObservableDNFCalibrator.restore(json.loads(json.dumps(fit.metadata()))).predict_records(x)==fit.predict_records(x)
    for boundary,allowed in [('yes',CORE),('partial',SUPPORT)]:
        assert all(any(a['test']=='true' and a['fact'] in allowed for a in clause) for clause in fit.metadata()[boundary])


def test_no_positive_verdict_without_a_requested_physical_witness():
    from critical.core.calibration.instruction_semantic_rules import PREDICATES,program_prediction
    facts={k:'false' for k in PREDICATES}
    facts['source_subject_layout_retained']='true';facts['target_result_visible']='true'
    yes=[[{'fact':'all_bound_postconditions_established','test':'true'},{'fact':'relocation_duplicate_observed','test':'false'}]]
    partial=[[{'fact':'a_required_positive_witness_visible','test':'true'}],[{'fact':'instruction_related_intermediate_witness','test':'true'}]]
    assert program_prediction({'facts':facts},yes,partial)==0
    facts['instruction_related_intermediate_witness']='true'
    assert program_prediction({'facts':facts},yes,partial)==1
    facts['all_bound_postconditions_established']='true'
    assert program_prediction({'facts':facts},yes,partial)==2
    facts['relocation_duplicate_observed']='true'
    assert program_prediction({'facts':facts},yes,partial)==1
