"""Extract fixed rubric concepts locally; no paid model calls or pixel uploads."""
import argparse
from pathlib import Path
import time

import numpy as np

from critical.core.decision import nli_rubric_v81 as nli
from critical.core.decision.artifacts import digest
from run.calitree_grounded_regions_v77 import ROOT,read,save,sha

FROZEN=ROOT/'logs/exps/261021-frozen-visual-policy-v69'


def prepare(out):
    if out.exists():raise ValueError('Fresh experiment directory required')
    entries=[]
    for r in read(FROZEN/'replay_inputs_without_references.json'):
        pair=r['observation']['image_pair_ref'] if r['observation'] else None
        entries.append({'case':r['case'],'program_ref':r['program']['program_ref'],'image_pair_ref':pair,
            'plans':nli.plans(r['program'],r['observation'],pair,r['judgment'])})
    protocol={'version':nli.VERSION,'contract_ref':nli.CONTRACT_REF,'model':nli.MODEL,'revision':nli.REVISION,
        'cases':len(entries),'unique_sentence_pairs':len({digest([p['premise'],p['hypothesis']]) for e in entries for p in e['plans']}),
        'max_tokens':384,'dtype':'float32','backend':'mps','batch_size':16,
        'scope':'Fixed semantic claims about text. Frozen public NLI model; zero fitting and no human grades in extraction.',
        'limits':'No new image observation; cannot by itself fix a hallucinated image description. Language entailment support is not factual confidence.',
        'new_api_calls':0,'uploads':0,'reserved_sources_used':0}
    out.mkdir(parents=True);save(out/'protocol.json',protocol);save(out/'inputs_without_labels.json',entries)
    code=[Path(__file__),Path(nli.__file__)]
    save(out/'manifest.json',{'protocol_ref':digest(protocol),'inputs_ref':digest(entries),'code_sha256':{str(p):sha(p) for p in code}})
    for p in code:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    (out/'run.log').write_text('Prepared fixed language-rubric concept extraction.\n');(out/'llm-histories.log').write_text('No API calls. Local NLI score histories are saved as per-case artifacts.\n')
    print(protocol,flush=True)


def extract(out):
    import torch,transformers
    from transformers import AutoTokenizer,AutoModelForSequenceClassification
    protocol,manifest=read(out/'protocol.json'),read(out/'manifest.json');entries=read(out/'inputs_without_labels.json')
    assert digest(protocol)==manifest['protocol_ref'] and digest(entries)==manifest['inputs_ref'] and protocol['contract_ref']==nli.CONTRACT_REF
    for p,h in manifest['code_sha256'].items():assert sha(p)==h,p
    identity=read('/tmp/calitree-vision-v63/nli_identity.json');snapshot=Path(identity['snapshot_path'])
    assert identity['model']==nli.MODEL and identity['revision']==snapshot.name==nli.REVISION
    for name,h in identity['files'].items():assert sha(snapshot/name)==h,name
    assert torch.backends.mps.is_available()
    identity={**identity,'snapshot_path':'pinned-local-cache','backend':'mps','dtype':'float32','torch':torch.__version__,'transformers':transformers.__version__,
        'contract_ref':nli.CONTRACT_REF,'code_sha256':manifest['code_sha256']}
    if (out/'identity.json').exists():assert read(out/'identity.json')==identity
    else:save(out/'identity.json',identity)
    torch.set_num_threads(2)
    tokenizer=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True,trust_remote_code=False)
    model=AutoModelForSequenceClassification.from_pretrained(str(snapshot),local_files_only=True,trust_remote_code=False,use_safetensors=True).to('mps').eval()
    expected={0:'contradiction',1:'entailment',2:'neutral'}
    assert {int(k):v.lower() for k,v in model.config.id2label.items()}==expected,model.config.id2label
    cache=ROOT/'logs/cache/nli-rubric-v81'/digest(identity);cache.mkdir(parents=True,exist_ok=True)
    unique={digest([p['premise'],p['hypothesis']]):p for e in entries for p in e['plans']}
    pending=[(key,p) for key,p in sorted(unique.items()) if not (cache/(key+'.json')).exists()]
    started=time.monotonic()
    with torch.inference_mode():
        for start in range(0,len(pending),protocol['batch_size']):
            batch=pending[start:start+protocol['batch_size']]
            tokens=tokenizer([p['premise'] for _,p in batch],[p['hypothesis'] for _,p in batch],padding=True,truncation='longest_first',max_length=protocol['max_tokens'],return_tensors='pt')
            tokens={k:v.to('mps') for k,v in tokens.items()};support=model(**tokens).logits.softmax(dim=-1).cpu().float().numpy()
            for (key,p),values in zip(batch,support):save(cache/(key+'.json'),{'pair_ref':key,'support':values.tolist()})
            if start%512==0:print({'completed_pairs':min(start+len(batch),len(pending)),'pending_pairs':len(pending),'seconds':round(time.monotonic()-started,1)},flush=True)
    for e in entries:
        rows=[]
        for p in e['plans']:
            key=digest([p['premise'],p['hypothesis']]);rows.append({'context':p['context'],'concept':p['concept'],'pair_ref':key,'support':read(cache/(key+'.json'))['support']})
        save(out/'cases'/(e['case']+'.json'),{'case':e['case'],'program_ref':e['program_ref'],'image_pair_ref':e['image_pair_ref'],
            'identity_ref':digest(identity),'features':nli.features(rows),'trace':rows})
    result={'cases':len(entries),'unique_pairs':len(unique),'new_inferences':len(pending),'seconds':time.monotonic()-started,'new_api_calls':0,'uploads':0,'reserved_sources_used':0}
    save(out/'results.json',result);(out/'run.log').write_text('Completed fixed local semantic concept extraction: '+str(result)+'\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    m=p.add_mutually_exclusive_group(required=True);m.add_argument('--prepare',action='store_true');m.add_argument('--extract',action='store_true')
    a=p.parse_args();prepare(a.output_dir.resolve()) if a.prepare else extract(a.output_dir.resolve())
