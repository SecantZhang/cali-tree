"""Frozen training-only native sampling/thinking comparison for Qwen3.5."""
import argparse
from copy import deepcopy
from importlib.metadata import version,distribution
import json
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_sampled_v124 import SampledLocalMLXEngine,sample_seed
from critical.lm_engine.local_mlx_v118 import MEMORY_LIMIT,CACHE_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash,local_messages
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_mlx_observer_probe_v119 import ROOT,DOWNLOAD,read

ARMS=('sampled_instruct','sampled_thinking')


def prepare(previous,verified,out):
    if out.exists():raise ValueError('Fresh native-sampling diagnostic required')
    v=read(verified/'verification.json');assert v['passed'] and v['complete'] and v['accepted']==12
    old=read(previous/'manifest.json');jobs=read(previous/'jobs.json');profile=read(previous/'identity.json')
    assert digest(jobs)==old['jobs_ref'] and digest(profile)==old['identity_ref']
    for path,sha in old['code_sha256'].items():assert file_hash(path)==sha
    files=[Path(__file__),ROOT/'critical/lm_engine/local_mlx_sampled_v124.py',ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/core/decision/local_rubric_evidence_v94.py']
    out.mkdir(parents=True);code={str(p):file_hash(p) for p in files}
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    for arm in ARMS:
        thinking=arm=='sampled_thinking';identity=deepcopy(profile)
        identity.update(engine=SampledLocalMLXEngine.name,enable_thinking=thinking,do_sample=True,temperature=1. if thinking else .7,top_p=.95 if thinking else .8,
            top_k=20,min_p=0.,presence_penalty=1.5,max_reasoning_tokens=2048 if thinking else 0,max_final_tokens=512,max_new_tokens=2560 if thinking else 512,
            decoder='native_sampled_thinking_boundary_json_v124',strict_field_order=False,seed_rule='uint32_prefix_sha256([local-sampling-v124,20261023,program_ref,image_pair_ref])',
            sampled_engine_sha256=file_hash(ROOT/'critical/lm_engine/local_mlx_sampled_v124.py'))
        frozen=[]
        for before in jobs:
            job={k:v for k,v in before.items() if k!='request_ref'};job['identity_ref']=digest(identity);job['seed']=sample_seed(job['program']['program_ref'],job['image_pair_ref']);job['request_ref']=digest(job);frozen.append(job)
        folder=out/arm;save_json(folder/'identity.json',identity);save_json(folder/'jobs.json',frozen);save_json(folder/'references.json',read(previous/'references.json'))
        save_json(folder/'manifest.json',{'identity_ref':digest(identity),'jobs_ref':digest(frozen),'code_sha256':code,'checkpoint_identity_sha256':file_hash(DOWNLOAD),
            'prior_manifest_sha256':file_hash(previous/'manifest.json'),'prior_audit_manifest_sha256':file_hash(verified/'manifest.json')})
        (folder/'run.log').write_text('Frozen training-only native sampling arm.\n');(folder/'llm-histories.log').touch()
    protocol={'version':'native-sampling-training-diagnostic-v125','arms':ARMS,'cases_per_arm':12,
        'selection':'Same12 balanced original-training inputs and original seven-field prompt/schema as v119. No held/reserved images, fitting or label-dependent new selection.',
        'source':'https://huggingface.co/Qwen/Qwen3.5-9B#best-practices',
        'profiles':'Published general-task sampling: instruct .7/.8, thinking1/.95, both top_k20 and presence_penalty1.5. Each input gets one deterministic input-derived seed. Framework is pinned native MLX.',
        'channels':'Thinking is unconstrained until the model emits its native closing-think token; JSON constraints then apply to the final channel. No synthetic closing token, JSON repair, thought-as-answer extraction or resampling. Raw native text and token IDs are retained.',
        'bounds':{'workers':1,'max_local_inferences':24,'max_new_tokens':36864,'instruct_per_case':512,'thinking_per_case':2560,'reasoning_per_case':2048,'final_per_case':512,'retries':0},
        'failure':'Truncation, no native thinking close, invalid records and backend failures remain unavailable. Stop at the first backend error or three consecutive observation failures; no fits or serving changes.',
        'scope':'Training-only diagnostic, not population/pipeline accuracy. No API calls, task uploads or reserved-source access.',
        'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False}
    save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Prepared seeded native instruct/thinking diagnostics, no inference.\n');(out/'llm-histories.log').write_text('Per-arm native histories contain unmodified generated channels. No root-level inference.\n')
    print({'arms':ARMS,'cases_per_arm':12,'max_local_tokens':36864},flush=True)


def collect(out):
    import os
    if os.environ.get('LMFE_STRICT_JSON_FIELD_ORDER','false').lower() not in('false','0',''):raise ValueError('Original non-forced field-order profile required')
    checkpoint=read(DOWNLOAD);engine=None;results={}
    for arm in ARMS:
        folder=out/arm;profile=read(folder/'identity.json');manifest=read(folder/'manifest.json');jobs=read(folder/'jobs.json')
        assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and file_hash(DOWNLOAD)==manifest['checkpoint_identity_sha256']
        for p,sha in manifest['code_sha256'].items():assert file_hash(p)==sha
        for p,expected in profile['packages'].items():assert version(p)==expected
        for p,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(p))==sha
        if engine is None:engine=SampledLocalMLXEngine(checkpoint['destination'],checkpoint,thinking=profile['enable_thinking'],max_pixels=profile['max_pixels_per_image'])
        else:engine.configure(profile['enable_thinking'])
        assert engine.max_tokens==profile['max_new_tokens'] and engine.temperature==profile['temperature'] and engine.top_p==profile['top_p']
        engine.history=LLMHistoryWriter(folder/'llm-histories.log')
        import mlx.core as mx
        old_memory=mx.set_memory_limit(MEMORY_LIMIT);old_cache=mx.set_cache_limit(CACHE_LIMIT)
        try:
            engine._load();first=jobs[0];media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':first['evidence']['source_image']},
                {'type':'text','text':'EDITED image'},{'type':'image','path':first['evidence']['edited_image']}]
            messages,paths=local_messages(first['prompt'],media);inputs,rendered=engine._prepare_inputs(messages,paths)
            if mx.get_peak_memory()>MEMORY_LIMIT:raise RuntimeError('Model/processor preflight exceeds observed8GiB bound')
            save_json(folder/'preflight.json',{'passed':True,'neural_calls':0,'peak_memory_bytes':mx.get_peak_memory(),'processor_rendered_ref':digest(rendered),'input_shapes':{k:list(v.shape) for k,v in inputs.items()}});del inputs
        finally:mx.synchronize();mx.clear_cache();mx.set_memory_limit(old_memory);mx.set_cache_limit(old_cache)
        (folder/'responses').mkdir(exist_ok=True);(folder/'attempts').mkdir(exist_ok=True);errors=0
        for job in jobs:
            case=job['case'];destination=folder/'responses'/(case+'.json');attempt=folder/'attempts'/(case+'.json')
            if destination.exists() or attempt.exists():continue
            assert job['schema']==facts.schema() and job['seed']==sample_seed(job['program']['program_ref'],job['image_pair_ref']) and digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
            hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
            with attempt.open('x') as f:json.dump({'case':case,'request_ref':job['request_ref'],'status':'attempted'},f)
            result={'case':case,'request_ref':job['request_ref'],'observation':None,'record':None,'error':None}
            try:
                result['response']=engine.generate(job['prompt'],[
                    {'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                    {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}],job['schema'],seed=job['seed'])
                if result['response']['finishReason']!='stop' or not result['response']['thinkingClosed']:raise ValueError('Native final channel unavailable within frozen bounds')
                value=facts.validate(result['response']['parsed']);record=facts.bind(job['program'],pair,job['identity_ref'],job['prompt_ref'],value);result.update(observation=value,record=record)
            except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
            save_json(destination,result);errors=errors+1 if result['error'] else 0
            with(folder/'run.log').open('a') as f:f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
            print({'arm':arm,'case':case,'accepted':result['record'] is not None,'tokens':result.get('response',{}).get('completionTokens'),'error':result['error']},flush=True)
            if errors>=3 or (result['error'] or '').startswith('RuntimeError:'):break
        rows=[read(p) for p in(folder/'responses').glob('*.json')];attempts=len(list((folder/'attempts').glob('*.json')))
        tokens=sum(r.get('response',{}).get('completionTokens',0) for r in rows);reserved=(attempts-sum(r.get('response') is not None for r in rows))*profile['max_new_tokens']
        assert attempts<=12 and tokens+reserved<=12*profile['max_new_tokens']
        result={'cases':12,'attempts':attempts,'responses':len(rows),'accepted':sum(r['record'] is not None for r in rows),'completion_tokens':tokens,'reserved_completion_tokens':reserved,
            'complete':len(rows)==12,'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False};save_json(folder/'results.json',result);results[arm]=result;print({'arm':arm,'result':result},flush=True)
        if not result['complete']:break
    save_json(out/'results.json',results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous-probe',type=Path);p.add_argument('--previous-audit',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose prepare or collect')
    if a.prepare:prepare(a.previous_probe.resolve(),a.previous_audit.resolve(),a.output_dir.resolve())
    else:collect(a.output_dir.resolve())
