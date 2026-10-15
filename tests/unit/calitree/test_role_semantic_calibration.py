from critical.core.calibration.role_semantic_rules import ObservableDNFCalibrator
from critical.core.decision.role_bound_witnesses import compile_record
from tests.unit.calitree.test_factual_rules import row
from tests.unit.calitree.test_physical_witness_program import mid


def program(require_attribute):
    return {'postconditions':[{'source_quote':'add the requested entity at the requested location',
        'physical_test':'The requested entity is recognizable at its destination, without a conflicting required appearance.',
        'required_present':['added_entity_recognizable','requested_spatial_relation'],
        'required_absent':['specified_entity_attribute_conflict'] if require_attribute else []}],
        'supporting_witnesses':[],
        'identity_witnesses':[],'collateral_witnesses':[]}


def test_same_observed_attribute_difference_has_different_requested_role():
    p=program(True);x=[]
    for _ in range(2):x.append(compile_record(row(added_entity_recognizable='true',requested_spatial_relation='true',specified_entity_attribute_conflict='true'),p,mid()))
    for _ in range(2):x.append(compile_record(row(added_entity_recognizable='true',requested_spatial_relation='false',specified_entity_attribute_conflict='false'),p,mid()))
    for _ in range(2):x.append(compile_record(row(added_entity_recognizable='true',requested_spatial_relation='true',specified_entity_attribute_conflict='false'),p,mid()))
    fit=ObservableDNFCalibrator(('attribute','relation')).fit(x,[0,0,1,1,2,2],source_groups=list('abcdef'))
    assert [r['prediction'] for r in fit.predict_records(x)]==[0,0,1,1,2,2]
    descriptive=compile_record(row(added_entity_recognizable='true',requested_spatial_relation='true',specified_entity_attribute_conflict='true'),program(False),mid())
    assert fit.predict_records([descriptive])[0]['prediction']==2
