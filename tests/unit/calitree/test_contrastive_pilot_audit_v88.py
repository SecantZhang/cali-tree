import pytest

from critical.core.decision.calls import DurableCalls
from run.verify_calitree_contrastive_pilot_v88 import slot_ref,metrics,audit
from run.calitree_contrastive_pilot_v75 import LUNA,SOL


def test_auditor_reconstructs_both_actual_durable_request_routes(tmp_path):
    before=tmp_path/'before';after=tmp_path/'after';before.write_bytes(b'source');after.write_bytes(b'edit')
    class Engine:
        def generate(self,*args,**kwargs):return {'parsed':{'label':'no','rationale':'Mock judgment.'},'finishReason':'stop','completionTokens':5,'promptTokens':10}
    factory=lambda cap:Engine()
    calls=DurableCalls(tmp_path/'ledger',factory,identity=LUNA,max_calls=72,max_completion_tokens=344064,
        scope_limits={'search':3,'final':0},routes={'sol':{'identity':SOL,'engine_factory':factory}})
    for arm,route,cap in [('regular_luna',None,2048),('semantic_sol','sol',8192)]:
        job={'case':'query','arm':arm,'route':route,'max_tokens':cap,'payload':{'instruction':'Make the cup blue'},
            'media':[{'type':'text','text':'SOURCE image'},{'type':'image','path':str(before)},{'type':'text','text':'EDITED image'},{'type':'image','path':str(after)}],
            'schema':{'type':'object'},'template':'fixed template'}
        _,actual=calls.call('semantic_contrastive_v75',job['payload'],job['schema'],template=job['template'],media=job['media'],case_id=job['case'],slot=arm,route=route,max_tokens=cap)
        assert slot_ref(job)==actual
        assert slot_ref({**job,'max_tokens':cap+1})!=actual


def test_unresolved_remains_in_accuracy_denominator():
    result=metrics([{'reference':0,'arm':0},{'reference':1,'arm':-1}],'arm')
    assert result['correct']==1 and result['total']==2 and result['accuracy']==.5
    assert result['unresolved']==1 and result['confusion']['partial']['unresolved']==1


def test_mock_rehearsal_cannot_be_reported_as_paid_benchmark(tmp_path):
    prepared=tmp_path/'mock';prepared.mkdir();(prepared/'mock_only.json').write_text('{}')
    with pytest.raises(ValueError,match='Mock'):audit(prepared,tmp_path/'out',complete=True)
