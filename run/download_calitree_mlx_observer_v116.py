"""Pin a compact public MLX vision checkpoint without uploading task data."""
import argparse
from pathlib import Path
import shutil

from huggingface_hub import HfApi, snapshot_download

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash

MODEL='mlx-community/Qwen3.5-9B-4bit'
REVISION='8b2b98c00a6b4d291155e4890773ca8f769aee53'
WEIGHT_BYTES=5950221072


def download(out,destination):
    if out.exists():
        raise ValueError('Fresh download evidence directory required')
    destination.mkdir(parents=True,exist_ok=True);free=shutil.disk_usage(destination).free
    if free<=WEIGHT_BYTES+12*1024**3:
        raise ValueError('Preserve at least12GiB for runtime, operating system and ongoing collection')
    out.mkdir(parents=True);(out/'run.log').write_text('Pinned public MLX checkpoint download started. No inference, credentials or project payload.\n');(out/'llm-histories.log').write_text('No LLM/API calls. Public model/configuration files only; no task data uploaded.\n')
    info=HfApi(token=False).model_info(MODEL,revision=REVISION,files_metadata=True);assert info.sha==REVISION
    weights={f.rfilename:f.size for f in info.siblings if f.rfilename.endswith('.safetensors')};assert sum(weights.values())==WEIGHT_BYTES
    identity={'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'weights':weights,'destination':str(destination),
        'trust_remote_code':False,'authentication':False,'upstream_model_card':'https://huggingface.co/'+MODEL,'upstream_base_model':'Qwen/Qwen3.5-9B',
        'conversion_library':'mlx-vlm0.3.12','quantization':{'bits':4,'group_size':64,'mode':'affine'},'free_bytes_before':free,'status':'downloading'}
    save_json(out/'identity.json',identity)
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);shutil.copyfile(__file__,snapshot)
    snapshot_download(MODEL,revision=REVISION,token=False,local_dir=str(destination),max_workers=2,
        allow_patterns=['*.json','*.jinja','*.txt','*.safetensors','LICENSE','README.md'])
    for name,size in weights.items():
        assert (destination/name).stat().st_size==size
    hashes={p.name:file_hash(p) for p in destination.iterdir() if p.is_file()};identity.update(status='complete',file_sha256=hashes)
    save_json(out/'identity.json',identity);save_json(out/'manifest.json',{'downloader_sha256':file_hash(__file__),'file_sha256':hashes})
    (out/'run.log').write_text('Public checkpoint downloaded and all local file hashes recorded. No task uploads or model inference performed.\n')
    print({'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'destination':str(destination),'status':'complete'},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();download(a.output_dir.resolve(),a.destination.resolve())
