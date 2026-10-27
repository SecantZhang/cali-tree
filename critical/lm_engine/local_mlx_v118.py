"""Pinned local MLX image comparison with native JSON token constraints.

Uses the upstream MLX model and Hugging Face processor; never calls the shared
HTTP transport or repairs a generated response. Model loading is lazy/offline.
"""
import json
from pathlib import Path
import time

from .lm_template import LMEngine
from .local_qwen_v94 import file_hash, local_messages, parse_json
from ..core.decision.artifacts import digest

MODEL='mlx-community/Qwen3.5-9B-4bit'
REVISION='8b2b98c00a6b4d291155e4890773ca8f769aee53'
WEIGHT_BYTES=5950221072
MEMORY_LIMIT=8*1024**3
CACHE_LIMIT=256*1024**2


def terminal_ids(tokenizer,configured):
    ids=configured if isinstance(configured,list) else [configured]
    ids=sorted(set([*ids,tokenizer.eos_token_id]))
    if any(type(i) is not int or tokenizer.decode([i],skip_special_tokens=False) not in('<|endoftext|>','<|im_end|>') for i in ids):
        raise ValueError('Recognized model/tokenizer terminal tokens required')
    return ids


def build_tokenizer_data(tokenizer,data_type=None,*,eos_token_ids=None):
    """Bridge the core enforcer API without its Transformers4-only imports."""
    if data_type is None:
        from lmformatenforcer import TokenEnforcerTokenizerData
        data_type=TokenEnforcerTokenizerData
    neutral=tokenizer.encode('0')[-1];special=set(tokenizer.all_special_ids);regular=[]
    for index in range(len(tokenizer)):
        if index in special:continue
        contextual=tokenizer.decode([neutral,index])[1:]
        standalone=tokenizer.decode([index])
        regular.append((index,contextual,len(contextual)>len(standalone)))
    def decode(tokens):return tokenizer.decode(tokens).rstrip('�')
    return data_type(regular,decode,tokenizer.eos_token_id if eos_token_ids is None else eos_token_ids,False,len(tokenizer))


def mask_logits(mx,scores,allowed):
    if not allowed or any(type(i) is not int or not 0<=i<scores.shape[-1] for i in allowed):
        raise ValueError('Nonempty in-vocabulary JSON token set required')
    mask=mx.full(scores.shape,-float('inf'),dtype=scores.dtype)
    mask[:,mx.array(allowed)]=0
    return scores+mask


class LocalMLXEngine(LMEngine):
    name='local_mlx_v118'
    default_model=MODEL
    supports_video=False

    def __init__(self,local_dir,checkpoint_identity,*,history=None,max_tokens=512,max_pixels=256*32*32):
        if type(max_tokens) is not int or not 1<=max_tokens<=512 or max_pixels not in (256*32*32,1024*32*32):
            raise ValueError('Bounded MLX observation profile required')
        if (checkpoint_identity.get('model')!=MODEL or checkpoint_identity.get('revision')!=REVISION or
                checkpoint_identity.get('weight_bytes')!=WEIGHT_BYTES or checkpoint_identity.get('status')!='complete'):
            raise ValueError('Exact completed quantized checkpoint required')
        super().__init__(model=MODEL,history=history,max_tokens=max_tokens,temperature=0.)
        self.local_dir=Path(local_dir).resolve();self.identity=checkpoint_identity;self.max_pixels=max_pixels
        self._model=self._processor=self._tokenizer_data=None

    def _load(self):
        if self._model is not None:
            return
        if self.identity.get('destination')!=str(self.local_dir):
            raise ValueError('Local MLX checkpoint location differs from its manifest')
        required={'config.json','tokenizer.json','preprocessor_config.json','chat_template.jinja','model.safetensors.index.json',*self.identity.get('weights',{})}
        if not required<=set(self.identity.get('file_sha256',{})):
            raise ValueError('Complete safetensors/tokenizer identity required')
        for name,sha in self.identity['file_sha256'].items():
            if Path(name).name!=name or file_hash(self.local_dir/name)!=sha:
                raise ValueError('Changed local MLX model file')
        import mlx.core as mx
        from mlx_vlm.utils import load_model
        from transformers import AutoProcessor
        if not mx.metal.is_available():
            raise RuntimeError('Metal unavailable; no CPU or remote fallback')
        processor=AutoProcessor.from_pretrained(self.local_dir,local_files_only=True,trust_remote_code=False,use_fast=True)
        processor.image_processor.size={'longest_edge':self.max_pixels,'shortest_edge':64*32*32}
        model=load_model(self.local_dir,lazy=False,trust_remote_code=False,local_files_only=True)
        model.eval()
        config=json.loads((self.local_dir/'config.json').read_text())
        eos=terminal_ids(processor.tokenizer,config['text_config']['eos_token_id'])
        tokenizer_data=build_tokenizer_data(processor.tokenizer,eos_token_ids=eos)
        self._model,self._processor,self._tokenizer_data,self._eos=model,processor,tokenizer_data,eos

    def _prepare_inputs(self,messages,paths):
        import mlx.core as mx
        from PIL import Image
        images=[]
        for path in paths:
            with Image.open(path) as im:images.append(im.convert('RGB'))
        rendered=self._processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        # The native fast processor supports PyTorch output. Image work stays
        # on CPU; only its finished tensors transfer into the MLX backend.
        prepared=self._processor(text=[rendered],images=images,return_tensors='pt',padding=True)
        inputs={k:mx.array(v.detach().cpu().numpy()) for k,v in prepared.items()}
        return inputs,rendered

    def _complete(self,messages,paths,schema):
        import mlx.core as mx
        previous_memory=mx.set_memory_limit(MEMORY_LIMIT);previous_cache=mx.set_cache_limit(CACHE_LIMIT)
        generator=None
        try:
            self._load()
            from mlx_vlm.generate import generate_step
            from lmformatenforcer import TokenEnforcer,JsonSchemaParser
            inputs,rendered=self._prepare_inputs(messages,paths)
            prompt_tokens=int(inputs['input_ids'].size)
            # Per-request parser state; no state is shared with another call.
            enforcer=TokenEnforcer(self._tokenizer_data,JsonSchemaParser(schema))
            def enforce(tokens,scores):
                allowed=enforcer.get_allowed_tokens(tokens.tolist()).allowed_tokens
                return mask_logits(mx,scores,allowed)
            extra={k:v for k,v in inputs.items() if k not in('input_ids','pixel_values','attention_mask')}
            generator=generate_step(inputs['input_ids'],self._model,inputs['pixel_values'],inputs.get('attention_mask'),
                max_tokens=self.max_tokens,temperature=0.,top_p=1.,prefill_step_size=None,logits_processors=[enforce],**extra)
            generated=[];finish='length'
            for token,_ in generator:
                generated.append(int(token))
                if mx.get_peak_memory()>MEMORY_LIMIT:
                    raise RuntimeError('Observed MLX allocation exceeded the8GiB experiment bound')
                if token in self._eos:
                    finish='stop';break
            content=self._processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False)
            return {'content':content,'promptTokens':prompt_tokens,'completionTokens':len(generated),'finishReason':finish,
                    'renderedPromptRef':digest(rendered),'peakMemoryBytes':mx.get_peak_memory(),
                    'inputShapes':{k:list(v.shape) for k,v in inputs.items()}}
        finally:
            if generator is not None:generator.close()
            mx.synchronize();mx.clear_cache();mx.set_memory_limit(previous_memory);mx.set_cache_limit(previous_cache)

    def generate(self,prompt,media_inputs=None,schema=None,*,system=None,model=None,strict_schema=True):
        if model not in(None,MODEL):
            raise ValueError('No model or endpoint substitution in the local MLX profile')
        if (not isinstance(schema,dict) or schema.get('type')!='object' or schema.get('additionalProperties') is not False or
                set(schema.get('required',[]))!=set(schema.get('properties',{}))):
            raise ValueError('Closed JSON schema with every field required')
        messages,paths=local_messages(prompt,media_inputs,system)
        if len(paths)!=2:
            raise ValueError('Exactly two ordered local comparison images required')
        started=time.monotonic();raw=None;error=None
        try:
            raw=self._complete(messages,paths,schema)
            if (type(raw['completionTokens']) is not int or not 0<=raw['completionTokens']<=self.max_tokens or
                    type(raw['promptTokens']) is not int or raw['promptTokens']<1 or raw['finishReason'] not in('stop','length')):
                raise ValueError('Invalid native MLX token accounting')
        except Exception as exc:
            error=type(exc).__name__+': '+str(exc)
        elapsed=time.monotonic()-started
        if self.history is not None:
            self.history.record(engine=self.name,model=self.model,prompt=(system+'\n\n' if system else '')+prompt,
                response=raw['content'] if raw else None,media_inputs=media_inputs,prompt_tokens=raw['promptTokens'] if raw else 0,
                completion_tokens=raw['completionTokens'] if raw else 0,total_tokens=(raw['promptTokens']+raw['completionTokens']) if raw else 0,
                latency_s=elapsed,endpoint='local-mlx',error=error,
                extra={'checkpoint_revision':REVISION,'max_new_tokens':self.max_tokens,'max_pixels_per_image':self.max_pixels,'enable_thinking':False,
                       'do_sample':False,'decoder':'native-json-prefix-mlx-core-v118','input_format':'native_pytorch_cpu_to_mlx','termination':'recognized_model_and_tokenizer_end_tokens','memory_limit_bytes':MEMORY_LIMIT,'memory_limit_kind':'mlx_soft_guideline_with_peak_abort','cache_limit_bytes':CACHE_LIMIT,'remote_calls':0,
                       'rendered_prompt_ref':raw.get('renderedPromptRef') if raw else None})
        if error is not None:
            raise RuntimeError(error)
        return {**raw,'parsed':parse_json(raw['content']),'model':MODEL,'engine':self.name,'endpointHost':'local-mlx',
                'totalTokens':raw['promptTokens']+raw['completionTokens'],'latencySeconds':elapsed}
