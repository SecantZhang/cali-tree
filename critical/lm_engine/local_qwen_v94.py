"""Pinned local Qwen3-VL inference with no credential or network fallback."""
import json
from hashlib import sha256
from pathlib import Path
import time

from .lm_template import LMEngine

MODEL = 'Qwen/Qwen3-VL-8B-Instruct'
REVISION = '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b'


def file_hash(path):
    result = sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def parse_json(content):
    text = content.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[8:-4]
    elif text.startswith('```\n') and text.endswith('\n```'):
        text = text[4:-4]
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def local_messages(prompt, media_inputs, system=None):
    """Plan local images without opening URLs or constructing data uploads."""
    content = []; paths = []
    for media in media_inputs or []:
        if media.get('type') == 'image':
            path = Path(media['path'])
            if not path.is_absolute() or not path.is_file():
                raise ValueError('Existing absolute local image paths required')
            paths.append(path); content.append({'type': 'image'})
        elif media.get('type') == 'text':
            content.append({'type': 'text', 'text': media.get('text', '')})
        else:
            raise ValueError('Local engine accepts image/text references only')
    if len(paths) > 2:
        raise ValueError('The local comparison profile permits at most two images')
    content.append({'type': 'text', 'text': prompt})
    messages = ([{'role': 'system', 'content': system}] if system else [])
    messages.append({'role': 'user', 'content': content})
    return messages, paths


class LocalQwenEngine(LMEngine):
    name = 'local_qwen_v94'
    default_model = MODEL
    supports_video = False

    def __init__(self, local_dir, checkpoint_identity, *, history=None, max_tokens=256,
                 device='mps', max_pixels=256*32*32):
        if type(max_tokens) is not int or not 1 <= max_tokens <= 512 or device not in ('mps', 'cpu'):
            raise ValueError('Bounded explicit local inference profile required')
        super().__init__(model=self.default_model, history=history, max_tokens=max_tokens, temperature=0.)
        self.local_dir = Path(local_dir).resolve(); self.identity = checkpoint_identity
        self.device, self.max_pixels = device, max_pixels
        self._model = self._processor = None

    def _load(self):
        if self._model is not None:
            return
        if (self.identity.get('model') != MODEL or self.identity.get('revision') != REVISION or
                self.identity.get('status') != 'complete' or self.identity.get('destination') != str(self.local_dir)):
            raise ValueError('Exact completed pinned local checkpoint required')
        required = {'config.json', 'tokenizer.json', 'model.safetensors.index.json', *self.identity.get('weights', {})}
        if not required <= set(self.identity.get('file_sha256', {})) or self.identity.get('weight_bytes') != 17534339512:
            raise ValueError('Complete checkpoint file identity required')
        for name, sha in self.identity['file_sha256'].items():
            if Path(name).name != name or file_hash(self.local_dir/name) != sha:
                raise ValueError('Changed local model file')
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        if self.device == 'mps' and not torch.backends.mps.is_available():
            raise RuntimeError('Metal unavailable; no silent CPU or remote fallback')
        self._processor = AutoProcessor.from_pretrained(self.local_dir, local_files_only=True, trust_remote_code=False)
        self._processor.image_processor.size = {'longest_edge': self.max_pixels, 'shortest_edge': 64*32*32}
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(self.local_dir, local_files_only=True,
                    use_safetensors=True, trust_remote_code=False, dtype=torch.float16, attn_implementation='sdpa').to(self.device).eval()

    def _complete(self, messages, paths):
        self._load()
        import torch
        from PIL import Image
        images = []
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert('RGB'))
        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], images=images or None, return_tensors='pt').to(self.device)
        input_tokens = int(inputs['input_ids'].shape[-1])
        with torch.inference_mode():
            result = self._model.generate(**inputs, max_new_tokens=self.max_tokens, do_sample=False)
        new = result[:, input_tokens:]
        content = self._processor.batch_decode(new, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return content, input_tokens, int(new.shape[-1])

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None, strict_schema=False):
        if model not in (None, self.default_model):
            raise ValueError('No model or endpoint substitution in the pinned local profile')
        if strict_schema:
            raise ValueError('Local decoding is advisory JSON; caller must validate the response')
        return self._run_local(prompt, media_inputs, schema, system, self._complete)

    def _run_local(self, prompt, media_inputs, schema, system, complete):
        messages, paths = local_messages(prompt, media_inputs, system)
        start = time.monotonic(); error = None; content = None; input_tokens = output_tokens = 0
        try:
            content, input_tokens, output_tokens = complete(messages, paths)
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)
        elapsed = time.monotonic()-start
        if self.history is not None:
            self.history.record(engine=self.name, model=self.model, prompt=(system+'\n\n' if system else '')+prompt,
                response=content, media_inputs=media_inputs, prompt_tokens=input_tokens, completion_tokens=output_tokens,
                total_tokens=input_tokens+output_tokens, latency_s=elapsed, endpoint='local-mps' if self.device == 'mps' else 'local-cpu',
                error=error, extra={'checkpoint_revision': self.identity.get('revision'), 'max_new_tokens': self.max_tokens,
                                  'max_pixels_per_image': self.max_pixels, 'do_sample': False, 'remote_calls': 0})
        if error is not None:
            raise RuntimeError(error)
        out = {'content': content, 'model': self.model, 'engine': self.name, 'promptTokens': input_tokens,
               'completionTokens': output_tokens, 'totalTokens': input_tokens+output_tokens, 'latencySeconds': elapsed,
               'endpointHost': 'local-'+self.device, 'finishReason': 'length' if output_tokens >= self.max_tokens else 'stop'}
        if schema is not None:
            out['parsed'] = parse_json(content)
        return out
