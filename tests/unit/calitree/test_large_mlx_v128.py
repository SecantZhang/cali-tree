from copy import deepcopy
import pytest

from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine,MODEL,REVISION,WEIGHT_BYTES
from critical.core.decision.local_rubric_evidence_v94 import schema


def identity(tmp_path):
    sizes=(5320786075,5359012183,5338391026,3602259399)
    return {'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'status':'complete','destination':str(tmp_path),
            'weights':{f'model-0000{i}-of-00004.safetensors':size for i,size in enumerate(sizes,1)}}


def test_large_profile_cannot_accept_the_old_model_or_a_partial_weight_manifest(tmp_path):
    value=identity(tmp_path);engine=LargeMLXEngine(tmp_path,value)
    assert engine.model==MODEL and engine._creds is None and engine._model is None
    for field,replacement in [('model','other'),('revision','other'),('weights',{})]:
        wrong=deepcopy(value);wrong[field]=replacement
        with pytest.raises(ValueError,match='Exact completed'):LargeMLXEngine(tmp_path,wrong)


def test_native_output_keeps_large_model_identity_and_never_repairs_truncation(tmp_path,monkeypatch):
    engine=LargeMLXEngine(tmp_path,identity(tmp_path));a=tmp_path/'a';b=tmp_path/'b';a.touch();b.touch()
    raw={'content':'{broken','promptTokens':10,'completionTokens':12,'finishReason':'length'}
    monkeypatch.setattr(engine,'_complete',lambda *args:raw)
    result=engine.generate('test',[{'type':'image','path':str(a)},{'type':'image','path':str(b)}],schema())
    assert result['model']==MODEL and result['parsed'] is None and result['content']=='{broken' and result['totalTokens']==22
    assert engine._creds is None
