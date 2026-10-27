"""Fit-source-only smoke of the already cached, frozen grounding detector."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import torch
from PIL import Image
from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection


def run(out):
    if out.exists():raise ValueError('Fresh smoke directory required')
    root=Path(__file__).resolve().parents[1]
    identity=json.loads(Path('/tmp/calitree-vision-v63/detector_identity.json').read_text())
    snapshot=Path(identity['snapshot_path'])
    assert identity['model']=='IDEA-Research/grounding-dino-tiny' and identity['revision']=='a2bb814dd30d776dcf7e30523b00659f4f141c71'
    entries=json.loads((root/'logs/exps/261021-frozen-visual-policy-v69/replay_inputs_without_references.json').read_text())
    sample=next(r for r in entries[:99] if 'clevr' in r['evidence']['source_image'])
    out.mkdir(parents=True)
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir() if p.is_file()}
    device='mps' if torch.backends.mps.is_available() else 'cpu';torch.set_num_threads(2)
    save('protocol.json',{'model':identity['model'],'revision':identity['revision'],'file_sha256':files,
         'device':device,'dtype':'float32','case':sample['case'],'scope':'One original fitting source; no references, validation sources or API calls.',
         'captions':['purple sphere.','sphere.'],'threshold':.2,'text_threshold':.2,'local_files_only':True})
    (out/'run.log').write_text('Cached native grounding detector smoke in progress; no network access.\n')
    (out/'llm-histories.log').write_text('Zero API calls. Frozen local detector only.\n')
    processor=AutoProcessor.from_pretrained(str(snapshot),local_files_only=True)
    model=AutoModelForZeroShotObjectDetection.from_pretrained(str(snapshot),local_files_only=True,use_safetensors=True)
    model.config.disable_custom_kernels=True;model=model.to(device).eval()
    rows=[]
    with torch.inference_mode():
        for caption in ('purple sphere.','sphere.'):
            for side in ('source_image','edited_image'):
                image=Image.open(sample['evidence'][side]).convert('RGB')
                batch=processor(images=image,text=caption,return_tensors='pt')
                batch={k:v.to(device) for k,v in batch.items()}
                start=time.monotonic();outputs=model(**batch)
                result=processor.post_process_grounded_object_detection(outputs,batch['input_ids'],threshold=.2,
                            text_threshold=.2,target_sizes=[(image.height,image.width)])[0]
                row={'side':side,'caption':caption,'image_size':[image.width,image.height],
                     'boxes':result['boxes'].cpu().tolist(),'scores':result['scores'].cpu().tolist(),
                     'labels':result.get('text_labels',result.get('labels')),'seconds':time.monotonic()-start}
                rows.append(row);save('detections.json',rows)
                print(row,flush=True)
    save('verification.json',{'inferences':4,'reference_labels_used':False,'new_api_calls':0,
                             'postprocessing_api':'threshold keyword verified against installed Transformers4.57.6'})
    (out/'run.log').write_text('Completed four local frozen detections on one original fitting source; corrected the installed postprocessing threshold keyword. No accuracy or factual-grounding guarantee inferred.\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    run(parser.parse_args().output_dir.resolve())
