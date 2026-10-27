"""Audit local MLX requests, raw records, budgets and training-only warrants."""
import argparse
from collections import Counter
from importlib.metadata import version,distribution
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.calibration.local_warranted_rubric_v97 import claims
from critical.lm_engine.local_qwen_v94 import parse_json,file_hash,local_messages
from critical.lm_engine.local_mlx_v118 import MODEL,REVISION,MEMORY_LIMIT


def read(path):
    import json
    return json.loads(Path(path).read_text())


def validate(job,response,profile):
    if (job.get('request_ref')!=digest({k:v for k,v in job.items() if k!='request_ref'}) or response.get('request_ref')!=job['request_ref'] or
            response.get('case')!=job['case'] or job['identity_ref']!=digest(profile) or job['prompt_ref']!=digest(job['prompt']) or job['schema']!=facts.schema()):
        raise ValueError('Changed observation request/binding')
    raw=response.get('response');engine=profile['engine']
    if engine not in('local_mlx_v118','local_qwen_grammar_v95'):raise ValueError('Unrecognized local observation engine')
    endpoint='local-mlx' if engine=='local_mlx_v118' else 'local-mps'
    if raw is not None:
        if raw['engine']!=engine or raw['model']!=profile['model'] or raw['endpointHost']!=endpoint:
            raise ValueError('Different/remote observation endpoint')
        if any(type(raw[k]) is not int or raw[k]<0 for k in('promptTokens','completionTokens','totalTokens')):
            raise ValueError('Nonnegative native token counts required')
        if raw['promptTokens']+raw['completionTokens']!=raw['totalTokens'] or raw['completionTokens']>profile['max_new_tokens']:
            raise ValueError('Native token accounting differs')
        if parse_json(raw['content'])!=raw['parsed']:raise ValueError('Parsed content differs from unmodified raw output')
    if response.get('record') is not None:
        if response.get('error') is not None or raw is None or raw['finishReason']!='stop':raise ValueError('Failed/truncated record cannot be accepted')
        if response['observation']!=raw['parsed'] or response['record']['observation']!=raw['parsed']:raise ValueError('Repaired/replaced observation')
        facts.project(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],response['record'])
        if engine=='local_mlx_v118' and not 0<raw['peakMemoryBytes']<=MEMORY_LIMIT:raise ValueError('Observed MLX peak exceeds the experiment bound')
        return True
    if response.get('observation') is not None or not isinstance(response.get('error'),str) or not response['error']:
        raise ValueError('Unavailable observations must remain explicit failures')
    return False


def warrant(program,record):
    if record is None:return None
    flags=claims(program,record['observation']);ready=[i for i,k in enumerate(('no','partial','yes')) if flags['local_'+k+'_ready']]
    assert len(ready)<=1
    return ready[0] if ready else None


def audit(probe,previous,checkpoint,out,require_complete=False):
    if out.exists():raise ValueError('Fresh diagnostic audit required')
    manifest=read(probe/'manifest.json');profile=read(probe/'identity.json');protocol=read(probe/'protocol.json');jobs=read(probe/'jobs.json');references=read(probe/'references.json')
    assert profile['model']==MODEL and profile['revision']==REVISION and profile['engine']=='local_mlx_v118'
    assert digest(profile)==manifest['identity_ref'] and digest(protocol)==manifest['protocol_ref'] and digest(jobs)==manifest['jobs_ref']
    assert len(jobs)==12 and Counter(references.values())=={0:4,1:4,2:4} and set(references)=={j['case'] for j in jobs}
    assert profile['max_new_tokens']==512 and profile['max_pixels_per_image']==256*32*32 and profile['enable_thinking'] is False and profile['do_sample'] is False
    assert profile['schema_ref']==digest(facts.schema()) and profile['contract_ref']==facts.CONTRACT_REF and profile['memory_limit_kind']=='mlx_soft_guideline_with_peak_abort'
    assert protocol['bounds']=={'workers':1,'max_local_inferences':12,'max_new_tokens':6144,'retries':0}
    assert file_hash(checkpoint)==manifest['checkpoint_identity_sha256'] and digest(read(checkpoint))==profile['checkpoint_ref']
    for package,expected in profile['packages'].items():assert version(package)==expected
    for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
    source_hashes={}
    for path,sha in {**manifest['code_sha256'],**manifest['source_hashes']}.items():
        assert file_hash(path)==sha;source_hashes[path]=sha
    old_jobs={j['case']:j for j in read(previous/'jobs.json')};old_profile=read(previous/'identity.json');assert references==read(previous/'references.json')
    root=Path(__file__).resolve().parents[1];original={r['case']:r for r in read(root/'logs/exps/261021-frozen-visual-policy-v69/replay_inputs_without_references.json')[:99]}
    assert set(references)<=set(original)
    response_paths={p.stem:p for p in(probe/'responses').glob('*.json')};attempt_paths={p.stem:p for p in(probe/'attempts').glob('*.json')}
    assert set(response_paths)<=set(references) and set(attempt_paths)<=set(references)
    histories=[]
    for line in(probe/'llm-histories.log').read_text().splitlines(keepends=True):
        if not line.endswith('\n'):continue
        h=__import__('json').loads(line);assert h['engine']==profile['engine'] and h['model']==MODEL and h['endpoint_host']=='local-mlx' and h['remote_calls']==0
        assert h['checkpoint_revision']==REVISION and h['max_new_tokens']==512 and h['enable_thinking'] is False and h['decoder']==profile['decoder']
        histories.append(h)
    history=Counter((h['prompt'],h.get('response'),h['prompt_tokens'],h['completion_tokens']) for h in histories)
    from transformers import AutoProcessor
    identity=read(checkpoint);processor=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False,use_fast=True)
    processor.image_processor.size={'longest_edge':profile['max_pixels_per_image'],'shortest_edge':profile['min_pixels_per_image']}
    rows=[];accepted=tokens=reserved=0
    for job in jobs:
        case=job['case'];before=old_jobs[case]
        assert all(job[k]==before[k] for k in('program','evidence','image_hashes','image_pair_ref','prompt','prompt_ref','schema'))
        assert job['program']==original[case]['program'] and job['evidence']==original[case]['evidence']
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        old=read(previous/'responses'/(case+'.json'));assert validate(before,old,old_profile)
        if case in attempt_paths:
            attempted=read(attempt_paths[case]);assert attempted=={'case':case,'request_ref':job['request_ref'],'status':'attempted'}
        response=read(response_paths[case]) if case in response_paths else None
        row={'case':case,'reference':references[case],'attempted':case in attempt_paths,'accepted':False,'old_warrant':warrant(job['program'],old['record']),'new_warrant':None}
        if response is not None:
            assert case in attempt_paths;passed=validate(job,response,profile);row['accepted']=passed;accepted+=passed;raw=response.get('response')
            key=(job['prompt'],raw['content'] if raw else None,raw['promptTokens'] if raw else 0,raw['completionTokens'] if raw else 0)
            assert history[key]>=1;history[key]-=1
            tokens+=raw['completionTokens'] if raw else 0;reserved+=0 if raw else 512
            if raw is not None:
                media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                       {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
                messages,_=local_messages(job['prompt'],media);rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                assert raw['renderedPromptRef']==digest(rendered)
                from PIL import Image
                images=[]
                for name in('source_image','edited_image'):
                    with Image.open(job['evidence'][name]) as im:images.append(im.convert('RGB'))
                inputs=processor(text=[rendered],images=images,return_tensors='pt',padding=True)
                assert int(inputs['input_ids'].numel())==raw['promptTokens'] and {k:list(v.shape) for k,v in inputs.items()}==raw['inputShapes']
            row['new_warrant']=warrant(job['program'],response['record']);source_hashes[str(response_paths[case])]=file_hash(response_paths[case])
        elif case in attempt_paths:reserved+=512
        rows.append(row)
    complete=len(response_paths)==12
    assert len(attempt_paths)<=12 and len(histories)<=len(attempt_paths) and tokens+reserved<=6144
    if require_complete:assert complete,'Observation diagnostic is incomplete'
    if complete:
        terminal=read(probe/'results.json');assert terminal['complete'] and terminal['attempted']==12 and terminal['responses']==12 and terminal['accepted']==accepted and terminal['completion_tokens']==tokens and terminal['reserved_completion_tokens']==reserved
        assert not any(history.values())
    preflight=read(probe/'preflight.json');assert preflight['neural_calls']==0
    if response_paths:assert preflight['passed']
    result={'passed':True,'complete':complete,'snapshot_only':not require_complete,'responses':len(response_paths),'attempts':len(attempt_paths),'accepted':accepted,
        'completion_tokens':tokens,'reserved_completion_tokens':reserved,'history_records':len(histories),'raw_rendered_prompts_replayed':sum(read(p).get('response') is not None for p in response_paths.values()),
        'old_warranted':sum(r['old_warrant'] is not None for r in rows),'old_warrant_correct_of12':sum(r['old_warrant']==r['reference'] for r in rows),
        'new_warranted':sum(r['new_warrant'] is not None for r in rows) if complete else None,'new_warrant_correct_of12':sum(r['new_warrant']==r['reference'] for r in rows) if complete else None,
        'maximum_observed_mlx_bytes':max([preflight.get('peak_memory_bytes',0)]+[read(p).get('response',{}).get('peakMemoryBytes',0) for p in response_paths.values()]),
        'new_api_calls':0,'new_inference_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False,
        'scope':'Balanced12-case original-training diagnostic only. Warrant coverage/correctness are not population or pipeline accuracy. Failed/unwarranted cases remain in the12-case denominator.'}
    out.mkdir(parents=True);save_json(out/'verification.json',result);save_json(out/'cases.json',rows)
    for folder in(probe,previous):
        for name in('manifest.json','identity.json','jobs.json','references.json'):source_hashes[str(folder/name)]=file_hash(folder/name)
    source_hashes[str(checkpoint)]=file_hash(checkpoint);save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'source_hashes':source_hashes})
    dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Exact source/input bindings, raw records, native processor prompts/shapes, history and budgets verified. No fitting or population accuracy claim.\n');(out/'llm-histories.log').write_text('No inference/API calls; native CPU processor replay only.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('probe','previous-probe','checkpoint','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--require-complete',action='store_true');a=p.parse_args();audit(a.probe.resolve(),a.previous_probe.resolve(),a.checkpoint.resolve(),a.output_dir.resolve(),a.require_complete)
