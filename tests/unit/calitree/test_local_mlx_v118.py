import json
import numpy as np
import pytest

from critical.lm_engine.local_mlx_v118 import LocalMLXEngine,MODEL,REVISION,WEIGHT_BYTES,mask_logits,build_tokenizer_data,terminal_ids
from critical.core.decision.local_rubric_evidence_v94 import schema


def engine(tmp_path,**kwargs):
    identity={'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'status':'complete','destination':str(tmp_path)}
    return LocalMLXEngine(tmp_path,identity,**kwargs)


def media(tmp_path):
    paths=[tmp_path/'a.png',tmp_path/'b.png']
    for p in paths:p.write_bytes(b'fixture')
    return [{'type':'image','path':str(p)} for p in paths]


def test_prefix_mask_cannot_select_a_disallowed_logit():
    scores=np.asarray([[100.,2.,3.,50.]],dtype=np.float32);result=mask_logits(np,scores,[1,2])
    assert int(np.argmax(result))==2 and np.isneginf(result[0,0]) and np.isneginf(result[0,3])
    for allowed in([],[-1],[4]):
        with pytest.raises(ValueError,match='in-vocabulary'):mask_logits(np,scores,allowed)


def test_no_network_or_model_substitution_and_no_implicit_unordered_images(tmp_path,monkeypatch):
    e=engine(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('No inference permitted')
    monkeypatch.setattr(e,'_complete',forbidden)
    with pytest.raises(ValueError,match='substitution'):e.generate('test',media(tmp_path),schema(),model='other')
    with pytest.raises(ValueError,match='Closed JSON'):e.generate('test',media(tmp_path),{'type':'object'})
    with pytest.raises(ValueError,match='Exactly two'):e.generate('test',[],schema())
    with pytest.raises(ValueError,match='local image'):e.generate('test',[{'type':'image','path':'https://example.com/a.png'}]*2,schema())
    assert e._creds is None


def test_native_content_and_accounting_are_preserved_without_repairs(tmp_path,monkeypatch):
    e=engine(tmp_path);raw={'content':'{not valid JSON','promptTokens':10,'completionTokens':8,'finishReason':'length'}
    monkeypatch.setattr(e,'_complete',lambda *args:raw)
    result=e.generate('test',media(tmp_path),schema())
    assert result['content']==raw['content'] and result['parsed'] is None and result['finishReason']=='length' and result['totalTokens']==18
    assert e._creds is None


def test_over_cap_native_counts_fail_instead_of_falling_back_to_transport(tmp_path,monkeypatch):
    e=engine(tmp_path,max_tokens=8)
    monkeypatch.setattr(e,'_complete',lambda *args:{'content':'{}','promptTokens':10,'completionTokens':9,'finishReason':'stop'})
    with pytest.raises(RuntimeError,match='accounting'):e.generate('test',media(tmp_path),schema())


def test_core_tokenizer_bridge_keeps_contextual_spaces_and_terminal_identity():
    class Tokenizer:
        all_special_ids=[2];eos_token_id=2
        def __len__(self):return 3
        def encode(self,text):assert text=='0';return [0]
        def decode(self,ids):
            return {(0,):'0',(1,):'x',(0,0):'00',(0,1):'0 x'}[tuple(ids)]
    regular,decode,eos,bitmask,size=build_tokenizer_data(Tokenizer(),lambda *args:args)
    assert regular==[(0,'0',False),(1,' x',True)] and eos==2 and bitmask is False and size==3
    assert decode([0,1])=='0 x'


def test_chat_and_text_terminal_ids_are_both_allowed_but_regular_tokens_are_not():
    class Tokenizer:
        eos_token_id=2
        def decode(self,ids,**kwargs):return {1:'<|endoftext|>',2:'<|im_end|>',3:'word'}[ids[0]]
    assert terminal_ids(Tokenizer(),1)==[1,2]
    with pytest.raises(ValueError,match='terminal'):terminal_ids(Tokenizer(),3)
