"""Hash the actual processor tensors under both frozen image-size budgets.

No model weights, encoder, neural inference or human references are loaded.
Equal token lengths alone are insufficient: pixel tensors and every processor
output must agree before an input is called identical.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.lm_engine.local_qwen_v94 import file_hash


def read(path):
    import json
    return json.loads(Path(path).read_text())


def tensor_refs(inputs):
    return {key:{'shape':list(tensor.shape),'dtype':str(tensor.dtype),'sha256':sha256(tensor.contiguous().numpy().tobytes()).hexdigest()} for key,tensor in inputs.items()}


def audit(previous,current,checkpoint,out):
    if out.exists():
        raise ValueError('Fresh input-tensor audit required')
    import torch
    from PIL import Image
    from transformers import AutoProcessor
    old_profile=read(previous/'identity.json');new_profile=read(current/'identity.json');identity=read(checkpoint)
    assert old_profile['checkpoint_ref']==new_profile['checkpoint_ref']==digest(identity)
    old_jobs=read(previous/'jobs.json');new_jobs=read(current/'jobs.json');assert len(old_jobs)==len(new_jobs)==224
    for cache,profile,jobs in ((previous,old_profile,old_jobs),(current,new_profile,new_jobs)):
        manifest=read(cache/'manifest.json');assert manifest['identity_ref']==digest(profile) and manifest['jobs_ref']==digest(jobs)
    processors=[]
    for profile in(old_profile,new_profile):
        p=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False)
        p.image_processor.size={'longest_edge':profile['max_pixels_per_image'],'shortest_edge':profile['min_pixels_per_image']};processors.append(p)
    torch.set_num_threads(2)
    out.mkdir(parents=True);(out/'run.log').write_text('Actual CPU processor tensor comparisons started. No model/encoder or reference reads.\n');(out/'llm-histories.log').write_text('No inference or API calls. Native image patchification/tokenization only.\n')
    snapshot=out/'source_snapshot/run'/Path(__file__).name;snapshot.parent.mkdir(parents=True);shutil.copyfile(__file__,snapshot)
    rows=[];source_hashes={}
    for before,after in zip(old_jobs,new_jobs):
        assert all(before[k]==after[k] for k in('case','evidence','image_hashes','image_pair_ref','program','prompt','schema'))
        images=[];sizes=[]
        for key in('source_image','edited_image'):
            path=Path(before['evidence'][key]);source_hashes[str(path)]=file_hash(path)
            with Image.open(path) as im:images.append(im.convert('RGB'));sizes.append(list(im.size))
        content=[{'type':'text','text':'SOURCE image'},{'type':'image'},{'type':'text','text':'EDITED image'},{'type':'image'},{'type':'text','text':before['prompt']}]
        outputs=[]
        for processor in processors:
            text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True)
            result=processor(text=[text],images=images,return_tensors='pt');outputs.append(tensor_refs(result))
        rows.append({'case':before['case'],'sizes':sizes,'old':outputs[0],'new':outputs[1],'identical':outputs[0]==outputs[1]})
        if len(rows)%32==0:
            save_json(out/'cases.json',rows);print({'processed':len(rows),'identical':sum(r['identical'] for r in rows)},flush=True)
    result={'passed':True,'cases':len(rows),'identical_complete_processor_outputs':sum(r['identical'] for r in rows),'different_processor_outputs':sum(not r['identical'] for r in rows),
        'different_cases':[r['case'] for r in rows if not r['identical']],'new_inference_calls':0,'human_references_read':0,'uploads':0,
        'scope':'Actual input tensors under the old/new pixel budgets. Equal tensors establish no added visual input for those cases; this does not prove equal stochastic/numerical model execution or accuracy.'}
    save_json(out/'cases.json',rows);save_json(out/'verification.json',result)
    for cache in(previous,current):
        for name in('jobs.json','identity.json','manifest.json'):source_hashes[str(cache/name)]=file_hash(cache/name)
    source_hashes[str(checkpoint)]=file_hash(checkpoint)
    save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'source_hashes':source_hashes,'checkpoint_ref':digest(identity)})
    (out/'run.log').write_text('All224 actual input tensor dictionaries compared without loading model weights or human references. See verification; no accuracy result.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('previous-cache','current-cache','checkpoint','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.previous_cache.resolve(),a.current_cache.resolve(),a.checkpoint.resolve(),a.output_dir.resolve())
