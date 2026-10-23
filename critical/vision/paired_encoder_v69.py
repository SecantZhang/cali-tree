"""Reusable local encoder for arbitrary input pairs under the frozen v63 recipe."""
from functools import lru_cache
import hashlib
from pathlib import Path
from threading import Lock

import numpy as np

from .paired_features_v69 import MODEL, REVISION, VERSION, CONTRACT_REF, crop_boxes, query_plan, normalized, statistics, digest


def fingerprint(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def encoder_spec(identity):
    return {key: identity[key] for key in ('model', 'revision', 'files', 'backend', 'dtype', 'torch', 'transformers', 'feature_contract')}


class PairedVisionEncoder:
    """Serializes GPU work, caches preprocessing only, and binds each result."""
    def __init__(self, snapshot, expected_identity):
        import torch
        import transformers
        from transformers import AutoModel, AutoProcessor
        snapshot = Path(snapshot)
        self.identity = encoder_spec(expected_identity)
        if (self.identity['model'] != MODEL or self.identity['revision'] != REVISION or
                self.identity['feature_contract'] != CONTRACT_REF or self.identity['backend'] != 'mps' or
                self.identity['dtype'] != 'float32' or snapshot.name != REVISION):
            raise ValueError('Changed frozen encoder recipe')
        if torch.__version__ != self.identity['torch'] or transformers.__version__ != self.identity['transformers'] or not torch.backends.mps.is_available():
            raise ValueError('The verified encoder versions and Metal backend are required')
        for name, expected in self.identity['files'].items():
            if fingerprint(snapshot / name) != expected:
                raise ValueError('Changed frozen encoder asset')
        self.torch, self.lock = torch, Lock()
        torch.set_num_threads(2)
        self.model = AutoModel.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_safetensors=True).to('mps').eval()
        self.processor = AutoProcessor.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_fast=False)

    @lru_cache(maxsize=2048)
    def _image(self, path, sha):
        from PIL import Image
        if fingerprint(path) != sha:
            raise ValueError('Image changed during extraction')
        with Image.open(path) as original:
            image = original.convert('RGB')
            crops = [image.crop(box) for box in crop_boxes(*image.size)]
        pixels = self.processor.image_processor(images=crops, return_tensors='pt')['pixel_values'].to('mps')
        vectors = self.model.get_image_features(pixel_values=pixels).cpu().float().numpy()
        return normalized(vectors).astype(np.float32)

    @lru_cache(maxsize=8192)
    def _text(self, text):
        tokens = self.processor.tokenizer([text], padding='max_length', max_length=64, truncation=True, return_tensors='pt')
        vector = self.model.get_text_features(input_ids=tokens['input_ids'].to('mps')).cpu().float().numpy()[0]
        return normalized(vector).astype(np.float32)

    def compute(self, program, evidence):
        if set(evidence) != {'source_image', 'edited_image'}:
            raise ValueError('Ordered source and edited image paths required')
        hashes = {key: fingerprint(path) for key, path in evidence.items()}
        pair = digest(['bound-physical-evidence-v2', 'source_first', hashes['source_image'], hashes['edited_image']])
        with self.lock, self.torch.inference_mode():
            source, edited = [self._image(str(evidence[key]), hashes[key]) for key in ('source_image', 'edited_image')]
            plan = query_plan(program)
            text = {'target': self._text(plan['target']), 'goal': self._text(plan['goal']),
                    'probes': [{'positive': self._text(p['positive']), 'negative': np.stack([self._text(s) for s in p['negative']])} for p in plan['probes']]}
            measured = statistics(source, edited, text)
        return {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'program_ref': program['program_ref'],
                'image_pair_ref': pair, 'encoder_spec_ref': digest(self.identity), 'measurements': measured}
