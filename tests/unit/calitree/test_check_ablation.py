"""Offline controls for the paired visual execution-format experiment."""
from copy import deepcopy
import json
import pytest

from critical.core.decision.ablation import (make_bank, execute_draw, aggregate_observations,
    draw_metrics, paired_sign_flip, inconsistency)
from critical.core.decision.artifacts import export_program
from critical.core.decision.calls import DurableCalls, CaseCalls
from critical.core.optimization.program.demo import seed_program, demo_case
from run.calitree_check_ablation import execute, summarize


def graph():
    return {'representable':True,'reason':'Color evidence preserves the instruction',
        'facts':[{'id':key,'question':question,'present_when':'The specified color is visible',
            'absent_when':'The specified color is not visible','unknown_when':'The square cannot be seen'}
            for key,question in [('red','Is the square red?'),('blue','Is blue still visible on the square?')]],
        'decisions':[{'outcome_id':'o1','fact_ids':['red','blue'],
            'complete_when':'red present and blue absent','partial_when':'red present and blue present',
            'absent_when':'red absent','unknown_when':'red or blue unknown'}]}


class Engine:
    def __init__(self, reject=False, interrupt=False):
        self.requests=[];self.reject=reject;self.interrupt=interrupt
    def generate(self,prompt,**kwargs):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.requests.append((payload,kwargs))
        facts={'red':{'status':'present','evidence':'Red square visible'},'blue':{'status':'absent','evidence':'No remaining blue'}}
        outcomes={'o1':{'status':'complete','evidence':'Red present, blue absent'}}
        if 'max_facts' in payload:value=graph()
        elif 'seed' in payload:value={'accepted':not self.reject,'reason':'Semantic audit'}
        elif 'fact' in payload:
            if self.interrupt:
                self.interrupt=False;raise KeyboardInterrupt('Simulated interrupted atomic slot')
            value=facts[payload['fact']['id']]
        elif 'facts' in payload:value={'outcomes':outcomes}
        else:value={'facts':facts,'outcomes':outcomes}
        return {'parsed':value,'model':'gpt-6-luna','completionTokens':12,'promptTokens':50,'finishReason':'stop'}


def manifest(case):
    return {'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','repeats':5,
        'max_calls':400,'max_completion_tokens':409600,'reserve_calls':300,'reserve_tokens':307200,
        'scope':'offline test','cases':[{'id':case.id,'instruction':case.instruction,'target':'yes',
           'seed':export_program(seed_program()),'evidence':case.evidence}]}


def test_paired_runner_identical_criteria_label_isolation_and_resume(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);engine=Engine();output=tmp_path/'run'
    result=execute(output,m,lambda _:engine)
    assert result['status']=='completed'
    assert len(engine.requests)==22 # compilation + audit + five (one + three) paired draws
    rows=summarize(result,m)['arms']
    assert [r['calls'] for r in rows]==[5,15]
    assert all(r['agreement']==r['coverage']==1 and r['fully_consistent']==1 for r in rows)
    assert all(r['pairwise_inconsistency']==r['atomic_inconsistency']==0 for r in rows)
    banks=[]
    for payload,kwargs in engine.requests:
        assert 'reference_label' not in payload and 'target_label' not in payload and 'feedback' not in payload
        if 'bank' in payload and 'seed' not in payload:banks.append(payload['bank'])
        if 'facts' in payload:assert kwargs['media_inputs']==[]
        elif 'fact' in payload:
            assert len(kwargs['media_inputs'])==4 and 'decisions' not in payload and 'outcomes' not in payload
    assert all(bank==banks[0] for bank in banks)
    before=len(engine.requests);budget=(output/'budget.json').read_bytes()
    assert execute(output,m,lambda _:engine)==result
    assert len(engine.requests)==before and (output/'budget.json').read_bytes()==budget
    # Evaluation labels may change only metrics, never observations or model requests.
    changed=deepcopy(m);changed['cases'][0]['target']='no'
    again=execute(output,changed,lambda _:engine)
    assert again==result and len(engine.requests)==before
    assert all(r['agreement']==0 for r in summarize(again,changed)['arms'])


@pytest.mark.parametrize('arm',['combined','separated'])
def test_unknown_propagation_and_negative_fact_evidence(tmp_path,arm):
    bank=make_bank(seed_program(),graph());case=demo_case(tmp_path/'images');engine=Engine()
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:engine,identity={'model':'gpt-6-luna'}),arm)
    row=execute_draw(calls,bank,case.evidence,arm,0)
    assert row['facts']['blue']['status']=='absent' and row['label']=='yes'
    row['facts']['blue']['status']='unknown'
    assert aggregate_observations(bank,row['facts'],row['outcomes']) is None


@pytest.mark.parametrize('mutation', ['missing_outcome','extra_fact','unknown_reference','compound_type','unrepresentable'])
def test_invalid_bank_rejected(mutation):
    value=graph()
    if mutation=='missing_outcome':value['decisions']=[]
    elif mutation=='extra_fact':value['facts']*=2
    elif mutation=='unknown_reference':value['decisions'][0]['fact_ids']=['missing']
    elif mutation=='compound_type':value['facts'][0]['question']=['red','blue']
    else:value['representable']=False
    with pytest.raises(ValueError):make_bank(seed_program(),value)


def test_audit_rejection_preserved_as_unresolved_without_image_checks(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);engine=Engine(reject=True)
    result=execute(tmp_path/'run',m,lambda _:engine)
    assert result['status']=='completed' and len(engine.requests)==2
    metrics=summarize(result,m)
    assert all(r['agreement']==r['coverage']==r['calls']==0 for r in metrics['arms'])
    assert metrics['paired_inconsistency_separated_minus_combined']['cases']==0


def test_interrupted_slot_never_resampled(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);engine=Engine(interrupt=True);root=tmp_path/'run'
    with pytest.raises(KeyboardInterrupt):execute(root,m,lambda _:engine)
    result=execute(root,m,lambda _:engine)
    assert result['status']=='completed' and len(engine.requests)==22
    assert result['cases'][case.id]['draws']['separated'][0]['label'] is None
    jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
    assert sum(j['outcome']=='interrupted' for j in jobs)==1
    before=len(engine.requests);assert execute(root,m,lambda _:engine)==result
    assert len(engine.requests)==before


def test_case_level_stability_and_exact_sign_flip():
    assert inconsistency(['yes']*5)==0
    assert inconsistency([None]*5)==1
    assert inconsistency(['yes']*4+['no'])==0.4
    assert paired_sign_flip([0,0])['p_value']==1
    assert paired_sign_flip([-1]*4)=={'cases':4,'mean_difference':-1,'p_value':0.125}
    draws=[{'label':'yes','facts':{'f':{'status':'present'}},'errors':[]} for _ in range(5)]
    metrics=draw_metrics(draws,'no')
    assert metrics['independent_cases']==1 and metrics['repeats']==5
    assert metrics['all_resolved_consistent'] and not metrics['all_matching']


def test_empty_explanatory_reason_is_valid_but_empty_criteria_are_not():
    value=graph();value['reason']=''
    assert make_bank(seed_program(),value)['reason']==''
    value['facts'][0]['question']=''
    with pytest.raises(ValueError):make_bank(seed_program(),value)


def test_one_label_blind_semantic_repair_is_bounded_and_unchanged_audit_reused(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);m['preparation_repair_once']=True
    engine=Engine(reject=True)
    result=execute(tmp_path/'run',m,lambda _:engine)
    assert result['status']=='completed' and len(engine.requests)==3
    record=result['cases'][case.id]['preparation']
    assert record['status']=='audit_rejected' and record['initial_attempt']['status']=='audit_rejected'
    proposal=next(p for p,_ in engine.requests if 'preparation_diagnostics' in p)
    assert 'reference_label' not in proposal and 'target' not in proposal


def test_repaired_bank_is_audited_and_frozen_for_both_arms(tmp_path):
    class RepairEngine(Engine):
        def generate(self,prompt,**kwargs):
            response=super().generate(prompt,**kwargs)
            payload=json.loads(prompt.split('INPUT_JSON: ',1)[1])
            if 'preparation_diagnostics' in payload:
                response['parsed']['facts'][0]['question']='Is red visible on the intended square?'
            elif 'seed' in payload and 'bank' in payload:
                response['parsed']['accepted']=payload['bank']['facts'][0]['question'].startswith('Is red visible')
            return response
    case=demo_case(tmp_path/'images');m=manifest(case);m['preparation_repair_once']=True;engine=RepairEngine()
    result=execute(tmp_path/'run',m,lambda _:engine)
    row=result['cases'][case.id]
    assert row['preparation']['status']=='ready' and len(engine.requests)==24
    assert len({draw['bank_ref'] for arm in row['draws'].values() for draw in arm})==1
