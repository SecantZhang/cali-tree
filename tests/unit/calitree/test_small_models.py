from run.calitree_small_models import validate_settings,MODELS
from critical.lm_engine.provider_api import chat_request


def test_fast_models_use_the_declared_nonreasoning_wire_profile():
    validate_settings()
    assert {v['model'] for v in MODELS.values()}=={'gpt-6-luna','gpt-5.4-mini'}
    for identity in MODELS.values():
        _,body,_,_=chat_request('https://api.openai.com/v1','placeholder',identity['model'],[],16384,0,provider='openai')
        assert body['reasoning_effort']=='none' and body['temperature']==0
        assert body['max_completion_tokens']==16384
