"""Seeded native instruct/thinking profiles with explicit final JSON channels.

Reasoning is retained as native output but never parsed as an observation.
Only the final channel after the model's own closing-think token is eligible.
No synthetic closing token, JSON repair or resampling is used.
"""
import time

from .local_mlx_v118 import LocalMLXEngine,MODEL,MEMORY_LIMIT,CACHE_LIMIT,mask_logits
from .local_qwen_v94 import local_messages,parse_json
from ..core.decision.artifacts import digest


def sample_seed(program_ref,pair_ref):
    return int(digest(['local-sampling-v124',20261023,program_ref,pair_ref])[:8],16)


def split_channels(tokenizer,ids,closing_id,thinking):
    full=tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    if not thinking:
        return {'nativeFullContent':full,'reasoningContent':'','content':tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False),
                'reasoningTokens':0,'finalTokens':len(ids),'thinkingClosed':True}
    if closing_id not in ids:
        return {'nativeFullContent':full,'reasoningContent':full,'content':'','reasoningTokens':len(ids),'finalTokens':0,'thinkingClosed':False}
    end=ids.index(closing_id)+1
    return {'nativeFullContent':full,'reasoningContent':tokenizer.decode(ids[:end-1],skip_special_tokens=False,clean_up_tokenization_spaces=False),
        'content':tokenizer.decode(ids[end:],skip_special_tokens=True,clean_up_tokenization_spaces=False),'reasoningTokens':end,'finalTokens':len(ids)-end,'thinkingClosed':True}


class SampledLocalMLXEngine(LocalMLXEngine):
    name='local_mlx_sampled_v124'

    def __init__(self,*args,thinking=False,**kwargs):
        super().__init__(*args,**kwargs);self.configure(thinking)

    def configure(self,thinking):
        if type(thinking) is not bool:raise ValueError('Explicit native thinking mode required')
        self.thinking=thinking;self.temperature=1. if thinking else .7;self.top_p=.95 if thinking else .8
        self.max_reasoning=2048 if thinking else 0;self.max_final=512;self.max_tokens=self.max_reasoning+self.max_final

    def _prepare_inputs(self,messages,paths):
        import mlx.core as mx
        from PIL import Image
        images=[]
        for path in paths:
            with Image.open(path) as im:images.append(im.convert('RGB'))
        rendered=self._processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=self.thinking)
        prepared=self._processor(text=[rendered],images=images,return_tensors='pt',padding=True)
        return {k:mx.array(v.detach().cpu().numpy()) for k,v in prepared.items()},rendered

    def _sample_complete(self,messages,paths,schema,seed):
        import mlx.core as mx
        previous_memory=mx.set_memory_limit(MEMORY_LIMIT);previous_cache=mx.set_cache_limit(CACHE_LIMIT);generator=None
        try:
            self._load()
            from mlx_vlm.generate import generate_step
            from mlx_lm.sample_utils import make_sampler
            from lmformatenforcer import TokenEnforcer,JsonSchemaParser
            inputs,rendered=self._prepare_inputs(messages,paths);prompt_tokens=int(inputs['input_ids'].size)
            closing=self._processor.tokenizer.convert_tokens_to_ids('</think>')
            if self._processor.tokenizer.decode([closing],skip_special_tokens=False)!='</think>':raise ValueError('Native thinking boundary unavailable')
            enforcer=TokenEnforcer(self._tokenizer_data,JsonSchemaParser(schema));prefix_length=None
            def constrain(tokens,scores):
                nonlocal prefix_length
                sequence=tokens.tolist()
                if prefix_length is None:prefix_length=len(sequence)
                generated=sequence[prefix_length:]
                # Native presence penalty applies only to emitted tokens.
                if generated:
                    scores=scores.at[:,mx.array(sorted(set(generated)))].add(-1.5)
                if self.thinking and closing not in generated:return scores
                after=generated[generated.index(closing)+1:] if self.thinking else generated
                allowed=enforcer.get_allowed_tokens([closing,*after]).allowed_tokens
                return mask_logits(mx,scores,allowed)
            extra={k:v for k,v in inputs.items() if k not in('input_ids','pixel_values','attention_mask')}
            mx.random.seed(seed)
            generator=generate_step(inputs['input_ids'],self._model,inputs['pixel_values'],inputs.get('attention_mask'),max_tokens=self.max_tokens,
                temperature=self.temperature,top_p=self.top_p,prefill_step_size=None,logits_processors=[constrain],
                sampler=make_sampler(temp=self.temperature,top_p=self.top_p,top_k=20,min_p=0.),**extra)
            generated=[];closing_position=None;finish='length';termination='total_token_limit'
            for token,_ in generator:
                generated.append(int(token))
                if mx.get_peak_memory()>MEMORY_LIMIT:raise RuntimeError('Observed MLX allocation exceeded8GiB')
                if self.thinking and closing_position is None and token==closing:closing_position=len(generated)-1
                if token in self._eos:
                    if not self.thinking or closing_position is not None:finish='stop';termination='native_eos'
                    else:termination='eos_before_thinking_closed'
                    break
                if self.thinking and closing_position is None and len(generated)>=self.max_reasoning:
                    termination='reasoning_token_limit';break
                final_count=len(generated)-(closing_position+1) if self.thinking and closing_position is not None else len(generated) if not self.thinking else 0
                if final_count>=self.max_final:termination='final_token_limit';break
            channels=split_channels(self._processor.tokenizer,generated,closing,self.thinking)
            return {**channels,'generatedTokenIds':generated,'closingThinkTokenId':closing,'seed':seed,'promptTokens':prompt_tokens,'completionTokens':len(generated),
                'finishReason':finish,'terminationReason':termination,'renderedPromptRef':digest(rendered),'peakMemoryBytes':mx.get_peak_memory(),
                'inputShapes':{k:list(v.shape) for k,v in inputs.items()}}
        finally:
            if generator is not None:generator.close()
            mx.synchronize();mx.clear_cache();mx.set_memory_limit(previous_memory);mx.set_cache_limit(previous_cache)

    def generate(self,prompt,media_inputs=None,schema=None,*,seed,system=None,model=None,strict_schema=True):
        if model not in(None,MODEL) or type(seed) is not int or not 0<=seed<2**32:raise ValueError('Pinned model and explicit input-derived seed required')
        if (not isinstance(schema,dict) or schema.get('type')!='object' or schema.get('additionalProperties') is not False or
                set(schema.get('properties',{}))!=set(schema.get('required',[]))):raise ValueError('Closed final JSON schema required')
        messages,paths=local_messages(prompt,media_inputs,system)
        if len(paths)!=2:raise ValueError('Exactly two ordered images required')
        start=time.monotonic();raw=None;error=None
        try:
            raw=self._sample_complete(messages,paths,schema,seed)
            if (not 0<=raw['completionTokens']<=self.max_tokens or raw['reasoningTokens']+raw['finalTokens']!=raw['completionTokens'] or
                    raw['reasoningTokens']>self.max_reasoning or raw['finalTokens']>self.max_final):raise ValueError('Native channel token budget differs')
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        elapsed=time.monotonic()-start
        if self.history is not None:
            self.history.record(engine=self.name,model=MODEL,prompt=(system+'\n\n' if system else '')+prompt,response=raw['nativeFullContent'] if raw else None,
                media_inputs=media_inputs,prompt_tokens=raw['promptTokens'] if raw else 0,completion_tokens=raw['completionTokens'] if raw else 0,
                total_tokens=raw['promptTokens']+raw['completionTokens'] if raw else 0,latency_s=elapsed,endpoint='local-mlx',error=error,
                extra={'checkpoint_revision':self.identity['revision'],'max_new_tokens':self.max_tokens,'max_pixels_per_image':self.max_pixels,'enable_thinking':self.thinking,
                    'do_sample':True,'temperature':self.temperature,'top_p':self.top_p,'top_k':20,'presence_penalty':1.5,'seed':seed,
                    'decoder':'native_sampled_thinking_boundary_json_v124','remote_calls':0,'reasoning_tokens':raw['reasoningTokens'] if raw else None,'final_tokens':raw['finalTokens'] if raw else None})
        if error is not None:raise RuntimeError(error)
        return {**raw,'parsed':parse_json(raw['content']),'model':MODEL,'engine':self.name,'endpointHost':'local-mlx','totalTokens':raw['promptTokens']+raw['completionTokens'],'latencySeconds':elapsed}
