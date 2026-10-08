import json

import pytest

from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CallFailure, ProviderStopped
from run.calitree_resume_frozen import prepare, fingerprint


def stopped_run(tmp_path):
    source=tmp_path/'source'
    save_json(source/'manifest.json',{'model':'gpt-6-luna','provider':'openai',
        'cases':[{'id':'case'}],'arms':['broad-greedy','decomposed-greedy']})
    for arm in ('broad-greedy','decomposed-greedy'):
        save_json(source/'frozen'/arm/'0.json',{'nodes':{'leaf:case':{'program_ref':'unchanged'}}})
    (source/'observations.jsonl').write_text('')
    save_json(source/'results.json',{'status':'stopped'})
    calls=DurableCalls(source,lambda _: (_ for _ in ()).throw(OSError('TLS failure')),identity={'model':'mock'},
        max_calls=10,max_completion_tokens=100,reserve_calls=0,reserve_tokens=0,
        scope_limits={'search':10,'final':10})
    for i in range(3):
        with pytest.raises(CallFailure if i<2 else ProviderStopped):
            calls.call('check',{'x':i},{},template='saved',slot=str(i),max_tokens=10,case_id='scope',final=True)
    return source


def test_authorized_copy_preserves_slots_usage_and_original_stop(tmp_path):
    source=stopped_run(tmp_path);before=(source/'budget.json').read_bytes()
    record=prepare(source,tmp_path/'continuation')
    resumed=json.loads((tmp_path/'continuation/budget.json').read_text())
    old=json.loads(before)
    assert resumed['calls']==3 and resumed['completion_tokens_or_reserved']==30
    assert resumed['attempted_slots']==old['attempted_slots'] and resumed['limits']==old['limits']
    assert resumed['cases']==old['cases'] and resumed['final_calls']==3
    assert resumed['stopped'] is None and resumed['consecutive_errors']==0
    assert resumed['authorized_resumes'][0]['consecutive_errors']==3
    assert record['remaining_calls']==7 and record['remaining_completion_tokens']==70
    assert (source/'budget.json').read_bytes()==before
    for path in (source/'jobs').glob('*.json'):
        assert (tmp_path/'continuation/jobs'/path.name).read_bytes()==path.read_bytes()


def test_failed_slots_never_resampled_and_only_unattempted_can_run(tmp_path):
    source=stopped_run(tmp_path);output=tmp_path/'continuation';prepare(source,output)
    seen=[]
    class Engine:
        def generate(self,prompt,**kwargs):
            seen.append(prompt);return {'parsed':{'ok':True},'completionTokens':2}
    calls=DurableCalls(output,lambda _:Engine(),identity={'model':'mock'},max_calls=10,
        max_completion_tokens=100,scope_limits={'search':10,'final':10})
    for i in range(3):
        with pytest.raises(CallFailure):
            calls.call('check',{'x':i},{},template='saved',slot=str(i),max_tokens=10,case_id='scope',final=True)
    assert not seen and calls.budget['calls']==3
    calls.call('check',{'x':3},{},template='saved',slot='3',max_tokens=10,case_id='scope',final=True)
    assert len(seen)==1 and calls.budget['calls']==4 and calls.budget['completion_tokens_or_reserved']==32


def test_source_changes_or_frozen_changes_reject_continuation_resume(tmp_path):
    source=stopped_run(tmp_path);output=tmp_path/'continuation';record=prepare(source,output)
    assert prepare(source,output)==record
    save_json(output/'frozen/broad-greedy/0.json',{'changed':True})
    with pytest.raises(ValueError,match='assets'):prepare(source,output)
    source2=stopped_run(tmp_path/'second');output2=tmp_path/'continuation2';prepare(source2,output2)
    old=json.loads((source2/'budget.json').read_text());old['calls']+=1;save_json(source2/'budget.json',old)
    with pytest.raises(ValueError,match='accounting'):prepare(source2,output2)


def test_provider_rejection_cannot_be_released(tmp_path):
    source=stopped_run(tmp_path);budget=json.loads((source/'budget.json').read_text())
    budget['stopped']='Provider rejected the request';save_json(source/'budget.json',budget)
    with pytest.raises(ValueError,match='transport-stopped'):prepare(source,tmp_path/'copy')


def test_existing_new_stop_is_not_automatically_released(tmp_path):
    source=stopped_run(tmp_path);output=tmp_path/'copy';prepare(source,output)
    budget=json.loads((output/'budget.json').read_text());budget.update(stopped='Three consecutive transport failures',consecutive_errors=3)
    save_json(output/'budget.json',budget);before=fingerprint(output/'budget.json')
    prepare(source,output)
    assert fingerprint(output/'budget.json')==before


def test_inherited_accounting_cannot_be_rolled_back(tmp_path):
    source=stopped_run(tmp_path);output=tmp_path/'copy';prepare(source,output)
    budget=json.loads((output/'budget.json').read_text());budget['calls']=0
    save_json(output/'budget.json',budget)
    with pytest.raises(ValueError,match='rolled back'):prepare(source,output)
