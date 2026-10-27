"""Independently replay evidence-first raw order, bindings and diagnostic warrants."""
import argparse
from collections import Counter
from importlib.metadata import version,distribution
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_evidence_first_v121 import schema,EvidenceFirstEngine
from critical.lm_engine.local_mlx_v118 import MODEL,MEMORY_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash,parse_json,local_messages
from run.verify_calitree_mlx_probe_v120 import read,warrant


def validate(job,response,profile):
    if (digest({k:v for k,v in job.items() if k!='request_ref'})!=job['request_ref'] or response.get('request_ref')!=job['request_ref'] or response.get('case')!=job['case'] or
            job['identity_ref']!=digest(profile) or job['schema']!=schema() or job['prompt_ref']!=digest(job['prompt'])):
        raise ValueError('Changed evidence-first request')
    raw=response.get('response')
    if raw is not None:
        if raw['engine']!=EvidenceFirstEngine.name or raw['engine']!=profile['engine'] or raw['model']!=MODEL or raw['endpointHost']!='local-mlx':raise ValueError('Different local model/endpoint')
        if any(type(raw[k]) is not int or raw[k]<0 for k in('promptTokens','completionTokens','totalTokens')) or raw['promptTokens']+raw['completionTokens']!=raw['totalTokens'] or raw['completionTokens']>512:
            raise ValueError('Invalid native token accounting')
        if parse_json(raw['content'])!=raw['parsed']:raise ValueError('Raw output was repaired/replaced')
    if response.get('record') is not None:
        if raw is None or raw['finishReason']!='stop' or response.get('error') is not None:raise ValueError('Failed/truncated observation accepted')
        parsed=parse_json(raw['content'])
        if list(parsed)!=schema()['required']:raise ValueError('Evidence-first order differs from native text')
        if not 1<=len(parsed['evidence'])<=360:raise ValueError('Evidence length exceeds the frozen schema')
        if response['observation']!=parsed or response['record']['observation']!=parsed:raise ValueError('Observation differs from raw output')
        facts.project(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],response['record'])
        if not 0<raw['peakMemoryBytes']<=MEMORY_LIMIT:raise ValueError('Observed memory bound exceeded')
        return True
    if response.get('observation') is not None or not isinstance(response.get('error'),str) or not response['error']:
        raise ValueError('Failed observation must remain unavailable')
    return False


def audit(study,previous,previous_audit,checkpoint,out):
    if out.exists():raise ValueError('Fresh evidence-first audit required')
    prior=read(previous_audit/'verification.json');assert prior['passed'] and prior['complete'] and prior['accepted']==12
    baseline_jobs={j['case']:j for j in read(previous/'jobs.json')};references=read(previous/'references.json')
    protocol=read(study/'protocol.json');assert protocol['bounds']=={'max_local_inferences':24,'max_new_tokens':12288,'workers':1,'retries':0}
    assert tuple(protocol['arms'])==('order_only','order_clarified') and protocol['cases_per_arm']==12
    from transformers import AutoProcessor
    identity=read(checkpoint);processor=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False,use_fast=True)
    processor.image_processor.size={'longest_edge':256*32*32,'shortest_edge':64*32*32}
    source_hashes={};results={};rows=[];native_count=0
    for arm in protocol['arms']:
        folder=study/arm;manifest=read(folder/'manifest.json');profile=read(folder/'identity.json');jobs=read(folder/'jobs.json');template=(folder/'template.txt').read_text()
        assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(template)==manifest['template_ref']==profile['observer_template_ref']
        assert manifest['prior_manifest_sha256']==file_hash(previous/'manifest.json') and manifest['prior_audit_manifest_sha256']==file_hash(previous_audit/'manifest.json')
        assert manifest['checkpoint_identity_sha256']==file_hash(checkpoint) and profile['checkpoint_ref']==digest(identity)
        assert profile['strict_field_order'] is True and profile['schema_ref']==digest(schema()) and profile['engine']==EvidenceFirstEngine.name
        assert read(folder/'references.json')==references and len(jobs)==12 and {j['case'] for j in jobs}==set(references)
        for path,sha in manifest['code_sha256'].items():assert file_hash(path)==sha;source_hashes[path]=sha
        for package,expected in profile['packages'].items():assert version(package)==expected
        for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
        terminal=read(folder/'results.json');assert terminal['complete'] and terminal['responses']==12 and terminal['attempts']==12
        response_paths={p.stem:p for p in(folder/'responses').glob('*.json')};attempt_paths={p.stem:p for p in(folder/'attempts').glob('*.json')}
        assert set(response_paths)==set(attempt_paths)==set(references)
        history=[]
        for line in(folder/'llm-histories.log').read_text().splitlines():
            h=__import__('json').loads(line);assert h['engine']==EvidenceFirstEngine.name and h['model']==MODEL and h['remote_calls']==0 and h['endpoint_host']=='local-mlx'
            assert h['max_new_tokens']==512 and h['enable_thinking'] is False;history.append(h)
        counts=Counter((h['prompt'],h.get('response'),h['prompt_tokens'],h['completion_tokens']) for h in history)
        accepted=tokens=reserved=0;arm_rows=[]
        for job in jobs:
            case=job['case'];before=baseline_jobs[case]
            assert all(job[k]==before[k] for k in('case','program','evidence','image_hashes','image_pair_ref'))
            assert job['prompt']==facts.prompt(job['program'],template)
            hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
            assert read(attempt_paths[case])=={'case':case,'request_ref':job['request_ref'],'status':'attempted'}
            response=read(response_paths[case]);passed=validate(job,response,profile);accepted+=passed;raw=response.get('response')
            key=(job['prompt'],raw['content'] if raw else None,raw['promptTokens'] if raw else 0,raw['completionTokens'] if raw else 0)
            assert counts[key]>=1;counts[key]-=1;tokens+=raw['completionTokens'] if raw else 0;reserved+=0 if raw else 512
            if raw is not None:
                media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                       {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
                messages,_=local_messages(job['prompt'],media);rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                assert digest(rendered)==raw['renderedPromptRef']
                from PIL import Image
                images=[]
                for name in('source_image','edited_image'):
                    with Image.open(job['evidence'][name]) as im:images.append(im.convert('RGB'))
                native=processor(text=[rendered],images=images,return_tensors='pt',padding=True)
                assert int(native['input_ids'].numel())==raw['promptTokens'] and {k:list(v.shape) for k,v in native.items()}==raw['inputShapes'];native_count+=1
            old=read(previous/'responses'/(case+'.json'))
            row={'arm':arm,'case':case,'reference':references[case],'accepted':passed,'baseline_warrant':warrant(job['program'],old['record']),
                'new_warrant':warrant(job['program'],response['record'])}
            arm_rows.append(row);rows.append(row)
            for path in(response_paths[case],attempt_paths[case],previous/'responses'/(case+'.json')):source_hashes[str(path)]=file_hash(path)
        assert len(history)==12 and not any(counts.values()) and terminal['accepted']==accepted and terminal['completion_tokens']==tokens and terminal['reserved_completion_tokens']==reserved and tokens+reserved<=6144
        results[arm]={'accepted':accepted,'total':12,'warranted':sum(r['new_warrant'] is not None for r in arm_rows),'warrant_correct_of12':sum(r['new_warrant']==r['reference'] for r in arm_rows),
            'baseline_warrant_correct_of12':sum(r['baseline_warrant']==r['reference'] for r in arm_rows),'completion_tokens':tokens,'reserved_completion_tokens':reserved}
        for name in('identity.json','manifest.json','jobs.json','references.json','template.txt','llm-histories.log','results.json'):source_hashes[str(folder/name)]=file_hash(folder/name)
    assert sum(r['completion_tokens']+r['reserved_completion_tokens'] for r in results.values())<=12288
    result={'passed':True,'complete':True,'arms':results,'raw_native_processor_replays':native_count,'new_inference_calls':0,'new_api_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False,
        'scope':'Two balanced12-case original-training diagnostics only. Failed/unwarranted cases remain in each12-case denominator. These are not population or pipeline accuracy results.'}
    out.mkdir(parents=True);save_json(out/'verification.json',result);save_json(out/'cases.json',rows)
    source_hashes[str(study/'protocol.json')]=file_hash(study/'protocol.json');source_hashes[str(checkpoint)]=file_hash(checkpoint)
    save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'source_hashes':source_hashes});dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Native evidence-first order, char limit, processor inputs, request/source bindings and budgets verified. No fitting or pipeline accuracy claim.\n');(out/'llm-histories.log').write_text('No model/API calls; CPU processor replay only.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('study','previous-probe','previous-audit','checkpoint','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.study.resolve(),a.previous_probe.resolve(),a.previous_audit.resolve(),a.checkpoint.resolve(),a.output_dir.resolve())
