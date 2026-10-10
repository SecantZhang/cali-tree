"""Twelve-case identity, strict seed preparation and concurrent durable accounting."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from threading import Barrier,Lock
import time

from PIL import Image
import pytest
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import BudgetExhausted,CallFailure,ProviderStopped,CaseCalls
from critical.core.decision.concurrent_calls import ConcurrentDurableCalls
from critical.core.decision.compiler import object_schema,TEXT
from critical.core.decision.robust.construction import TypedEvidenceCompiler
from critical.core.decision.robust.models import export_program
from critical.core.optimization.program.robust.metrics import RobustPolicy
from critical.core.optimization.program.robust.demo import example_program
from run.calitree_typed_twelve import preflight,bridge_reference,execute,SOURCE,ARMS


def test_twelve_preflight_exact_identities_hashes_and_original_coverage(tmp_path):
    old=json.loads(SOURCE.read_text());m=preflight(tmp_path/'preflight')
    assert [r['id'] for r in m['cases']]==[r['id'] for r in old['cases']]
    assert len({r['group'] for r in m['cases']})==12 and m['max_calls']==3600 and m['reserve_calls']==960
    assert m['round_batches']==[1]*15 and m['scope_limits']=={'search':109,'final':40}
    for raw,row in zip(old['cases'],m['cases']):
        assert row['image_hashes']==raw['image_hashes']
        assert row['original']['program']['requirements']==raw['seed']['program']['requirements']
        assert row['original']['program']['outcomes']==raw['seed']['program']['outcomes']
        assert row['original']['program']['version']=='decision-leaf-v3' and raw['seed']['program']['version']=='decision-leaf-v2'
    assert preflight(tmp_path/'preflight')==m
    m['workers']=3;save_json(tmp_path/'preflight/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'preflight')


def test_concurrent_reservation_settlement_and_zero_call_replay(tmp_path):
    barrier=Barrier(2);lock=Lock();active=0;maximum=0;seen=[]
    class Engine:
        def generate(self,prompt,**kw):
            nonlocal active,maximum
            with lock:active+=1;maximum=max(maximum,active);seen.append(prompt)
            barrier.wait(timeout=3)
            with lock:active-=1
            return {'parsed':{'v':'ok'},'completionTokens':10,'promptTokens':20,'finishReason':'stop'}
    calls=ConcurrentDurableCalls(tmp_path,lambda cap:Engine(),identity={'model':'mock'},max_calls=3,
        reserve_calls=1,max_completion_tokens=10000,reserve_tokens=1024)
    def call(i):return calls.call('check',{'i':i},object_schema({'v':TEXT}),template='test',slot=str(i),max_tokens=1024,case_id=str(i))
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(call,[0,1]))
    assert maximum==2 and calls.budget['calls']==2 and calls.budget['completion_tokens_or_reserved']==20
    with pytest.raises(BudgetExhausted):call(2)
    assert [call(i) for i in [0,1]]==results and len(seen)==2
    assert len(calls.budget['attempted_slots'])==2


def test_global_failure_stop_and_failed_slot_accounting(tmp_path):
    hits=[]
    class Engine:
        def generate(self,*a,**k):hits.append(1);raise OSError('transport unavailable')
    calls=ConcurrentDurableCalls(tmp_path,lambda cap:Engine(),identity={'model':'mock'})
    def call(i):return calls.call('check',{'i':i},object_schema({'v':TEXT}),template='test',slot=str(i))
    for i in [0,1]:
        with pytest.raises(CallFailure):call(i)
    with pytest.raises(ProviderStopped):call(2)
    with pytest.raises(ProviderStopped):call(3)
    with pytest.raises(CallFailure):call(0)
    assert len(hits)==calls.budget['calls']==3 and calls.budget['completion_tokens_or_reserved']==6144


def test_fixed_two_support_schema_is_label_blind_and_rejects_bad_provider(tmp_path):
    seen=[];p=example_program()
    class Calls:
        directory=tmp_path
        def call(self,stage,payload,schema,**kw):
            seen.append((payload,schema,kw))
            return {'supports':[],'fulfillment_criteria':'explicit'},'unused'
    compiler=TypedEvidenceCompiler(Calls(),p,support_count=2)
    with pytest.raises(ValueError,match='required support count'):compiler.compile(p.instruction,p.rubric,slot='seed')
    payload,schema,kw=seen[0]
    assert 'reference_label' not in payload and 'feedback' not in payload and 'media' not in kw
    assert schema['properties']['supports']['minItems']==schema['properties']['supports']['maxItems']==2
    assert schema['properties']['supports']['items']['properties']['requirement_id']['enum']==['r']


def fake_manifest(tmp_path):
    cases=[];original=example_program()
    for i in range(2):
        evidence={}
        for key,color in [('source_image','blue'),('edited_image','red')]:
            p=tmp_path/f'{i}-{key}.png';Image.new('RGB',(8,8),color).save(p);evidence[key]=str(p)
        cases.append({'id':f'case-{i}','instruction':original.instruction,'rubric':original.rubric,
            'target':'partial','evidence':evidence,'group':str(i),'original':export_program(original)})
    return {'cases':cases,'arms':list(ARMS),'scope':'Synthetic two-case batch','model':'mock','provider':'mock',
        'temperature':0,'reasoning_effort':'none','policy':asdict(RobustPolicy()),'random_seed':42,'workers':2,
        'max_calls':600,'max_completion_tokens':768000,'reserve_calls':160,'reserve_tokens':163840,
        'scope_limits':{'search':109,'final':40}}


class Engine:
    def __init__(self,seen,bad_compile=False):self.seen,self.bad_compile=seen,bad_compile
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.seen.append((payload,kw))
        props=kw['schema']['properties']
        if 'supports' in props:
            value={'supports':[{'requirement_id':'r','question':'Is some red present?','criteria':'pass red; fail none; unknown unclear',
                'binding':'square','evidence_from':[]},{'requirement_id':'r','question':'Is the target visible?',
                'criteria':'pass target; fail none; unknown unclear','binding':'square','evidence_from':[]}],
                'fulfillment_criteria':'complete full red; partial known progress; absent none; unknown insufficient'}
            if self.bad_compile:value['supports']=[]
        elif 'accepted' in props:value={'accepted':True,'reason':'Synthetic faithful contract'}
        elif 'findings' in props:value={'findings':[]}
        elif 'text' in props:value={'text':'Investigate full requested extent, do not force a label'}
        elif 'transactions' in props:
            if payload['profile']=='criterion-only' or len(payload['program']['nodes'])==4:value={'transactions':[]}
            else:
                from tests.unit.calitree.test_typed_evidence import action,transaction
                value={'transactions':[transaction(action('insert_support',after='s2',before='fulfillment',new_check_id='extent',
                    requirement_id='r',question='Does red cover the square?',criteria='pass full; fail incomplete; unknown unclear',
                    binding='square',evidence_from=['s2'],readout_criteria='complete full red; partial progress with incomplete extent; absent none; unknown insufficient'))]}
        else:
            n=payload['node'];status='fail' if n['id']=='extent' else 'pass'
            if n['role']=='requested':status='partial'
            value={'status':status,'evidence':'Synthetic visible evidence','confidence':.99,'used_dependency_ids':n['dependencies']}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'mock-returned','finishReason':'stop'}


def test_parallel_batch_freezes_all_cases_before_finals_and_replays(tmp_path):
    m=fake_manifest(tmp_path);seen=[];out=tmp_path/'run';save_json(out/'manifest.json',m)
    result=execute(out,m,lambda cap:Engine(seen))
    assert result['status']=='completed' and len(result['cases'])==2
    assert all(r['support_status']=='locally_robust' for arms in result['cases'].values() for r in arms.values())
    n=len(seen);replayed=execute(out,m,lambda cap:Engine(seen));assert len(seen)==n and replayed['cases']==result['cases']
    jobs={p.stem:json.loads(p.read_text()) for p in (out/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in result['budget']['attempted_slots']];first=next(i for i,j in enumerate(ordered) if j['phase']=='final')
    assert all(j['phase']=='final' and j['stage']=='check' for j in ordered[first:])
    assert sum(j['case_id'].startswith('prepare/') for j in jobs.values())==4
    for payload,kw in seen:
        if not {'transactions','text'}&kw['schema']['properties'].keys():
            assert 'reference_label' not in payload and 'feedback' not in payload
    changed=deepcopy(m);changed['cases'][0]['target']='no'
    evaluated=execute(out,changed,lambda cap:Engine(seen));assert len(seen)==n
    assert all(r['final']['selected']['agreement']==0 for r in evaluated['cases']['case-0'].values())


def test_compiler_failures_remain_in_full_batch_denominator(tmp_path):
    m=fake_manifest(tmp_path);seen=[];out=tmp_path/'run'
    result=execute(out,m,lambda cap:Engine(seen,bad_compile=True))
    assert result['status']=='completed'
    assert all('error' in r and not r['final'] for arms in result['cases'].values() for r in arms.values())
    assert len(seen)==2 and all('supports' in kw['schema']['properties'] for _,kw in seen)
