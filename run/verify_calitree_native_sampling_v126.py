"""Audit native token/channel boundaries, seeded calls and training-only warrants."""
import argparse
from collections import Counter
from importlib.metadata import distribution,version
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_sampled_v124 import SampledLocalMLXEngine,sample_seed
from critical.lm_engine.local_mlx_v118 import MODEL,MEMORY_LIMIT,terminal_ids
from critical.lm_engine.local_qwen_v94 import file_hash,parse_json,local_messages
from run.verify_calitree_mlx_probe_v120 import read,warrant


def validate_channels(raw,profile,tokenizer,eos,vocab_size):
    ids=raw['generatedTokenIds'];thinking=profile['enable_thinking'];closing=raw['closingThinkTokenId']
    if (not isinstance(ids,list) or any(type(i) is not int or not 0<=i<vocab_size for i in ids) or raw['completionTokens']!=len(ids) or
            tokenizer.decode([closing],skip_special_tokens=False)!='</think>'):
        raise ValueError('Invalid native generated-token trace')
    full=tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    if full!=raw['nativeFullContent']:raise ValueError('Native full output differs from token trace')
    if thinking:
        closed=closing in ids;end=ids.index(closing)+1 if closed else len(ids)
        final_ids=ids[end:] if closed else [];reason_ids=ids[:end-1] if closed else ids
        reason=tokenizer.decode(reason_ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
        expected_final=tokenizer.decode(final_ids,skip_special_tokens=True,clean_up_tokenization_spaces=False) if closed else ''
    else:
        closed=True;end=0;final_ids=ids;reason='';expected_final=tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
    if (raw['thinkingClosed']!=closed or raw['reasoningTokens']!=end or raw['finalTokens']!=len(final_ids) or
            raw['reasoningContent']!=reason or raw['content']!=expected_final):
        raise ValueError('Final/reasoning channel differs from the native boundary')
    if end>profile['max_reasoning_tokens'] or len(final_ids)>512 or len(ids)>profile['max_new_tokens']:
        raise ValueError('Native channel token budget exceeded')
    if raw['finishReason']=='stop' and (not ids or ids[-1] not in eos or not closed):
        raise ValueError('Final output lacks native end/closing tokens')
    if parse_json(raw['content'])!=raw['parsed']:raise ValueError('Final JSON was repaired/replaced')


def audit(study,previous,previous_audit,checkpoint,out,require_complete=False,require_terminal=False):
    if out.exists():raise ValueError('Fresh sampled-channel audit required')
    prior=read(previous_audit/'verification.json');assert prior['passed'] and prior['complete']
    baseline={j['case']:j for j in read(previous/'jobs.json')};references=read(previous/'references.json');protocol=read(study/'protocol.json')
    assert tuple(protocol['arms'])==('sampled_instruct','sampled_thinking') and protocol['bounds']['max_local_inferences']==24 and protocol['bounds']['max_new_tokens']==36864
    root_terminal=read(study/'results.json') if (study/'results.json').exists() else None
    if require_terminal:assert root_terminal is not None and tuple(root_terminal)==tuple(protocol['arms']),'Collector has not finalized both planned arms'
    from transformers import AutoProcessor
    identity=read(checkpoint);processor=AutoProcessor.from_pretrained(identity['destination'],local_files_only=True,trust_remote_code=False,use_fast=True)
    processor.image_processor.size={'longest_edge':256*32*32,'shortest_edge':64*32*32};tokenizer=processor.tokenizer
    config=read(Path(identity['destination'])/'config.json');eos=terminal_ids(tokenizer,config['text_config']['eos_token_id']);vocab_size=config['text_config']['vocab_size']
    source_hashes={};results={};rows=[];replays=0
    for arm in protocol['arms']:
        folder=study/arm;profile=read(folder/'identity.json');manifest=read(folder/'manifest.json');jobs=read(folder/'jobs.json');thinking=arm=='sampled_thinking'
        assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and profile['engine']==SampledLocalMLXEngine.name
        assert profile['checkpoint_ref']==digest(identity) and manifest['checkpoint_identity_sha256']==file_hash(checkpoint)
        assert profile['enable_thinking']==thinking and profile['do_sample'] is True and profile['temperature']==(1. if thinking else .7) and profile['top_p']==(.95 if thinking else .8)
        assert profile['top_k']==20 and profile['presence_penalty']==1.5 and profile['max_reasoning_tokens']==(2048 if thinking else 0) and profile['max_new_tokens']==(2560 if thinking else 512)
        assert manifest['prior_manifest_sha256']==file_hash(previous/'manifest.json') and manifest['prior_audit_manifest_sha256']==file_hash(previous_audit/'manifest.json')
        assert read(folder/'references.json')==references and {j['case'] for j in jobs}==set(references) and len(jobs)==12
        for path,sha in manifest['code_sha256'].items():assert file_hash(path)==sha;source_hashes[path]=sha
        for name,expected in profile['packages'].items():assert version(name)==expected
        for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
        response_paths={p.stem:p for p in(folder/'responses').glob('*.json')};attempt_paths={p.stem:p for p in(folder/'attempts').glob('*.json')}
        assert set(response_paths)<=set(attempt_paths)<=set(references)
        complete=len(response_paths)==12
        if require_complete:assert complete,'Sampled diagnostic is incomplete'
        history=[]
        for line in(folder/'llm-histories.log').read_text().splitlines(keepends=True):
            if not line.endswith('\n'):continue
            h=__import__('json').loads(line);assert h['engine']==SampledLocalMLXEngine.name and h['model']==MODEL and h['remote_calls']==0 and h['endpoint_host']=='local-mlx'
            assert h['enable_thinking']==thinking and h['do_sample'] is True and h['temperature']==profile['temperature'] and h['top_p']==profile['top_p'] and h['top_k']==20 and h['presence_penalty']==1.5
            history.append(h)
        counts=Counter((h['prompt'],h.get('response'),h['prompt_tokens'],h['completion_tokens'],h['seed']) for h in history)
        accepted=tokens=reserved=reasoning=final=0;arm_rows=[];max_peak=0
        for job in jobs:
            case=job['case'];before=baseline[case];assert all(job[k]==before[k] for k in('program','evidence','image_hashes','image_pair_ref','prompt','prompt_ref','schema'))
            assert job['schema']==facts.schema() and job['identity_ref']==digest(profile) and job['seed']==sample_seed(job['program']['program_ref'],job['image_pair_ref']) and job['request_ref']==digest({k:v for k,v in job.items() if k!='request_ref'})
            hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
            old=read(previous/'responses'/(case+'.json'));row={'arm':arm,'case':case,'reference':references[case],'accepted':False,'baseline_warrant':warrant(job['program'],old['record']),'new_warrant':None}
            if case in attempt_paths:
                assert read(attempt_paths[case])=={'case':case,'request_ref':job['request_ref'],'status':'attempted'};source_hashes[str(attempt_paths[case])]=file_hash(attempt_paths[case])
            if case not in response_paths:
                if case in attempt_paths:reserved+=profile['max_new_tokens']
                arm_rows.append(row);rows.append(row);continue
            response=read(response_paths[case]);assert response['case']==case and response['request_ref']==job['request_ref'];raw=response.get('response')
            if raw is not None:
                assert raw['engine']==SampledLocalMLXEngine.name and raw['model']==MODEL and raw['endpointHost']=='local-mlx' and raw['seed']==job['seed']
                assert all(type(raw[k]) is int and raw[k]>=0 for k in('promptTokens','completionTokens','totalTokens')) and raw['promptTokens']+raw['completionTokens']==raw['totalTokens']
                validate_channels(raw,profile,tokenizer,eos,vocab_size)
                tokens+=raw['completionTokens'];reasoning+=raw['reasoningTokens'];final+=raw['finalTokens'];max_peak=max(max_peak,raw['peakMemoryBytes']);assert max_peak<=MEMORY_LIMIT
                key=(job['prompt'],raw['nativeFullContent'],raw['promptTokens'],raw['completionTokens'],job['seed'])
                media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},{'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
                messages,_=local_messages(job['prompt'],media);rendered=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=thinking)
                assert digest(rendered)==raw['renderedPromptRef']
                from PIL import Image
                images=[]
                for name in('source_image','edited_image'):
                    with Image.open(job['evidence'][name]) as im:images.append(im.convert('RGB'))
                native=processor(text=[rendered],images=images,return_tensors='pt',padding=True)
                assert int(native['input_ids'].numel())==raw['promptTokens'] and {k:list(v.shape) for k,v in native.items()}==raw['inputShapes'];replays+=1
            else:
                reserved+=profile['max_new_tokens'];key=(job['prompt'],None,0,0,job['seed'])
            assert counts[key]>=1;counts[key]-=1
            if response['record'] is not None:
                assert raw is not None and raw['finishReason']=='stop' and raw['thinkingClosed'] and response['error'] is None
                assert response['observation']==raw['parsed']==response['record']['observation']
                facts.project(job['program'],pair,job['identity_ref'],job['prompt_ref'],response['record']);row['accepted']=True;accepted+=1;row['new_warrant']=warrant(job['program'],response['record'])
            else:assert response['observation'] is None and isinstance(response['error'],str) and response['error']
            arm_rows.append(row);rows.append(row);source_hashes[str(response_paths[case])]=file_hash(response_paths[case])
        assert tokens+reserved<=12*profile['max_new_tokens'] and len(history)<=len(attempt_paths)
        if complete or require_terminal:
            terminal=read(folder/'results.json');assert terminal['complete']==complete and terminal['attempts']==len(attempt_paths) and terminal['responses']==len(response_paths) and terminal['accepted']==accepted and terminal['completion_tokens']==tokens and terminal['reserved_completion_tokens']==reserved
            if require_terminal:assert terminal==root_terminal[arm]
            assert not any(counts.values())
        results[arm]={'complete':complete,'responses':len(response_paths),'attempts':len(attempt_paths),'accepted':accepted,'completion_tokens':tokens,'reasoning_tokens':reasoning,'final_tokens':final,'reserved_completion_tokens':reserved,
            'warranted':sum(r['new_warrant'] is not None for r in arm_rows) if complete else None,'warrant_correct_of12':sum(r['new_warrant']==r['reference'] for r in arm_rows) if complete else None,
            'baseline_warrant_correct_of12':sum(r['baseline_warrant']==r['reference'] for r in arm_rows),'max_observed_mlx_bytes':max_peak}
        for name in('manifest.json','identity.json','jobs.json','references.json','llm-histories.log'):source_hashes[str(folder/name)]=file_hash(folder/name)
    assert sum(r['completion_tokens']+r['reserved_completion_tokens'] for r in results.values())<=36864
    result={'passed':True,'complete':all(r['complete'] for r in results.values()),'terminal':root_terminal is not None,'snapshot_only':not(require_complete or require_terminal),'arms':results,'native_processor_replays':replays,'new_inference_calls':0,'new_api_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False,
        'scope':'Balanced original-training diagnostic only. Native thought/final boundaries are replayed exactly; unfinished thoughts cannot become observations. Not population or pipeline accuracy.'}
    out.mkdir(parents=True);save_json(out/'verification.json',result);save_json(out/'cases.json',rows)
    source_hashes[str(study/'protocol.json')]=file_hash(study/'protocol.json');source_hashes[str(checkpoint)]=file_hash(checkpoint)
    sampler=distribution('mlx-lm').locate_file('mlx_lm/sample_utils.py');source_hashes[str(sampler)]=file_hash(sampler)
    save_json(out/'manifest.json',{'auditor_sha256':file_hash(__file__),'source_hashes':source_hashes});dest=out/'source_snapshot/run'/Path(__file__).name;dest.parent.mkdir(parents=True);shutil.copyfile(__file__,dest)
    (out/'run.log').write_text('Native tokens, channels, seeds, processor inputs, histories and budgets audited; no fitting or pipeline accuracy claim.\n');(out/'llm-histories.log').write_text('No model/API calls. CPU tokenizer/processor replay only.\n');print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('study','previous-probe','previous-audit','checkpoint','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--require-complete',action='store_true');p.add_argument('--require-terminal',action='store_true');a=p.parse_args();audit(a.study.resolve(),a.previous_probe.resolve(),a.previous_audit.resolve(),a.checkpoint.resolve(),a.output_dir.resolve(),a.require_complete,a.require_terminal)
