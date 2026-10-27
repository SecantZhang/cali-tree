"""Pinned32B local observation profile using the audited native MLX bridge."""
from pathlib import Path
import time

from .lm_template import LMEngine
from .local_mlx_v118 import LocalMLXEngine,mask_logits,CACHE_LIMIT
from .local_qwen_v94 import local_messages,parse_json
from ..core.decision.artifacts import digest

MODEL='mlx-community/Qwen3-VL-32B-Instruct-4bit'
REVISION='6e5644d3ea4b953b5221ffd02339bf897041038a'
WEIGHT_BYTES=19620448683
MEMORY_LIMIT=24*1024**3


class LargeMLXEngine(LocalMLXEngine):
    name='local_mlx_large_v128'
    default_model=MODEL

    def __init__(self,local_dir,checkpoint_identity,*,history=None,max_tokens=512,max_pixels=256*32*32):
        if type(max_tokens) is not int or not 1<=max_tokens<=512 or max_pixels not in(256*32*32,1024*32*32):
            raise ValueError('Bounded large-MLX observation profile required')
        weights=checkpoint_identity.get('weights',{})
        expected={f'model-0000{i}-of-00004.safetensors' for i in range(1,5)}
        if (checkpoint_identity.get('model')!=MODEL or checkpoint_identity.get('revision')!=REVISION or
                checkpoint_identity.get('weight_bytes')!=WEIGHT_BYTES or checkpoint_identity.get('status')!='complete' or
                set(weights)!=expected or sum(weights.values())!=WEIGHT_BYTES):
            raise ValueError('Exact completed32B quantized checkpoint required')
        LMEngine.__init__(self,model=MODEL,history=history,max_tokens=max_tokens,temperature=0.)
        self.local_dir=Path(local_dir).resolve();self.identity=checkpoint_identity;self.max_pixels=max_pixels
        self._model=self._processor=self._tokenizer_data=None

    def _complete(self,messages,paths,schema):
        import mlx.core as mx
        old_memory=mx.set_memory_limit(MEMORY_LIMIT);old_cache=mx.set_cache_limit(CACHE_LIMIT);generator=None
        try:
            self._load()
            from mlx_vlm.generate import generate_step
            from lmformatenforcer import TokenEnforcer,JsonSchemaParser
            inputs,rendered=self._prepare_inputs(messages,paths);enforcer=TokenEnforcer(self._tokenizer_data,JsonSchemaParser(schema))
            def constrain(tokens,scores):return mask_logits(mx,scores,enforcer.get_allowed_tokens(tokens.tolist()).allowed_tokens)
            extra={k:v for k,v in inputs.items() if k not in('input_ids','pixel_values','attention_mask')}
            generator=generate_step(inputs['input_ids'],self._model,inputs['pixel_values'],inputs.get('attention_mask'),max_tokens=self.max_tokens,
                temperature=0.,top_p=1.,prefill_step_size=None,logits_processors=[constrain],**extra)
            generated=[];finish='length'
            for token,_ in generator:
                generated.append(int(token))
                if mx.get_peak_memory()>MEMORY_LIMIT:raise RuntimeError('Observed32B MLX allocation exceeded24GiB')
                if token in self._eos:finish='stop';break
            return {'content':self._processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False),
                'promptTokens':int(inputs['input_ids'].size),'completionTokens':len(generated),'finishReason':finish,
                'renderedPromptRef':digest(rendered),'peakMemoryBytes':mx.get_peak_memory(),'inputShapes':{k:list(v.shape) for k,v in inputs.items()}}
        finally:
            if generator is not None:generator.close()
            mx.synchronize();mx.clear_cache();mx.set_memory_limit(old_memory);mx.set_cache_limit(old_cache)

    def generate(self,prompt,media_inputs=None,schema=None,*,system=None,model=None,strict_schema=True):
        if model not in(None,MODEL):raise ValueError('No model/endpoint substitution in the pinned32B profile')
        if (not isinstance(schema,dict) or schema.get('type')!='object' or schema.get('additionalProperties') is not False or
                set(schema.get('properties',{}))!=set(schema.get('required',[]))):raise ValueError('Closed native JSON schema required')
        messages,paths=local_messages(prompt,media_inputs,system)
        if len(paths)!=2:raise ValueError('Exactly two ordered local comparison images required')
        start=time.monotonic();raw=None;error=None
        try:
            raw=self._complete(messages,paths,schema)
            if (type(raw['completionTokens']) is not int or not 0<=raw['completionTokens']<=self.max_tokens or
                    type(raw['promptTokens']) is not int or raw['promptTokens']<1 or raw['finishReason'] not in('stop','length')):
                raise ValueError('Invalid native32B token accounting')
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        elapsed=time.monotonic()-start
        if self.history is not None:
            self.history.record(engine=self.name,model=MODEL,prompt=(system+'\n\n' if system else '')+prompt,response=raw['content'] if raw else None,
                media_inputs=media_inputs,prompt_tokens=raw['promptTokens'] if raw else 0,completion_tokens=raw['completionTokens'] if raw else 0,
                total_tokens=raw['promptTokens']+raw['completionTokens'] if raw else 0,latency_s=elapsed,endpoint='local-mlx',error=error,
                extra={'checkpoint_revision':REVISION,'max_new_tokens':self.max_tokens,'max_pixels_per_image':self.max_pixels,'enable_thinking':False,'do_sample':False,
                    'decoder':'native-json-prefix-mlx-large-v128','input_format':'native_pytorch_cpu_to_mlx','memory_limit_bytes':MEMORY_LIMIT,
                    'memory_limit_kind':'mlx_soft_guideline_with_peak_abort','cache_limit_bytes':CACHE_LIMIT,'remote_calls':0,
                    'rendered_prompt_ref':raw.get('renderedPromptRef') if raw else None})
        if error is not None:raise RuntimeError(error)
        return {**raw,'parsed':parse_json(raw['content']),'model':MODEL,'engine':self.name,'endpointHost':'local-mlx','totalTokens':raw['promptTokens']+raw['completionTokens'],'latencySeconds':elapsed}
