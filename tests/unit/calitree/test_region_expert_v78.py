from copy import deepcopy

import pytest

from critical.core.calibration.region_expert_v78 import proposal,RegionProfile


def fixture():
    program={'program_ref':'bound','requirements':[{'source_quote':'Turn the red cylinder blue'}]}
    record={'program_ref':'bound','measurements':{'region_all_plans_bound':True,'region_all_requirements_supported':True,
        'source_detection_score':.8,'edited_detection_score':.8,'source_binding_margin':.2,'counterpart_margin':.2,'counterpart_similarity':.95,
        'color_edited_fraction':.9,'color_goal_delta':.8},'trace':[{'plan':{'kind':'attribute','property_probes':[{'family':'color'}]}}]}
    semantic={'meaning_identity_materiality_no_shortfall_all':True,'meaning_collateral_materiality_none_all':True}
    return program,record,semantic


def test_endpoint_requires_qualified_localized_change_and_preservation():
    p,r,s=fixture();assert proposal(p,r,s)['prediction']==2
    assert proposal(p,r,{})['prediction']==-1
    r['measurements']['color_goal_delta']=0
    assert proposal(p,r,s)['prediction']==-1


def test_material_shortfall_downgrades_endpoint_but_essential_loss_rejects():
    p,r,s=fixture();s['meaning_collateral_materiality_material_unrequested_change_any']=True
    assert proposal(p,r,s)['prediction']==1
    s.update(meaning_retention_need_same_instance_essential_all=True,meaning_identity_evidence_replacement_or_loss_all=True,meaning_identity_materiality_material_shortfall_all=True)
    assert proposal(p,r,s)['prediction']==0


def test_progress_is_distinct_from_endpoint_and_wrong_direction():
    p,r,s=fixture();r['measurements'].update(color_edited_fraction=.3,color_goal_delta=.2)
    assert proposal(p,r,s)['prediction']==1
    r['measurements'].update(color_edited_fraction=.05,color_goal_delta=-.1)
    assert proposal(p,r,s)['prediction']==0


def test_uncertain_binding_and_unsupported_scope_abstain():
    p,r,s=fixture();r['measurements']['counterpart_margin']=.001
    assert proposal(p,r,s)['prediction']==-1
    p,r,s=fixture();r['trace'].append(deepcopy(r['trace'][0]))
    assert proposal(p,r,s)['prediction']==-1
    p,r,s=fixture();r['measurements']['region_all_plans_bound']=False
    assert proposal(p,r,s)['prediction']==-1


def test_contract_and_profile_are_validated():
    p,r,s=fixture();r['program_ref']='other'
    with pytest.raises(ValueError,match='mismatch'):proposal(p,r,s)
    with pytest.raises(ValueError,match='profile'):RegionProfile('unqualified','anything')
