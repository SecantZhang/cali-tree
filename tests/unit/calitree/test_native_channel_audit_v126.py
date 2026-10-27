from copy import deepcopy
import pytest

from run.verify_calitree_native_sampling_v126 import validate_channels
from tests.unit.calitree.test_sampled_mlx_v124 import Tokenizer


def sample():
    raw={'generatedTokenIds':[1,2,3,4,5],'completionTokens':5,'closingThinkTokenId':2,'nativeFullContent':'observing</think>{}<|im_end|>',
        'thinkingClosed':True,'reasoningTokens':2,'finalTokens':3,'reasoningContent':'observing','content':'{}','finishReason':'stop','parsed':{}}
    profile={'enable_thinking':True,'max_reasoning_tokens':4,'max_new_tokens':10}
    return raw,profile


def test_native_channel_replay_rejects_thought_text_relabelled_as_a_final_answer():
    raw,profile=sample();validate_channels(raw,profile,Tokenizer(),[5],6)
    wrong=deepcopy(raw);wrong['content']='observing{}'
    with pytest.raises(ValueError,match='channel'):validate_channels(wrong,profile,Tokenizer(),[5],6)


def test_a_small_total_does_not_override_the_separate_reasoning_budget():
    raw,profile=sample()
    with pytest.raises(ValueError,match='budget'):validate_channels(raw,{**profile,'max_reasoning_tokens':1},Tokenizer(),[5],6)
