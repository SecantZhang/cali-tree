"""Download an exact public safetensors checkpoint; never upload task data."""
import argparse
from hashlib import sha256
from pathlib import Path
import shutil

from huggingface_hub import HfApi, snapshot_download

from critical.core.decision.artifacts import save_json

MODEL = 'Qwen/Qwen3-VL-8B-Instruct'
REVISION = '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b'
EXPECTED_WEIGHT_BYTES = 17534339512


def fingerprint(path):
    result = sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def download(out, destination):
    if out.exists():
        raise ValueError('Fresh download evidence directory required')
    out.mkdir(parents=True); destination.mkdir(parents=True, exist_ok=True)
    (out/'run.log').write_text('Read-only public model download; no project payload or authentication sent.\n')
    (out/'llm-histories.log').write_text('Zero model inference/API calls. Only public Hugging Face model files are downloaded without authentication.\n')
    api = HfApi(token=False); info = api.model_info(MODEL, revision=REVISION, files_metadata=True)
    assert info.sha == REVISION
    weights = {f.rfilename: f.size for f in info.siblings if f.rfilename.endswith('.safetensors')}
    assert sum(weights.values()) == EXPECTED_WEIGHT_BYTES
    assert shutil.disk_usage(destination).free > EXPECTED_WEIGHT_BYTES+10*1024**3
    identity = {'model': MODEL, 'revision': REVISION, 'weight_bytes': EXPECTED_WEIGHT_BYTES, 'weights': weights,
                'destination': str(destination), 'trust_remote_code': False, 'authentication': False,
                'upstream_model_card': 'https://huggingface.co/'+MODEL, 'status': 'downloading'}
    save_json(out/'identity.json', identity)
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True); snapshot.write_bytes(Path(__file__).read_bytes())
    snapshot_download(MODEL, revision=REVISION, token=False, local_dir=str(destination), max_workers=2,
                      allow_patterns=['*.json', '*.jinja', '*.txt', '*.safetensors', 'LICENSE', 'README.md'])
    for name, size in weights.items():
        assert (destination/name).stat().st_size == size
    hashes = {p.name: fingerprint(p) for p in destination.iterdir() if p.is_file()}
    identity['status'] = 'complete'; identity['file_sha256'] = hashes; save_json(out/'identity.json', identity)
    save_json(out/'manifest.json', {'downloader_sha256': fingerprint(__file__), 'file_sha256': hashes})
    (out/'run.log').write_text('Pinned public checkpoint downloaded and every file SHA256 recorded. No project data uploaded or model inference performed.\n')
    print({'model': MODEL, 'revision': REVISION, 'weight_bytes': EXPECTED_WEIGHT_BYTES, 'destination': str(destination), 'status': 'complete'}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--destination', type=Path, required=True)
    a = p.parse_args(); download(a.output_dir.resolve(), a.destination.resolve())
