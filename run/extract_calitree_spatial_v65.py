"""Encode missing entity captions locally and project requested relative geometry."""
import argparse
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoProcessor

from run.extract_calitree_paired_vision_v63 import read, fingerprint, save, array_save
from run.paired_vision_features_v63 import normalized, digest, REVISION
from run.spatial_vision_features_v65 import statistics, CONTRACT_REF


def extract(out, snapshot):
    protocol, manifest = read(out / 'protocol.json'), read(out / 'manifest.json')
    assert snapshot.name == REVISION and protocol['contract_ref'] == CONTRACT_REF
    assert fingerprint(out / 'inputs_without_labels.json') == manifest['inputs_sha256']
    for p, expected in manifest['code_hashes'].items():
        assert fingerprint(p) == expected
    parent = Path(protocol['parent'])
    assert fingerprint(parent / 'manifest.json') == manifest['parent_manifest_sha256']
    assert fingerprint(parent / 'inputs_without_labels.json') == manifest['parent_inputs_sha256']
    identity = read(parent / 'encoder_identity.json')
    assert digest(identity) == protocol['parent_encoder_ref']
    assert fingerprint(snapshot / 'model.safetensors') == identity['files']['model.safetensors']
    cache = parent / 'encoder_cache' / protocol['parent_encoder_ref']
    entries = read(out / 'inputs_without_labels.json')
    texts = {p[key] for e in entries for p in e['probes'] for key in ('target', 'reference') if key in p}
    needed = [text for text in sorted(texts) if not (cache / 'texts' / (digest(text) + '.npy')).exists()]
    local_cache = out / 'text_cache'
    needed = [text for text in needed if not (local_cache / (digest(text) + '.npy')).exists()]
    if needed:
        assert torch.backends.mps.is_available()
        torch.set_num_threads(2)
        model = AutoModel.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_safetensors=True).to('mps').eval()
        processor = AutoProcessor.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False, use_fast=False)
        with torch.inference_mode():
            for offset in range(0, len(needed), 32):
                selected = needed[offset:offset + 32]
                inputs = processor.tokenizer(selected, padding='max_length', max_length=64, truncation=True, return_tensors='pt')
                vectors = model.get_text_features(input_ids=inputs['input_ids'].to('mps')).cpu().float().numpy()
                for text, vector in zip(selected, normalized(vectors).astype(np.float32)):
                    array_save(local_cache / (digest(text) + '.npy'), vector)
    def text_vector(text):
        previous = cache / 'texts' / (digest(text) + '.npy')
        return np.load(previous if previous.exists() else local_cache / (digest(text) + '.npy'), allow_pickle=False)
    images = read(parent / 'manifest.json')['image_hashes']
    for e in entries:
        target = out / 'cases' / (e['case'] + '.json')
        if target.exists():
            continue
        source, edited = [np.load(cache / 'images' / (images[e['evidence'][key]] + '.npy'), allow_pickle=False) for key in ('source_image', 'edited_image')]
        embedded = []
        for probe in e['probes']:
            value = {**probe, 'target_vector': text_vector(probe['target'])}
            if 'reference' in probe:
                value['reference_vector'] = text_vector(probe['reference'])
            embedded.append(value)
        save(target, {'case': e['case'], 'parent_encoder_ref': protocol['parent_encoder_ref'], 'contract_ref': CONTRACT_REF,
                      'scores': statistics(source, edited, embedded)})
    report = {'cases': len(entries), 'spatial_probe_cases': sum(bool(e['probes']) for e in entries),
              'new_text_queries': len(needed), 'image_encodings_reused': True, 'new_paid_model_calls': 0, 'reserved_sources_used': 0}
    save(out / 'results.json', report)
    with (out / 'run.log').open('a') as handle:
        handle.write(str(report) + '\n')
    print(report, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    args = parser.parse_args()
    extract(args.output_dir.resolve(), args.model_dir.resolve())
