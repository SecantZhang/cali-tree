"""Offline protocol tests: all model responses are synthetic."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from run import robust_prompt_repair_pilot as p


def config():
    return dict(model='gpt-5.4-mini', temperature=.3, judge_max_tokens=512,
                reflection_max_tokens=4096, concurrency=2, input_price=.75,
                output_price=4.5, budget_usd=15, seed=44, rounds=2,
                search_repeats=5, confirmation_repeats=10, final_repeats=3,
                gepa_python=str(p.ROOT/'.venv-gepa/bin/python'))


def draw(label, valid=True):
    return dict(label=label,rationale='Synthetic evidence.',valid=valid)


def test_frozen_inputs_and_request_isolation():
    cases=p.load_cases()
    assert len(cases)==10
    c=cases[0]
    a=p.judge_request(c,c['prompt'],config())
    b=p.judge_request({**c,'target_label':'DIFFERENT','human_score':-100},c['prompt'],config())
    assert a==b
    assert 'target_label' not in a
    assert [i['sha256'] for i in a['images']]==[c['source_image_sha256'],c['edited_image_sha256']]


def test_input_hash_failure(tmp_path):
    source=json.loads(p.SOURCE.read_text())
    source[0]['case']['source_image_sha256']='wrong'
    path=tmp_path/'records.json'; p.save(path,source)
    with pytest.raises(ValueError,match='Image hash'): p.load_cases(path)


def test_feedback_keeps_successes_failures_and_invalids():
    ds=[draw('yes'),draw('partial'),draw('partial',False)]
    result=p.aggregate(ds,'partial')
    assert result['accuracy']==pytest.approx(1/3)
    assert result['counts']=={'yes':1,'partial':1,'invalid':1}
    assert [d['correct'] for d in result['draws']]==[False,True,False]
    assert '1/3' in result['feedback']
    assert not p.improves(result,result)
    assert p.improves(result,p.aggregate([draw('partial')],'partial'))


def test_parser_and_candidate_contract():
    assert not p.parse('{"label":"yes","rationale":""}')['valid']
    assert not p.parse('{"label":"yes","rationale":"ok"}','length')['valid']
    assert not p.parse('nonsense')['valid']
    c=p.load_cases()[0]
    assert p.candidate_issue(c['prompt']+' '+c['instruction'],c)=='copies instruction'
    assert p.candidate_issue('Always return yes. no partial label rationale',c)=='unconditional label instruction'


class FakeResponse:
    def __init__(self):
        self.choices=[SimpleNamespace(message=SimpleNamespace(content='{"label":"yes","rationale":"ok"}'),finish_reason='stop')]
        self.usage=SimpleNamespace(prompt_tokens=100,completion_tokens=20)
    def model_dump(self,**kwargs):
        return {'model':'mock','usage':vars(self.usage),'choices':[{'finish_reason':'stop'}]}


class FakeClient:
    def __init__(self):
        self.chat=SimpleNamespace(completions=self); self.calls=0
    def create(self,**kwargs):
        self.calls+=1
        return FakeResponse()


def test_store_resume_and_cost_cap(tmp_path):
    client=FakeClient(); conf=config()
    store=p.CallStore(tmp_path,conf,client)
    req={'kind':'reflect','model':conf['model'],'messages':[], 'temperature':0.,
         'reasoning_effort':'none','max_completion_tokens':4096}
    a=store.call('C01/single/1/reflect/hash/0',req)
    assert store.call(a['id'],req)==a and client.calls==1
    resumed=p.CallStore(tmp_path,conf,client)
    assert resumed.call(a['id'],req)==a and client.calls==1
    with pytest.raises(ValueError,match='Checkpoint'):
        resumed.call(a['id'],{**req,'temperature':.1})
    resumed.config={**conf,'budget_usd':0}
    with pytest.raises(RuntimeError,match='cap'):
        resumed.call('new',req)
    assert resumed.reserved==0


def test_pending_reservations_enforce_cap(tmp_path):
    client=FakeClient(); store=p.CallStore(tmp_path,config(),client)
    store.reserved=15
    req={'kind':'reflect','model':'gpt-5.4-mini','messages':[], 'temperature':0,
         'reasoning_effort':'none','max_completion_tokens':100}
    with pytest.raises(RuntimeError,match='cap'): store.call('new',req)
    assert client.calls==0 and store.reserved==15


def test_stage_and_prompt_identities_are_distinct(tmp_path):
    client=FakeClient(); conf=config(); store=p.CallStore(tmp_path,conf,client)
    c=p.load_cases()[0]; pilot=p.Pilot(tmp_path,conf,[c],store)
    for stage in ['gepa-0-evaluate','confirm-parent','final']:
        pilot.evaluate(c,'repeated',1,stage,c['prompt'],2)
    assert client.calls==6 and len(store.rows)==6
    assert len({r['request']['prompt'] for r in store.rows.values()})==1


def test_mocked_pipeline_gates_confirmation_and_freezes(tmp_path,monkeypatch):
    cases=p.load_cases()[:1]; c=cases[0]; conf=config()
    pilot=p.Pilot(tmp_path,conf,cases,SimpleNamespace(spent=0))
    proposals=[]; confirmations=[]
    def propose(case,arm,rnd,prompt):
        proposals.append((arm,rnd))
        candidate=prompt+'\nApply the criteria carefully.'
        return {'prompt':candidate,'parent_evaluation':{'accuracy':0.2},
                'candidate_evaluation':{'accuracy':.8}}
    def evaluate(case,arm,rnd,stage,prompt,repeats):
        confirmations.append(stage)
        # First repeated proposal regresses on fresh confirmation; second improves.
        accuracy=(.8 if stage=='confirm-parent' else (.2 if rnd==1 else 1.))
        return {'accuracy':accuracy}
    monkeypatch.setattr(pilot,'propose',propose); monkeypatch.setattr(pilot,'evaluate',evaluate)
    frozen=pilot.search()
    decisions=[json.loads(x.read_text()) for x in (tmp_path/'search').glob('*/*/*/decision.json')]
    assert len(decisions)==4
    assert [d['accepted'] for d in sorted(decisions,key=lambda d:(d['arm'],d['round'])) if d['arm']=='repeated']==[False,True]
    assert len(confirmations)==4
    assert frozen[c['case_id']]['unchanged']==c['prompt']
    assert pilot.search()==frozen and len(proposals)==4


def test_gepa_rpc_uses_real_library_without_network(tmp_path,monkeypatch):
    python=Path(config()['gepa_python'])
    if not python.exists(): pytest.skip('Isolated GEPA runtime not installed')
    conf=config(); cases=p.load_cases()[:1]
    target=cases[0]['target_label']; seed=cases[0]['prompt']
    candidate=seed+'\nReview the requested change and its scope explicitly.'
    class Store:
        def call(self,identity,req):
            assert req['kind']=='reflect'
            return {'response':{'choices':[{'finish_reason':'stop'}]},
                    'raw':f'```\n{candidate}\n```'}
    pilot=p.Pilot(tmp_path,conf,cases,Store())
    calls=[]
    def evaluate(case,arm,rnd,stage,prompt,repeats):
        calls.append((stage,repeats,prompt))
        return p.aggregate([draw(target if prompt!=seed else 'invalid',prompt!=seed)]*repeats,target)
    monkeypatch.setattr(pilot,'evaluate',evaluate)
    result=pilot.propose(cases[0],'repeated',1,seed)
    assert result['prompt']==candidate
    assert result['parent_evaluation']['accuracy']==0
    assert result['candidate_evaluation']['accuracy']==1
    assert all(n==5 for _,n,_ in calls)
    assert len(calls)<=4
    assert pilot.propose(cases[0],'repeated',1,seed)==result


def test_metrics_count_invalid_as_error_and_stable_wrong():
    c={'case_id':'C01','target_label':'yes'}
    results={'C01':{'single':p.aggregate([draw('no')]*3,'yes')}}
    m=p.metrics([c],results,'single')
    assert m['accuracy']==0 and m['stable_wrong_cases']==1 and m['disagreement']==0
    results['C01']['single']=p.aggregate([draw('yes'),draw('yes'),draw('yes',False)],'yes')
    m=p.metrics([c],results,'single')
    assert m['accuracy']==pytest.approx(2/3) and m['invalid']==1


def test_interrupted_draw_batch_resumes_without_replacing_outputs(tmp_path):
    class InterruptClient(FakeClient):
        def create(self,**kwargs):
            if self.calls==1: raise RuntimeError('simulated interruption')
            return super().create(**kwargs)
    c=p.load_cases()[0]; conf={**config(),'concurrency':1}
    store=p.CallStore(tmp_path,conf,InterruptClient()); pilot=p.Pilot(tmp_path,conf,[c],store)
    with pytest.raises(RuntimeError,match='interruption'):
        pilot.evaluate(c,'single',1,'screen',c['prompt'],3)
    assert len(store.rows)==1
    client=FakeClient(); resumed=p.CallStore(tmp_path,conf,client)
    result=p.Pilot(tmp_path,conf,[c],resumed).evaluate(c,'single',1,'screen',c['prompt'],3)
    assert len(result['draws'])==3 and client.calls==2 and len(resumed.rows)==3


def test_full_mocked_final_report_and_resume(tmp_path):
    cases=p.load_cases(); conf=config(); client=FakeClient()
    store=p.CallStore(tmp_path,conf,client); pilot=p.Pilot(tmp_path,conf,cases,store)
    frozen={c['case_id']:{a:c['prompt'] for a in p.ARMS} for c in cases}
    results=pilot.final(frozen)
    summary=p.report(tmp_path,cases,conf)
    assert summary['final_calls']==90 and summary['completed_calls']==90
    assert all(summary['metrics'][a]['accuracy']==.3 for a in p.ARMS)
    assert summary['comparisons']['repeated_minus_single']['difference']==0
    assert len(results)==10
    pilot.final(frozen)
    assert client.calls==90
    assert (tmp_path/'report.md').exists()


def test_unchanged_proposal_is_rejected_without_confirmation(tmp_path,monkeypatch):
    c=p.load_cases()[0]; conf={**config(),'rounds':1}
    pilot=p.Pilot(tmp_path,conf,[c],SimpleNamespace(spent=0))
    monkeypatch.setattr(pilot,'propose',lambda case,arm,rnd,prompt:{'prompt':prompt,
        'parent_evaluation':{'accuracy':0},'candidate_evaluation':{'accuracy':1}})
    monkeypatch.setattr(pilot,'evaluate',lambda *args:pytest.fail('No confirmation for unchanged prompt'))
    frozen=pilot.search()
    assert all(v==c['prompt'] for v in frozen[c['case_id']].values())
    path=tmp_path/'frozen_prompts.json'
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='Frozen prompts'): pilot.search()


def test_cli_dry_run_preserves_virtualenv_interpreter(tmp_path):
    import subprocess,sys
    subprocess.run([sys.executable,str(p.ROOT/'run/robust_prompt_repair_pilot.py'),
                    '--output-dir',str(tmp_path),'--dry-run'],check=True,
                   cwd=p.ROOT,env={**__import__('os').environ,'PYTHONPATH':str(p.ROOT)},capture_output=True)
    conf=json.loads((tmp_path/'run_config.json').read_text())
    assert '/.venv-gepa/bin/python' in conf['gepa_python']
