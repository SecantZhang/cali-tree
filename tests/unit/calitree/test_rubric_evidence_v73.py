from copy import deepcopy

import pytest

from critical.core.calibration import rubric_evidence_v73 as evidence
from critical.core.decision.bound_evidence_v2 import bind_program
from critical.core.decision.semantic_interpretation_v5 import make_input
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_bound_evidence import observation
from tests.unit.calitree.test_semantic_stability_audit_v14 import requirement


def interpreted(p, o, rows):
    payload=make_input(p,o,'pair')
    return {'evidence_ref':payload['evidence_ref'],'requirements':{
        key:{**row,'support_check_ids':[next(c['id'] for c in p['checks'] if c['role']=='outcome' and key in c['requirement_ids'])],
             'explanation':'Instruction-bound physical evidence.'} for key,row in rows.items()}}


def test_ready_yes_has_coherent_endpoint_identity_and_collateral_evidence():
    p=bind_program('Change the target',draft('Change the target',kind='attribute'));o=observation(p)
    value=evidence.project(p,o,'pair',interpreted(p,o,{'r1':requirement()}))
    assert value['rubric_yes_ready'] and not value['rubric_no_ready'] and not value['rubric_partial_ready']


def test_different_requirements_cannot_supply_each_others_endpoint_and_collateral():
    d=draft('Change both targets',kind='attribute')
    second=deepcopy(d['requirements'][0]);second.update(id='r2',description='The second requested target')
    check=deepcopy(d['checks'][0]);check.update(id='endpoint2',requirement_ids=['r2'],question='Is the second target changed?',target='the second target')
    d['requirements'].append(second);d['checks'].append(check)
    p=bind_program('Change both targets',d);o=observation(p)
    a=requirement();b={**requirement('toward_requested_goal','core_endpoint_missing'),'collateral_materiality':'material_unrequested_change'}
    value=evidence.project(p,o,'pair',interpreted(p,o,{'r1':a,'r2':b}))
    assert value['rubric_partial_ready'] and not value['rubric_yes_ready']
    assert not value['rubric_material_collateral_with_endpoint_any']


def test_judge_support_is_a_view_cue_not_an_image_truth_oracle():
    semantic=dict.fromkeys(evidence.SEMANTIC,False);semantic['rubric_partial_ready']=True
    flags=evidence.views(semantic,[.6,.3,.1],1)
    assert flags['view_disagrees'] and flags['view_regular_warranted'] and flags['view_teacher_unwarranted']
    assert flags['view_top_support_lt_0.65']
    with pytest.raises(ValueError,match='normalized'):
        evidence.views(semantic,[.9,.9,.1],1)


def test_missing_interpretation_stays_unavailable():
    assert evidence.project(None,None,None,None) is None


def test_unknown_physical_endpoint_cannot_become_an_established_yes():
    p=bind_program('Change the target',draft('Change the target',kind='attribute'));o=observation(p,endpoint='unknown')
    value=evidence.project(p,o,'pair',interpreted(p,o,{'r1':requirement()}))
    assert not value['rubric_yes_ready'] and value['rubric_outcome_unknown_any']


def test_conflicting_duplicate_witnesses_become_unknown_instead_of_voting():
    d=draft('Change the target',kind='attribute');duplicate=deepcopy(d['checks'][0]);duplicate['id']='copy'
    d['checks'].append(duplicate);p=bind_program('Change the target',d);o=observation(p,copy='false')
    value=evidence.project(p,o,'pair',interpreted(p,o,{'r1':requirement()}))
    assert value['rubric_duplicate_conflict_any'] and value['rubric_outcome_unknown_any']
    assert not value['rubric_yes_ready']


def test_uncertain_outcome_is_not_an_explicit_failure_witness():
    p=bind_program('Change the target',draft('Change the target',kind='attribute'));o=observation(p,endpoint='unknown')
    value=evidence.project(p,o,'pair',interpreted(p,o,{'r1':requirement('none','uncertain')}))
    assert not value['rubric_no_ready'] and value['rubric_uncertainty_any']
