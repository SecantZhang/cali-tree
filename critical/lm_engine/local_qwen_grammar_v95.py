"""Native JSON-schema decoding of local observations, without output repair."""
from .local_qwen_v94 import LocalQwenEngine


class LocalQwenGrammarEngine(LocalQwenEngine):
    name = 'local_qwen_grammar_v95'

    def _complete_schema(self, messages, paths, schema):
        self._load()
        import torch
        from PIL import Image
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
        images = []
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert('RGB'))
        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], images=images or None, return_tensors='pt').to(self.device)
        tokens = int(inputs['input_ids'].shape[-1])
        allowed = build_transformers_prefix_allowed_tokens_fn(self._processor.tokenizer, JsonSchemaParser(schema))
        with torch.inference_mode():
            result = self._model.generate(**inputs, max_new_tokens=self.max_tokens, do_sample=False,
                    temperature=None, top_p=None, top_k=None, prefix_allowed_tokens_fn=allowed)
        new = result[:, tokens:]
        content = self._processor.batch_decode(new, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return content, tokens, int(new.shape[-1])

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None, strict_schema=True):
        if model not in (None, self.default_model):
            raise ValueError('No model or endpoint substitution in the pinned local profile')
        if (not isinstance(schema, dict) or schema.get('type') != 'object' or
                schema.get('additionalProperties') is not False or
                set(schema.get('properties', {})) != set(schema.get('required', []))):
            raise ValueError('Closed object schema with every field required')
        # The closure is per request; no mutable schema shared across calls.
        return self._run_local(prompt, media_inputs, schema, system,
                               lambda messages, paths: self._complete_schema(messages, paths, schema))
