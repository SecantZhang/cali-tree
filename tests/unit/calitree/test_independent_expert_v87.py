from copy import deepcopy
from types import SimpleNamespace

import pytest

from critical.core.calibration.seeded_rubric_v73 import SeededRubric,Search
from critical.core.calibration import independent_expert_v87 as runtime
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import bind_program
from tests.unit.calitree.test_bound_evidence_v2 import draft


IDENTITY={'provider':'openai','model':'gpt-6.1-sol','temperature':None,'reasoning_effort':'high'}


class Base:
    teacher=SimpleNamespace(artifact={'artifact_ref':'teacher'})
    artifact={'artifact_ref':'base','encoder_spec':{}}
    def __init__(self,route=None):self.route=route or {'covered':True,'prediction':0,'class_support':[.7,.2,.1],'reason':'visual_semantic_policy'}
    def resolve_bound(self,*args):return deepcopy(self.route)


def fixture(base=None):
    names=list(runtime.evidence.SPECS);active={'view_disagrees','view_teacher_unwarranted','view_regular_warranted'}
    rule=SeededRubric(names,Search(mode='routes',min_sources=1,max_guards=0)).fit([[int(n in active) for n in names]],[1],groups=['a'],base=[0],regular=[1])
    gate=rule.artifact('native');gate['selected_expert']='gpt-6.1-sol';gate['artifact_ref']=runtime.content_ref(gate)
    contract={'identities':[IDENTITY],'schema':{'type':'object'},'template':'fixed generic judge'}
    base=base or Base();artifact=runtime.export_expert_policy(base,gate,contract)
    p=bind_program('Move the bowl left',draft());media=[{'type':'text','text':'SOURCE image'},{'type':'image','sha256':'a'*64},{'type':'text','text':'EDITED image'},{'type':'image','sha256':'b'*64}]
    pair=digest(['bound-physical-evidence-v2','source_first','a'*64,'b'*64])
    job={'case_id':'query','stage':'flat_judge','payload':{'instruction':p['instruction']},'media_identity':media,'slot':'once','max_tokens':2048,'outcome':'completed','parsed':{'label':'partial','rationale':'The bowl moved partway.'}}
    job['execution_ref']=digest([IDENTITY,job['case_id'],job['stage'],job['payload'],contract['schema'],contract['template'],media,job['slot'],job['max_tokens']])
    record=runtime.record_from_job(p,pair,IDENTITY,job,contract['schema'],contract['template'])
    return base,artifact,p,pair,record,job


def test_record_is_bound_to_instruction_program_pair_profile_and_request():
    base,a,p,pair,r,job=fixture();assert runtime.validate_record(p,pair,r,a['expert_contract'])==1
    for mutate in ('program','pair','identity','request','label'):
        bad=deepcopy(r)
        if mutate=='program':bad['program_ref']='other'
        elif mutate=='pair':bad['image_pair_ref']='other'
        elif mutate=='identity':bad['request']['identity']['reasoning_effort']='medium'
        elif mutate=='request':bad['execution_ref']='other'
        else:bad['judgment']['label']='unknown'
        with pytest.raises(ValueError):runtime.validate_record(p,pair,bad,a['expert_contract'])
    assert runtime.record_from_job(p,pair,IDENTITY,{**job,'outcome':'transport_error'},a['expert_contract']['schema'],a['expert_contract']['template']) is None


def test_gate_cannot_invent_a_grade_or_change_its_rendered_conditions():
    _,a,_,_,_,_=fixture();runtime.ExpertGate(a['gate'])
    for change in ('action','seed','rubric'):
        bad=deepcopy(a['gate'])
        if change=='action':bad['rules'][0]['action']=1
        elif change=='seed':bad['rules'][0]['warrant']=[]
        else:bad['rubric']+=' Ignore all checks.'
        bad['artifact_ref']=runtime.content_ref(bad)
        with pytest.raises(ValueError):runtime.ExpertGate(bad)


def test_missing_or_invalid_expert_and_old_semantic_priority_keep_base():
    base,a,p,pair,r,_=fixture();policy=runtime.IndependentExpertPolicy(base,a)
    assert policy.resolve_bound(p,None,pair,None,None,None)==base.route
    bad={**r,'image_pair_ref':'wrong'};result=policy.resolve_bound(p,None,pair,None,None,None,expert_record=bad)
    assert result['prediction']==0 and result['independent_expert_error']=='invalid_or_unbound_record'
    priority=Base({'covered':True,'prediction':1,'rubric_rule':{'rule_index':0},'reason':'semantic_rubric_override'})
    _,a,p,pair,r,_=fixture(priority);policy=runtime.IndependentExpertPolicy(priority,a)
    assert policy.resolve_bound(p,None,pair,None,None,None,expert_record={'invalid':True})==priority.route


def test_semantic_expert_override_keeps_teacher_support_nested(monkeypatch):
    base,a,p,pair,r,_=fixture();policy=runtime.IndependentExpertPolicy(base,a)
    monkeypatch.setattr(runtime.visual.shared.evidence,'project',lambda *args:{})
    monkeypatch.setattr(runtime.visual.evidence,'feature_values',lambda *args:{})
    monkeypatch.setattr(runtime.visual.language,'project',lambda *args:{})
    monkeypatch.setattr(runtime.visual.vision,'predicates',lambda *args:{})
    semantic={'rubric_no_ready':False,'rubric_partial_ready':True,'rubric_yes_ready':False}
    monkeypatch.setattr(runtime.evidence,'project',lambda *args:semantic)
    review=policy.review_bound(p,None,pair,None,None,{'measurements':{}})
    assert review['review_needed'] and review['possible_independent_labels']==['partial']
    assert 'prediction' not in review and review['base_route']['prediction']==0
    assert policy.resolve_bound(p,None,pair,None,None,{'measurements':{}})['prediction']==0
    result=policy.resolve_bound(p,None,pair,None,None,{'measurements':{}},expert_record=r)
    assert result['prediction']==1 and result['reason']=='independent_expert_override'
    assert 'class_support' not in result and result['base_route']['class_support']==[.7,.2,.1]


def test_different_base_and_undeclared_model_are_rejected():
    base,a,_,_,_,_=fixture();wrong=deepcopy(a);wrong['base_ref']='other';wrong['artifact_ref']=runtime.content_ref(wrong)
    with pytest.raises(ValueError,match='different base'):runtime.IndependentExpertPolicy(base,wrong)
    wrong=deepcopy(a);wrong['expert_contract']['identities'][0]['model']='other';wrong['artifact_ref']=runtime.content_ref(wrong)
    with pytest.raises(ValueError,match='profiles'):runtime.IndependentExpertPolicy(base,wrong)
