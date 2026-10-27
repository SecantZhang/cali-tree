"""Fetch a pinned32B public MLX checkpoint after completed-cache eviction."""
import argparse
from pathlib import Path
import shutil

from huggingface_hub import HfApi,snapshot_download

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash

MODEL='mlx-community/Qwen3-VL-32B-Instruct-4bit'
REVISION='6e5644d3ea4b953b5221ffd02339bf897041038a'
WEIGHT_BYTES=19620448683


def download(out,destination):
    if out.exists():raise ValueError('Fresh large-model download evidence required')
    destination.mkdir(parents=True,exist_ok=True);free=shutil.disk_usage(destination).free
    if free<=WEIGHT_BYTES+12*1024**3:raise ValueError('Retain12GiB beyond the full pinned checkpoint size')
    out.mkdir(parents=True);(out/'run.log').write_text('Pinned public32B MLX checkpoint download started. No inference, task data or credentials sent.\n');(out/'llm-histories.log').write_text('No model/API calls; public safetensors/configuration download only.\n')
    info=HfApi(token=False).model_info(MODEL,revision=REVISION,files_metadata=True);assert info.sha==REVISION
    weights={f.rfilename:f.size for f in info.siblings if f.rfilename.endswith('.safetensors')};assert sum(weights.values())==WEIGHT_BYTES
    identity={'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'weights':weights,'destination':str(destination),
        'trust_remote_code':False,'authentication':False,'quantization':{'bits':4,'group_size':64,'mode':'affine'},
        'upstream_model_card':'https://huggingface.co/'+MODEL,'upstream_base_model':'Qwen/Qwen3-VL-32B-Instruct',
        'free_bytes_before':free,'status':'downloading','planned_memory_guideline_bytes':24*1024**3}
    save_json(out/'identity.json',identity);dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    snapshot_download(MODEL,revision=REVISION,token=False,local_dir=str(destination),max_workers=2,
        allow_patterns=['*.json','*.jinja','*.txt','*.safetensors','LICENSE','README.md'])
    for name,size in weights.items():assert (destination/name).stat().st_size==size
    hashes={p.name:file_hash(p) for p in destination.iterdir() if p.is_file()};identity.update(status='complete',file_sha256=hashes)
    save_json(out/'identity.json',identity);save_json(out/'manifest.json',{'downloader_sha256':file_hash(__file__),'file_sha256':hashes})
    (out/'run.log').write_text('Pinned public32B checkpoint downloaded; every file hashed. No model calls or project uploads.\n')
    print({'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'status':'complete','destination':str(destination)},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();download(a.output_dir.resolve(),a.destination.resolve())
