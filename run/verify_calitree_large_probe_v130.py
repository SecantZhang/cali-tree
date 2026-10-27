"""Audit32B local observations and the paired original-training diagnostic."""
import argparse
from collections import Counter
from importlib.metadata import distribution,version
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bounded_local_schema_v131 import schema as bounded_schema
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine,MODEL,REVISION,MEMORY_LIMIT
from critical.lm_engine.local_qwen_v94 import parse_json,file_hash,local_messages
from run.verify_calitree_mlx_probe_v120 import read,warrant


def validate(job,response,profile):
    expected=bounded_schema() if profile.get('evidence_max_chars')==360 else facts.schema()
    if (job['request_ref']!=digest({k:v for k,v in job.items() if k!='request_ref'}) or response.get('request_ref')!=job['request_ref'] or response.get('case')!=job['case'] or
            job['identity_ref']!=digest(profile) or job['schema']!=expected or job['prompt_ref']!=digest(job['prompt'])):
        raise ValueError('Changed32B observation request')
    raw=response.get('response')
    if raw is not None:
        if raw['engine']!=LargeMLXEngine.name or raw['model']!=MODEL or raw['endpointHost']!='local-mlx':raise ValueError('Different/remote observation engine')
        if any(type(raw[k]) is not int or raw[k]<0 for k in('promptTokens','completionTokens','totalTokens')) or raw['promptTokens']+raw['completionTokens']!=raw['totalTokens'] or raw['completionTokens']>profile['max_new_tokens']:
            raise ValueError('Invalid native token accounting')
        if parse_json(raw['content'])!=raw['parsed']:raise ValueError('Raw observation was repaired/replaced')
    if response.get('record') is not None:
        if raw is None or raw['finishReason']!='stop' or response.get('error') is not None:raise ValueError('Failed/truncated record accepted')
        if response['observation']!=raw['parsed'] or response['record']['observation']!=raw['parsed']:raise ValueError('Bound observation differs from raw output')
        facts.project(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],response['record'])
        if profile.get('evidence_max_chars')==360 and not 1<=len(raw['parsed']['evidence'])<=360:raise ValueError('Bounded evidence exceeds the frozen schema')
        if not 0<raw['peakMemoryBytes']<=MEMORY_LIMIT:raise ValueError('Observed32B memory bound exceeded')
        return True
    if response.get('observation') is not None or not isinstance(response.get('error'),str) or not response['error']:raise ValueError('Unavailable record must remain an explicit failure')
    return False


def audit(probe,previous,checkpoint,out,require_complete=False,require_terminal=False):
    if out.exists():raise ValueError('Fresh32B diagnostic audit required')
    manifest=read(probe/'manifest.json');profile=read(probe/'identity.json');jobs=read(probe/'jobs.json');protocol=read(probe/'protocol.json');references=read(probe/'references.json')
    if protocol['version']=='large-bounded-local-observer-v131':assert profile['evidence_max_chars']==360;expected_schema=bounded_schema()
    else:assert protocol['version']=='large-local-observer-diagnostic-v129' and 'evidence_max_chars' not in profile;expected_schema=facts.schema()
    assert profile['model']==MODEL and profile['revision']==REVISION and profile['engine']==LargeMLXEngine.name and profile['memory_limit_bytes']==MEMORY_LIMIT
    assert profile['max_new_tokens']==512 and profile['max_pixels_per_image']==256*32*32 and not profile['do_sample'] and not profile['enable_thinking']
    assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(protocol)==manifest['protocol_ref']
    assert profile['schema_ref']==digest(expected_schema) and profile['contract_ref']==facts.CONTRACT_REF
    assert len(jobs)==12 and Counter(references.values())=={0:4,1:4,2:4} and set(references)=={j['case'] for j in jobs}
    assert protocol['bounds']=={'workers':1,'max_local_inferences':12,'max_new_tokens':6144,'retries':0}
    assert file_hash(checkpoint)==manifest['checkpoint_identity_sha256'] and digest(read(checkpoint))==profile['checkpoint_ref']
    source_hashes={}
    for path,sha in{**manifest['code_sha256'],**manifest['source_hashes']}.items():assert file_hash(path)==sha;source_hashes[path]=sha
    for name,expected in profile['packages'].items():assert version(name)==expected
    for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
    old_jobs={j['case']:j for j in read(previous/'jobs.json')};assert references==read(previous/'references.json')
    response_paths={p.stem:p for p in(probe/'responses').glob('*.json')};attempt_paths={p.stem:p for p in(probe/'attempts').glob('*.json')}
    assert set(response_paths)<=set(attempt_paths)<=set(references)
    terminal=read(probe/'results.json') if(probe/'results.json').exists() else None
    if require_terminal:assert terminal is not None,'Collector is not terminal'
    complete=len(response_paths)==12
    if require_complete:assert complete,'Incomplete32B diagnostic'
    history=[]
    for line in(probe/'llm-histories.log').read_text().splitlines(keepends=True):
        if not line.endswith('\n'):continue
        h=__import__('json').loads(line);assert h['engine']==LargeMLXEngine.name and h['model']==MODEL and h['endpoint_host']=='local-mlx' and h['remote_calls']==0
        assert h['checkpoint_revision']==REVISION and h['max_new_tokens']==512 and h['memory_limit_bytes']==MEMORY_LIMIT and not h['do_sample'] and not h['enable_thinking'];history.append(h)
    counts=Counter((h['prompt'],h.get('response'),h['prompt_tokens'],h['completion_tokens']) for h in history)
    from transformers import AutoProcessor
    identity=read(checkpoint);processor=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False,use_fast=True)
    processor.image_processor.size={'longest_edge':profile['max_pixels_per_image'],'shortest_edge':profile['min_pixels_per_image']}
    accepted=tokens=reserved=replays=0;rows=[];maximum=0
    for job in jobs:
        case=job['case'];old_job=old_jobs[case];assert all(job[k]==old_job[k] for k in('program','evidence','image_hashes','image_pair_ref','prompt','prompt_ref')) and job['schema']==expected_schema
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        old=read(previous/'responses'/(case+'.json'));facts.project(old_job['program'],pair,old_job['identity_ref'],old_job['prompt_ref'],old['record'])
        row={'case':case,'reference':references[case],'attempted':case in attempt_paths,'accepted':False,'old_warrant':warrant(job['program'],old['record']),'new_warrant':None}
        if case in attempt_paths:
            assert read(attempt_paths[case])=={'case':case,'request_ref':job['request_ref'],'status':'attempted'};source_hashes[str(attempt_paths[case])]=file_hash(attempt_paths[case])
        if case not in response_paths:
            if case in attempt_paths:reserved+=512
            rows.append(row);continue
        response=read(response_paths[case]);passed=validate(job,response,profile);row['accepted']=passed;accepted+=passed;raw=response.get('response')
        key=(job['prompt'],raw['content'] if raw else None,raw['promptTokens'] if raw else 0,raw['completionTokens'] if raw else 0)
        assert counts[key]>=1;counts[key]-=1;tokens+=raw['completionTokens'] if raw else 0;reserved+=0 if raw else 512
        if raw is not None:
            maximum=max(maximum,raw['peakMemoryBytes'])
            media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},{'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
            messages,_=local_messages(job['prompt'],media);rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            assert digest(rendered)==raw['renderedPromptRef']
            from PIL import Image
            images=[]
            for name in('source_image','edited_image'):
                with Image.open(job['evidence'][name]) as im:images.append(im.convert('RGB'))
            inputs=processor(text=[rendered],images=images,return_tensors='pt',padding=True)
            assert int(inputs['input_ids'].numel())==raw['promptTokens'] and{k:list(v.shape) for k,v in inputs.items()}==raw['inputShapes'];replays+=1
        row['new_warrant']=warrant(job['program'],response['record']);rows.append(row);source_hashes[str(response_paths[case])]=file_hash(response_paths[case])
    assert len(history)<=len(attempt_paths)<=12 and tokens+reserved<=6144
    if complete or require_terminal:
        assert terminal is not None and terminal['complete']==complete and terminal['attempts']==len(attempt_paths) and terminal['responses']==len(response_paths) and terminal['accepted']==accepted and terminal['completion_tokens']==tokens and terminal['reserved_completion_tokens']==reserved
        assert not any(counts.values())
    preflight=read(probe/'preflight.json');assert preflight['neural_calls']==0
    if response_paths:assert preflight['passed']
    result={'passed':True,'complete':complete,'terminal':terminal is not None,'snapshot_only':not(require_complete or require_terminal),'responses':len(response_paths),'attempts':len(attempt_paths),'accepted':accepted,
        'completion_tokens':tokens,'reserved_completion_tokens':reserved,'native_processor_replays':replays,'max_observed_mlx_bytes':maximum,
        'old_warranted':sum(r['old_warrant'] is not None for r in rows),'old_warrant_correct_of12':sum(r['old_warrant']==r['reference'] for r in rows),
        'new_warranted':sum(r['new_warrant'] is not None for r in rows) if complete else None,'new_warrant_correct_of12':sum(r['new_warrant']==r['reference'] for r in rows) if complete else None,
        'new_inference_calls':0,'new_api_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False,
        'scope':'Same balanced12 original-training inputs, not population or pipeline accuracy. Unwarranted/failed observations stay in the12-case denominator.'}
    out.mkdir(parents=True);save_json(out/'verification.json',result);save_json(out/'cases.json',rows)
    for folder in(probe,previous):
        for name in('manifest.json','identity.json','jobs.json','references.json'):source_hashes[str(folder/name)]=file_hash(folder/name)
    source_hashes[str(checkpoint)]=file_hash(checkpoint);save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'source_hashes':source_hashes})
    dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Large-model exact bindings, raw records, native processor inputs, histories and budgets audited. No fitting or pipeline accuracy claim.\n');(out/'llm-histories.log').write_text('No inference/API calls; CPU processor replay only.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('probe','previous-probe','checkpoint','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--require-complete',action='store_true');p.add_argument('--require-terminal',action='store_true');a=p.parse_args();audit(a.probe.resolve(),a.previous_probe.resolve(),a.checkpoint.resolve(),a.output_dir.resolve(),a.require_complete,a.require_terminal)
