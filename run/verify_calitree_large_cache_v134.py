"""Audit fixed32B review-cache selection, native records, reuse and budgets.

The unchanged teacher/source masks reuse the hash-pinned complete36-model v98
audit. New observer inputs/outputs and model/profile bindings are checked here.
"""
import argparse
from collections import Counter
from importlib.metadata import distribution,version
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bounded_local_schema_v131 import schema
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine,MODEL,REVISION,MEMORY_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash,local_messages
from run.verify_calitree_large_probe_v130 import validate,read


def audit(cache,out,require_complete=False):
    if out.exists():raise ValueError('Fresh large-cache audit required')
    manifest=read(cache/'manifest.json');profile=read(cache/'identity.json');jobs=read(cache/'jobs.json');members=read(cache/'memberships.json');protocol=read(cache/'protocol.json')
    assert profile['engine']==LargeMLXEngine.name and profile['model']==MODEL and profile['revision']==REVISION and profile['evidence_max_chars']==360 and profile['schema_ref']==digest(schema())
    assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(members)==manifest['memberships_ref'] and digest(protocol)==manifest['protocol_ref']
    assert len(jobs)==224 and protocol['bounds']=={'workers':1,'max_fresh_local_inferences':224,'max_new_tokens':114688,'retries':0}
    assert protocol['review_threshold']==.8
    for p,sha in manifest['code_sha256'].items():assert file_hash(p)==sha
    for name,expected in profile['packages'].items():assert version(name)==expected
    for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
    legacy=Path(manifest['legacy_cache']);legacy_audit=Path(manifest['legacy_audit']);probe=Path(manifest['probe']);probe_audit=Path(manifest['probe_audit'])
    source_hashes={}
    for p,sha in((legacy/'manifest.json',manifest['legacy_manifest_sha256']),(legacy_audit/'manifest.json',manifest['legacy_audit_manifest_sha256']),
                  (probe/'manifest.json',manifest['probe_manifest_sha256']),(probe_audit/'manifest.json',manifest['probe_audit_manifest_sha256'])):
        assert file_hash(p)==sha;source_hashes[str(p)]=sha
    verified=read(legacy_audit/'verification.json');assert verified['passed'] and verified['complete'] and not verified['snapshot_only'] and verified['native_models_checked']==36
    for path,sha in read(legacy_audit/'manifest.json')['source_hashes'].items():assert file_hash(path)==sha;source_hashes[path]=sha
    pv=read(probe_audit/'verification.json');assert pv['passed'] and pv['complete'] and pv['accepted']==12 and not pv['snapshot_only']
    for path,sha in read(probe_audit/'manifest.json')['source_hashes'].items():assert file_hash(path)==sha;source_hashes[path]=sha
    assert profile==read(probe/'identity.json') and members==read(legacy/'memberships.json')
    old_jobs=read(legacy/'jobs.json');old_manifest=read(legacy/'manifest.json')
    assert digest(old_jobs)==old_manifest['jobs_ref'] and digest(members)==old_manifest['memberships_ref']
    for before,after in zip(old_jobs,jobs):
        transformed={k:v for k,v in before.items() if k!='request_ref'};transformed.update(identity_ref=digest(profile),schema=schema());transformed['request_ref']=digest(transformed)
        assert transformed==after
    template=(cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text();assert digest(template)==manifest['template_ref']
    checkpoint=Path(__file__).resolve().parents[1]/'logs/exps/261023-large-mlx-download-v127-r1/identity.json'
    assert file_hash(checkpoint)==manifest['checkpoint_identity_sha256'] and digest(read(checkpoint))==profile['checkpoint_ref']
    histories=[]
    for line in(cache/'llm-histories.log').read_text().splitlines(keepends=True):
        if not line.endswith('\n'):continue
        h=__import__('json').loads(line);assert h['engine']==LargeMLXEngine.name and h['model']==MODEL and h['endpoint_host']=='local-mlx' and h['remote_calls']==0
        assert h['checkpoint_revision']==REVISION and h['max_new_tokens']==512 and h['max_pixels_per_image']==256*32*32 and h['memory_limit_bytes']==MEMORY_LIMIT and not h['do_sample'];histories.append(h)
    history=Counter((h['prompt'],h.get('response'),h['prompt_tokens'],h['completion_tokens']) for h in histories)
    responses={p.stem:p for p in(cache/'responses').glob('*.json')};attempts={p.stem:p for p in(cache/'attempts').glob('*.json')}
    assert set(responses)<=set(j['case'] for j in jobs) and set(attempts)<=set(j['case'] for j in jobs)
    from transformers import AutoProcessor
    import torch
    torch.set_num_threads(2)
    identity=read(checkpoint);processor=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False,use_fast=True)
    processor.image_processor.size={'longest_edge':256*32*32,'shortest_edge':64*32*32}
    prior_jobs={j['case']:j for j in read(probe/'jobs.json')};slots=[];accepted=reused=fresh_tokens=reserved=cpu_replays=0
    for job in jobs:
        case=job['case'];assert job['prompt']==facts.prompt(job['program'],template)
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        if case in attempts:
            assert read(attempts[case])=={'case':case,'request_ref':job['request_ref'],'status':'attempted'};source_hashes[str(attempts[case])]=file_hash(attempts[case])
        if case not in responses:
            if case in attempts:reserved+=512
            slots.append({'case':case,'status':'pending','attempted':case in attempts});continue
        response=read(responses[case]);passed=validate(job,response,profile);accepted+=passed;raw=response.get('response')
        if 'cache_origin' in response:
            origin=Path(response['cache_origin']);assert case not in attempts and origin==probe/'responses'/(case+'.json')
            assert prior_jobs[case]==job and file_hash(origin)==response['cache_origin_sha256']
            assert{k:v for k,v in response.items() if k not in('cache_origin','cache_origin_sha256')}==read(origin);reused+=1;source_hashes[str(origin)]=file_hash(origin)
        else:
            assert case in attempts
            key=(job['prompt'],raw['content'] if raw else None,raw['promptTokens'] if raw else 0,raw['completionTokens'] if raw else 0)
            assert history[key]>=1;history[key]-=1;fresh_tokens+=raw['completionTokens'] if raw else 0;reserved+=0 if raw else 512
        if raw is not None:
            media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},{'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
            messages,_=local_messages(job['prompt'],media);rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            assert digest(rendered)==raw['renderedPromptRef']
            from PIL import Image
            images=[]
            for key in('source_image','edited_image'):
                with Image.open(job['evidence'][key]) as im:images.append(im.convert('RGB'))
            native=processor(text=[rendered],images=images,return_tensors='pt',padding=True)
            assert int(native['input_ids'].numel())==raw['promptTokens'] and{k:list(v.shape) for k,v in native.items()}==raw['inputShapes'];cpu_replays+=1
        source_hashes[str(responses[case])]=file_hash(responses[case]);slots.append({'case':case,'status':'accepted' if passed else 'failed','reused':'cache_origin' in response})
    complete=len(responses)==224
    assert len(attempts)<=224 and len(histories)<=len(attempts) and fresh_tokens+reserved<=114688
    if require_complete:
        assert complete,'Large observer cache is incomplete'
        terminal=read(cache/'results.json');assert terminal['complete'] and terminal['responses']==224 and terminal['fresh_attempts']==len(attempts) and terminal['reused']==reused and terminal['accepted']==accepted and terminal['fresh_completion_tokens']==fresh_tokens and terminal['reserved_completion_tokens']==reserved
        assert not any(history.values())
    out.mkdir(parents=True);result={'passed':True,'complete':complete,'snapshot_only':not require_complete,'responses_checked':len(responses),'accepted':accepted,'reused':reused,'fresh_attempts':len(attempts),
        'fresh_completion_tokens':fresh_tokens,'reserved_completion_tokens':reserved,'native_processor_replays':cpu_replays,'native_teacher_models_reused':36,'source_masks_unchanged':True,
        'new_inference_calls':0,'new_api_calls':0,'reserved_sources_used':0,'fitting_performed':False,'accuracy_claim':False}
    save_json(out/'verification.json',result);save_json(out/'slots.json',slots)
    for name in('manifest.json','identity.json','jobs.json','memberships.json','protocol.json','llm-histories.log'):source_hashes[str(cache/name)]=file_hash(cache/name)
    source_hashes[str(checkpoint)]=file_hash(checkpoint);source_hashes[str(cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt')]=file_hash(cache/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt')
    save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'cache_manifest_sha256':file_hash(cache/'manifest.json'),'source_hashes':source_hashes})
    dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Unchanged source/fold masks and new bounded32B bindings/native processor outputs/accounting audited. Partial snapshots never permit fitting.\n');(out/'llm-histories.log').write_text('No neural/API calls. Existing native-teacher audit reused by hashes; CPU processor replay only.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--require-complete',action='store_true');a=p.parse_args();audit(a.cache.resolve(),a.output_dir.resolve(),a.require_complete)
