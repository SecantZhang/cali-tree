import pytest
from critical.lm_engine.provider_api import chat_request
from run.collect_calitree_aurora_pilot_v29r1 import collect


def test_luna_default_adapter_preserves_approved_wire_settings():
    url,payload,_,dialect=chat_request('https://api.openai.com/v1','dummy','gpt-6-luna',
                                      [{'role':'user','content':'test'}],8192,0,provider='openai')
    assert dialect=='openai' and url=='https://api.openai.com/v1/chat/completions'
    assert payload['reasoning_effort']=='none' and payload['temperature']==0
    assert payload['max_completion_tokens']==8192 and payload['model']=='gpt-6-luna'


def test_old_explicit_argument_fails_in_request_builder_before_http():
    with pytest.raises(ValueError,match='Explicit reasoning configuration'):
        chat_request('https://api.openai.com/v1','dummy','gpt-6-luna',[],8192,0,provider='openai',reasoning_effort='none')


def test_recovery_runner_still_requires_live_authorization(tmp_path):
    with pytest.raises(ValueError,match='authorization'):
        collect(tmp_path)
