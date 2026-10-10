from copy import deepcopy
import json

import pytest

from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls,CaseCalls,RoutedCalls
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.program.robust.typed import create_typed_evidence_optimizer
from critical.lm_engine import get_engine,openai_compat
from critical.lm_engine.creds import ProviderCreds
from run.calitree_sol_proposer import preflight,execute,ARMS,PRIMARY,SOL,SOURCE,INDICES
from tests.unit.calitree.test_typed_twelve import fake_manifest,Engine


def test_sol_wire_reasoning_and_sampling(monkeypatch):
    seen=[]
    class Response:
        status_code=200;headers={}
        def json(self):return {'model':'gpt-6.1-sol','choices':[{'message':{'content':'{}'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':20,'completion_tokens':30,'total_tokens':50}}
    def post(url,**kw):seen.append((url,kw));return Response()
    monkeypatch.setattr(openai_compat.requests,'post',post)
    result=openai_compat.chat_completion(endpoints=['https://api.openai.com/v1'],token='test-key',model='gpt-6.1-sol',
        messages=[{'role':'user','content':'test'}],temperature=None,reasoning_effort='medium',max_http_attempts=1)
    payload=seen[0][1]['json']
    assert payload['reasoning_effort']=='medium' and 'temperature' not in payload
    assert seen[0][1]['allow_redirects'] is False and len(seen)==1 and result.completion_tokens==30
    with pytest.raises(ValueError,match='temperature=None'):
        openai_compat.chat_completion(endpoints=['https://api.openai.com/v1'],token='test-key',model='gpt-6.1-sol',
            messages=[],temperature=0,reasoning_effort='medium',max_http_attempts=1)
    with pytest.raises(ValueError,match='enabled reasoning'):
        openai_compat.chat_completion(endpoints=['https://api.openai.com/v1'],token='test-key',model='gpt-6.1-sol',
            messages=[],temperature=None,reasoning_effort='none',max_http_attempts=1)
    assert len(seen)==1


def test_engine_forwards_explicit_reasoning_without_changing_legacy(monkeypatch):
    seen=[]
    def completion(**kw):
        seen.append(kw)
        return openai_compat.ChatResult('{}',1,2,3,'api.openai.com',.1,kw['model'],'stop')
    monkeypatch.setattr(openai_compat,'chat_completion',completion)
    creds=ProviderCreds(token='test',base_url='https://api.openai.com/v1',provider='openai')
    get_engine('gpt',model='gpt-6.1-sol',creds=creds,temperature=None,reasoning_effort='medium').generate('test')
    get_engine('gpt',model='gpt-6-luna',creds=creds,temperature=0).generate('test')
    assert seen[0]['reasoning_effort']=='medium' and seen[0]['temperature'] is None
    assert 'reasoning_effort' not in seen[1] and seen[1]['temperature']==0


def test_frozen_three_case_preflight_preserves_saved_seeds(tmp_path):
    m=preflight(tmp_path/'run');source=json.loads((SOURCE/'manifest.json').read_text())
    assert [c['id'] for c in m['cases']]==[source['cases'][i]['id'] for i in INDICES]
    for c,i in zip(m['cases'],INDICES):
        assert c['seed']==json.loads((SOURCE/'prepared'/f'{i}.json').read_text())['seed']
    assert m['primary_identity']==PRIMARY and m['routes']['sol-proposer']==SOL
    assert m['proposal_max_tokens']==4096 and m['reserve_calls']==240 and m['max_rounds']==15
    assert m['historical_feedback_or_observations_reused'] is False
    assert preflight(tmp_path/'run')==m
    m['routes']['sol-proposer']['reasoning_effort']='high';save_json(tmp_path/'run/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'run')


def test_proposer_must_share_scope_and_budget(tmp_path):
    calls=DurableCalls(tmp_path,lambda _:None,identity=PRIMARY,
        routes={'sol':{'identity':SOL,'engine_factory':lambda _:None}})
    primary=CaseCalls(calls,'case')
    opt=create_typed_evidence_optimizer(primary,example_program(),proposer_calls=RoutedCalls(primary,'sol'),proposal_max_tokens=4096)
    assert opt.proposer.calls.identity==SOL and opt.compiler.calls is primary and opt.gradient.calls is primary
    with pytest.raises(ValueError,match='case scope'):
        create_typed_evidence_optimizer(primary,example_program(),proposer_calls=RoutedCalls(CaseCalls(calls,'other'),'sol'))


def test_proposer_only_route_finals_and_zero_call_resume(tmp_path):
    m=fake_manifest(tmp_path);m.update(arms=list(ARMS),primary_identity=PRIMARY,routes={'sol-proposer':SOL},
        profile='nested-required',max_rounds=15,proposal_max_tokens=4096)
    from critical.core.decision.robust.construction import construct_ordered_program
    from critical.core.decision.robust.models import export_program
    specification={'supports':[
        {'requirement_id':'r','question':'Is some red present?','criteria':'pass red; fail none; unknown unclear','binding':'square','evidence_from':[]},
        {'requirement_id':'r','question':'Is the requested target visible?','criteria':'pass visible; fail missing; unknown unclear','binding':'square','evidence_from':[]}],
        'fulfillment_criteria':'complete full red; partial progress; absent none; unknown unresolved'}
    seed,_=construct_ordered_program(example_program(),specification)
    for c in m['cases']:c['seed']=export_program(seed)
    primary_seen=[];proposal_seen=[];out=tmp_path/'run';save_json(out/'manifest.json',m)
    results=execute(out,m,lambda _:Engine(primary_seen),lambda _:Engine(proposal_seen))
    assert results['status']=='completed' and proposal_seen
    assert all('transactions' in kw['schema']['properties'] for _,kw in proposal_seen)
    assert all(row['support_status']=='locally_robust' for arms in results['cases'].values() for row in arms.values())
    jobs={p.stem:json.loads(p.read_text()) for p in (out/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in results['budget']['attempted_slots']]
    for j in ordered:
        if j.get('route'):
            assert j['route']=='sol-proposer' and j['stage']=='propose_typed' and j['case_id'].startswith('sol-proposer/')
            assert j['requested_identity']==SOL and j['max_tokens']==4096
        if j['stage'] in ('check','audit'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload'] and 'route' not in j
    first=next(i for i,j in enumerate(ordered) if j['phase']=='final')
    assert all(j['phase']=='final' and j['stage']=='check' for j in ordered[first:])
    n=(len(primary_seen),len(proposal_seen));replayed=execute(out,m,lambda _:Engine(primary_seen),lambda _:Engine(proposal_seen))
    assert n==(len(primary_seen),len(proposal_seen)) and replayed['cases']==results['cases']
