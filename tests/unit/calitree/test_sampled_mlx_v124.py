import pytest

from critical.lm_engine.local_mlx_sampled_v124 import split_channels,sample_seed,SampledLocalMLXEngine
from critical.lm_engine.local_mlx_v118 import MODEL,REVISION,WEIGHT_BYTES
from critical.core.decision.local_rubric_evidence_v94 import schema


class Tokenizer:
    def decode(self,ids,skip_special_tokens=False,**kwargs):
        pieces={1:'observing',2:'</think>',3:'{',4:'}',5:'<|im_end|>'}
        return ''.join(pieces[i] for i in ids if not skip_special_tokens or i not in(2,5))


def test_only_a_native_thinking_close_can_expose_final_json():
    incomplete=split_channels(Tokenizer(),[1,3,4],2,True)
    assert incomplete['content']=='' and incomplete['reasoningTokens']==3 and incomplete['finalTokens']==0 and not incomplete['thinkingClosed']
    result=split_channels(Tokenizer(),[1,2,3,4,5],2,True)
    assert result['content']=='{}' and result['reasoningTokens']==2 and result['finalTokens']==3 and result['nativeFullContent']=='observing</think>{}<|im_end|>'


def test_non_thinking_output_has_no_hidden_channel_or_token_loss():
    result=split_channels(Tokenizer(),[3,4,5],2,False)
    assert result['content']=='{}' and result['reasoningContent']=='' and result['reasoningTokens']==0 and result['finalTokens']==3


def test_seed_is_input_derived_and_does_not_depend_on_sampling_order():
    assert sample_seed('program','pair')==sample_seed('program','pair')
    assert sample_seed('program','pair')!=sample_seed('program','other') and 0<=sample_seed('program','pair')<2**32


def test_channel_budget_cannot_be_satisfied_by_moving_tokens_between_channels(tmp_path,monkeypatch):
    identity={'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'status':'complete','destination':str(tmp_path)}
    engine=SampledLocalMLXEngine(tmp_path,identity,thinking=True)
    a=tmp_path/'a';b=tmp_path/'b';a.touch();b.touch()
    raw={'content':'{}','nativeFullContent':'unclosed','promptTokens':10,'completionTokens':2050,'reasoningTokens':2049,'finalTokens':1}
    monkeypatch.setattr(engine,'_sample_complete',lambda *args:raw)
    with pytest.raises(RuntimeError,match='budget'):engine.generate('prompt',[{'type':'image','path':str(a)},{'type':'image','path':str(b)}],schema(),seed=1)
    assert engine._creds is None
