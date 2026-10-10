import json

import pytest

from critical.core.decision.artifacts import save_json
from run.calitree_resume_typed_twelve import prepare,install_failure_replay
from run.calitree_typed_twelve import execute
from tests.unit.calitree.test_typed_twelve import Engine,fake_manifest


def interrupted(tmp_path):
    manifest=fake_manifest(tmp_path)
    manifest.update(version='typed-evidence-twelve-v1',model='gpt-6-luna',provider='openai')
    source=tmp_path/'source';save_json(source/'manifest.json',manifest)
    seen=[];counter=[]
    class FailingEngine(Engine):
        def generate(self,*args,**kwargs):
            counter.append(1)
            if len(counter)>=6:raise OSError('synthetic TLS failure')
            return super().generate(*args,**kwargs)
    results=execute(source,manifest,lambda _:FailingEngine(seen))
    assert results['status']=='stopped' and results['budget']['stopped']=='Three consecutive transport failures'
    assert len(list((source/'frozen').glob('*/*.json')))<4
    return source,manifest


def test_partial_search_continues_without_reopening_frozen_or_retrying_failed_slots(tmp_path):
    source,manifest=interrupted(tmp_path);output=tmp_path/'continued'
    before={str(p.relative_to(source)):p.read_bytes() for folder in ('jobs','frozen','prepared')
            for p in (source/folder).rglob('*.json')}
    source_budget=(source/'budget.json').read_bytes();record=prepare(source,output)
    seen=[];results=execute(output,manifest,lambda _:Engine(seen))
    assert results['status']=='completed' and seen
    old=json.loads(source_budget);new=results['budget']
    assert new['attempted_slots'][:old['calls']]==old['attempted_slots']
    assert len(new['attempted_slots'])==len(set(new['attempted_slots']))==new['calls']
    assert new['calls']>old['calls'] and new['limits']==old['limits']
    assert (source/'budget.json').read_bytes()==source_budget
    assert all((output/rel).read_bytes()==value for rel,value in before.items())
    assert prepare(source,output)==record  # Existing immutable assets survive additions.
    n=len(seen);replay=execute(output,manifest,lambda _:Engine(seen))
    assert len(seen)==n and replay['cases']==results['cases']


def test_stop_release_is_once_and_inherited_assets_cannot_change(tmp_path):
    source,manifest=interrupted(tmp_path);output=tmp_path/'continued';prepare(source,output)
    budget=json.loads((output/'budget.json').read_text());budget['stopped']='Three consecutive transport failures'
    save_json(output/'budget.json',budget);prepare(source,output)
    assert json.loads((output/'budget.json').read_text())['stopped']==budget['stopped']
    job=next((output/'jobs').glob('*.json'));job.write_text('{}')
    with pytest.raises(ValueError,match='immutable'):prepare(source,output)


def test_provider_rejection_is_not_released(tmp_path):
    source,_=interrupted(tmp_path);budget=json.loads((source/'budget.json').read_text())
    budget['stopped']='Provider rejected the request';save_json(source/'budget.json',budget)
    with pytest.raises(ValueError,match='transport-stopped'):prepare(source,tmp_path/'continued')


def test_failed_diagnostics_do_not_resample_downstream_proposal(monkeypatch,tmp_path):
    from critical.core.decision.calls import DurableCalls,CallFailure
    old_call=DurableCalls.call
    monkeypatch.setattr(DurableCalls,'call',old_call)
    hits=[]
    class Mock:
        def generate(self,prompt,**kwargs):
            hits.append(prompt)
            if len(hits)==1:raise OSError('TLS failure')
            return {'parsed':{'transactions':[]},'completionTokens':2}
    ledger=DurableCalls(tmp_path,lambda _:Mock(),identity={'model':'mock'})
    def failed():return ledger.call('audit',{}, {},template='saved',slot='audit')
    with pytest.raises(CallFailure) as first:failed()
    expected=str(first.value)
    value=ledger.call('propose_typed',{'diagnostics':[expected]}, {},template='saved',slot='round/2/proposal')
    save_json(tmp_path/'initial_budget.json',ledger.budget)
    install_failure_replay()
    ledger=DurableCalls(tmp_path,lambda _:Mock(),identity={'model':'mock'})
    with pytest.raises(CallFailure) as replay:failed()
    assert str(replay.value)==expected
    assert ledger.call('propose_typed',{'diagnostics':[str(replay.value)]}, {},template='saved',slot='round/2/proposal')==value
    assert len(hits)==ledger.budget['calls']==2
    from critical.core.decision.calls import ProviderStopped
    with pytest.raises(ProviderStopped,match='Replay divergence'):
        ledger.call('propose_typed',{'diagnostics':['changed feedback']}, {},template='saved',slot='round/2/proposal')
    assert len(hits)==ledger.budget['calls']==2
