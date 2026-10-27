from copy import deepcopy
import pytest

from run.verify_calitree_mlx_probe_v120 import validate
from tests.unit.calitree.test_local_cache_audit_v98 import fixture


def test_native_raw_replacement_and_remote_endpoint_are_rejected():
    job,response,profile=fixture();assert validate(job,response,profile)
    wrong=deepcopy(response);wrong['response']['parsed']={}
    with pytest.raises(ValueError,match='unmodified raw'):validate(job,wrong,profile)
    wrong=deepcopy(response);wrong['response']['endpointHost']='api.openai.com'
    with pytest.raises(ValueError,match='remote'):validate(job,wrong,profile)


def test_rejected_outputs_keep_missing_records_and_caps_still_apply():
    job,response,profile=fixture();wrong=deepcopy(response);wrong['response']['completionTokens']=257;wrong['response']['totalTokens']=357
    with pytest.raises(ValueError,match='accounting'):validate(job,wrong,profile)
    failed={**response,'record':None,'observation':None,'error':'RuntimeError: backend failed'}
    assert validate(job,failed,profile) is False
    with pytest.raises(ValueError,match='explicit failures'):validate(job,{**failed,'error':None},profile)
