"""Prepare/extract label-blind caption audits using existing local image vectors."""
import argparse
from pathlib import Path
import time

import numpy as np

from critical.vision import caption_audit_v79 as audit
from critical.vision.paired_features_v69 import digest,normalized
from run.calitree_grounded_regions_v77 import ROOT,VISION,read,save,sha

FROZEN=ROOT/'logs/exps/261021-frozen-visual-policy-v69'


def prepare(out):
    if out.exists():raise ValueError('Fresh output directory required')
    image_inputs={r['case']:r for r in read(VISION/'inputs_without_labels.json')}
    entries=[];strings=set()
    for r in read(FROZEN/'replay_inputs_without_references.json'):
        pair=r['observation']['image_pair_ref'] if r['observation'] else None
        rows=audit.plan(r['program'],r['observation'],pair)
        entries.append({'case':r['case'],'program_ref':r['program']['program_ref'],'image_pair_ref':pair,
            'evidence':image_inputs[r['case']]['evidence'],'plan':rows})
        for row in rows:strings.update(row[k] for k in ('goal','source_description','edited_description'))
    protocol={'version':audit.VERSION,'contract_ref':audit.CONTRACT_REF,'cases':len(entries),'unique_texts':len(strings),
        'input':'Bound questions and raw source/edited descriptions, stripped of all observation state and grade fields.',
        'vision':'Reuse pinned SigLIP2 image vectors, encode only new texts locally, same64-token recipe.',
        'scalar_inputs':'Per-role image/goal affinity, own/cross-description affinity and paired change alignment; min/mean over distinct checks.',
        'no_truth_claim':'A local model audit view; no grade from embedding affinity alone.',
        'new_api_calls':0,'image_uploads':0,'reserved_sources_used':0,'model_downloads':0}
    out.mkdir(parents=True);save(out/'protocol.json',protocol);save(out/'inputs_without_labels.json',entries)
    code=[Path(__file__),Path(audit.__file__)]
    save(out/'manifest.json',{'protocol_ref':digest(protocol),'inputs_ref':digest(entries),
        'image_hashes':read(VISION/'manifest.json')['image_hashes'],'encoder_identity':read(VISION/'encoder_identity.json'),
        'code_sha256':{str(p):sha(p) for p in code}})
    for p in code:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    (out/'run.log').write_text('Prepared label-free caption audit.\n');(out/'llm-histories.log').write_text('Zero API calls; cached local encoder only.\n')
    print(protocol,flush=True)


def extract(out):
    import torch
    from critical.vision.paired_encoder_v69 import PairedVisionEncoder
    protocol,manifest=read(out/'protocol.json'),read(out/'manifest.json');entries=read(out/'inputs_without_labels.json')
    assert digest(protocol)==manifest['protocol_ref'] and digest(entries)==manifest['inputs_ref']
    for p,h in manifest['code_sha256'].items():assert sha(p)==h,p
    assert protocol['contract_ref']==audit.CONTRACT_REF
    encoder=PairedVisionEncoder(read('/tmp/calitree-vision-v63/model_identity.json')['snapshot_path'],manifest['encoder_identity'])
    cache=VISION/'encoder_cache'/digest(manifest['encoder_identity'])
    identity={'encoder':manifest['encoder_identity'],'contract_ref':audit.CONTRACT_REF,'code_sha256':manifest['code_sha256']}
    if (out/'identity.json').exists():assert read(out/'identity.json')==identity
    else:save(out/'identity.json',identity)
    strings=sorted({r[k] for e in entries for r in e['plan'] for k in ('goal','source_description','edited_description')})
    pending=[t for t in strings if not (cache/'texts'/(digest(t)+'.npy')).exists()]
    started=time.monotonic()
    with torch.inference_mode():
        for start in range(0,len(pending),32):
            batch=pending[start:start+32]
            tokens=encoder.processor.tokenizer(batch,padding='max_length',max_length=64,truncation=True,return_tensors='pt')
            vectors=normalized(encoder.model.get_text_features(input_ids=tokens['input_ids'].to('mps')).cpu().float().numpy()).astype(np.float32)
            for text,vector in zip(batch,vectors):
                path=cache/'texts'/(digest(text)+'.npy');temporary=path.with_suffix('.tmp')
                with temporary.open('wb') as handle:np.save(handle,vector,allow_pickle=False)
                temporary.replace(path)
            if start%320==0:print({'encoded':min(start+32,len(pending)),'pending_texts':len(pending),'seconds':round(time.monotonic()-started,1)},flush=True)
    def vector(text):return np.load(cache/'texts'/(digest(text)+'.npy'),allow_pickle=False)
    verified=set()
    for entry in entries:
        file=out/'cases'/(entry['case']+'.json')
        if file.exists():assert read(file)['identity_ref']==digest(identity);continue
        hashes=[]
        for kind in ('source_image','edited_image'):
            path=entry['evidence'][kind];expected=manifest['image_hashes'][path]
            if path not in verified:assert sha(path)==expected,path;verified.add(path)
            hashes.append(expected)
        pair=digest(['bound-physical-evidence-v2','source_first',*hashes])
        if entry['image_pair_ref']:assert pair==entry['image_pair_ref']
        source,edited=[np.load(cache/'images'/(h+'.npy'),allow_pickle=False) for h in hashes]
        scores,trace=audit.measure(source,edited,entry['plan'],vector)
        save(file,{'case':entry['case'],'version':audit.VERSION,'identity_ref':digest(identity),'program_ref':entry['program_ref'],
            'image_pair_ref':pair,'measurements':scores,'trace':trace})
    result={'cases':len(entries),'unique_texts':len(strings),'new_text_inferences':len(pending),'elapsed_seconds':time.monotonic()-started,
        'new_api_calls':0,'image_uploads':0,'reserved_sources_used':0}
    save(out/'results.json',result);(out/'run.log').write_text('Completed caption audit: '+str(result)+'\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    m=p.add_mutually_exclusive_group(required=True);m.add_argument('--prepare',action='store_true');m.add_argument('--extract',action='store_true')
    a=p.parse_args();prepare(a.output_dir.resolve()) if a.prepare else extract(a.output_dir.resolve())
