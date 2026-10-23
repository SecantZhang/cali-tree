"""Extract local frozen-encoder comparisons; no network access or labels needed.

Run in the isolated vision environment. The official checkpoint must already
be downloaded; safetensors/native model code and local_files_only are required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import torch
import transformers
from transformers import AutoModel, AutoProcessor

from run.paired_vision_features_v63 import MODEL, REVISION, CONTRACT_REF, digest, crop_boxes, normalized, statistics, predicates


def read(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
    temporary.replace(path)


def array_save(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as handle:
        np.save(handle, values, allow_pickle=False)
    temporary.replace(path)


def extract(out, snapshot):
    started = time.monotonic()
    protocol, manifest = read(out / 'protocol.json'), read(out / 'manifest.json')
    assert fingerprint(out / 'protocol.json') == manifest['protocol_sha256']
    assert fingerprint(out / 'inputs_without_labels.json') == manifest['inputs_sha256']
    assert protocol['model'] == MODEL and protocol['revision'] == REVISION and protocol['feature_contract_ref'] == CONTRACT_REF
    assert torch.__version__.split('+')[0] == protocol['torch_version'] and transformers.__version__ == protocol['transformers_version']
    assert torch.backends.mps.is_available() and protocol['backend'] == 'mps'
    assert snapshot.name == REVISION and snapshot.parent.name == 'snapshots'
    assert snapshot.parent.parent.name == 'models--google--siglip2-base-patch16-224'
    for p, sha in manifest['code_hashes'].items():
        assert fingerprint(p) == sha, p
    files = {p.name: fingerprint(p) for p in snapshot.iterdir() if p.is_file()}
    assert 'model.safetensors' in files and not any(name.endswith('.bin') for name in files)
    assert (snapshot / 'model.safetensors').resolve().name == files['model.safetensors']
    identity = {'model': MODEL, 'revision': REVISION, 'files': files, 'backend': 'mps', 'dtype': 'float32',
                'torch': torch.__version__, 'transformers': transformers.__version__, 'feature_contract': CONTRACT_REF,
                'code_hashes': manifest['code_hashes']}
    reference = digest(identity)
    identity_path = out / 'encoder_identity.json'
    if identity_path.exists():
        assert read(identity_path) == identity
    else:
        save(identity_path, identity)
    entries = read(out / 'inputs_without_labels.json')
    assert len(entries) == 915 and all(not {'reference', 'human_score', 'regular'} & set(e) for e in entries)
    torch.set_num_threads(2)
    model = AutoModel.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_safetensors=True).to('mps').eval()
    processor = AutoProcessor.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_fast=False)
    cache = out / 'encoder_cache' / reference
    cache.mkdir(parents=True, exist_ok=True)
    unique_images = {}
    for e in entries:
        for p in e['evidence'].values():
            sha = manifest['image_hashes'][p]
            assert fingerprint(p) == sha
            unique_images.setdefault(sha, p)
    with torch.inference_mode():
        for index, (sha, path) in enumerate(sorted(unique_images.items()), 1):
            target = cache / 'images' / (sha + '.npy')
            if not target.exists():
                with Image.open(path) as original:
                    image = original.convert('RGB')
                    crops = [image.crop(box) for box in crop_boxes(*image.size)]
                batch = processor.image_processor(images=crops, return_tensors='pt')['pixel_values'].to('mps')
                vectors = model.get_image_features(pixel_values=batch).cpu().float().numpy()
                array_save(target, normalized(vectors).astype(np.float32))
            if index % 25 == 0 or index == len(unique_images):
                print({'encoded_images': index, 'total_images': len(unique_images), 'elapsed_seconds': round(time.monotonic() - started, 1)}, flush=True)
        strings = set()
        for e in entries:
            plan = e['query_plan']
            strings.update([plan['target'], plan['goal']])
            for probe in plan['probes']:
                strings.update([probe['positive'], *probe['negative']])
        pending = [text for text in sorted(strings) if not (cache / 'texts' / (digest(text) + '.npy')).exists()]
        for offset in range(0, len(pending), 32):
            texts = pending[offset:offset + 32]
            inputs = processor.tokenizer(texts, padding='max_length', max_length=64, truncation=True, return_tensors='pt')
            vectors = model.get_text_features(input_ids=inputs['input_ids'].to('mps')).cpu().float().numpy()
            for text, vector in zip(texts, normalized(vectors).astype(np.float32)):
                array_save(cache / 'texts' / (digest(text) + '.npy'), vector)
        print({'encoded_text_queries': len(strings), 'elapsed_seconds': round(time.monotonic() - started, 1)}, flush=True)
    def text_vector(text):
        return np.load(cache / 'texts' / (digest(text) + '.npy'), allow_pickle=False)
    for e in entries:
        target = out / 'cases' / (e['case'] + '.json')
        if target.exists():
            assert read(target)['encoder_ref'] == reference
            continue
        source, edited = [np.load(cache / 'images' / (manifest['image_hashes'][e['evidence'][key]] + '.npy'), allow_pickle=False)
                          for key in ('source_image', 'edited_image')]
        plan = e['query_plan']
        text = {'target': text_vector(plan['target']), 'goal': text_vector(plan['goal']),
                'probes': [{'positive': text_vector(p['positive']), 'negative': np.stack([text_vector(s) for s in p['negative']])} for p in plan['probes']]}
        measured = statistics(source, edited, text)
        save(target, {'case': e['case'], 'encoder_ref': reference, 'measurements': measured, 'features': predicates(measured)})
    result = {'cases': len(entries), 'unique_images': len(unique_images), 'text_queries': len(strings), 'encoder_ref': reference,
              'elapsed_seconds': round(time.monotonic() - started, 1), 'new_paid_model_calls': 0, 'image_uploads': 0, 'reserved_sources_used': 0}
    save(out / 'results.json', result)
    with (out / 'run.log').open('a') as handle:
        handle.write('Completed local frozen-encoder extraction: ' + json.dumps(result) + '\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    args = parser.parse_args()
    extract(args.output_dir.resolve(), args.model_dir.resolve())
