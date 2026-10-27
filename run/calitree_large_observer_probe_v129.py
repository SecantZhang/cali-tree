"""Frozen32B local task/preservation diagnostic on the original12 training cases."""
import argparse
import fcntl
from importlib.metadata import version,distribution
import json
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine,MEMORY_LIMIT
from critical.lm_engine.local_mlx_v118 import CACHE_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash,local_messages
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_mlx_observer_probe_v119 import read,ROOT,PACKAGES,PREVIOUS,TEMPLATE

DOWNLOAD=ROOT/'logs/exps/261023-large-mlx-download-v127-r1/identity.json'


def prepare(out):
    if out.exists():raise ValueError('Fresh large-observer probe required')
    checkpoint=read(DOWNLOAD);assert checkpoint['status']=='complete'
    old_jobs=read(PREVIOUS/'jobs.json');old_manifest=read(PREVIOUS/'manifest.json');assert len(old_jobs)==12 and digest(old_jobs)==old_manifest['jobs_ref']
    packages={p:version(p) for p in PACKAGES};assert packages['mlx-vlm']=='0.3.12' and packages['mlx']=='0.30.4' and packages['transformers']=='5.1.0' and packages['torch']=='2.9.0' and packages['torchvision']=='0.24.0'
    libraries={name:file_hash(distribution('mlx-vlm').locate_file(name)) for name in('mlx_vlm/generate.py','mlx_vlm/utils.py','mlx_vlm/models/qwen3_vl/qwen3_vl.py')}
    profile={'model':checkpoint['model'],'revision':checkpoint['revision'],'checkpoint_ref':digest(checkpoint),'engine':LargeMLXEngine.name,'device':'metal',
        'quantization':checkpoint['quantization'],'max_new_tokens':512,'max_pixels_per_image':256*32*32,'min_pixels_per_image':64*32*32,'do_sample':False,'enable_thinking':False,
        'strict_field_order':False,'decoder':'native-json-prefix-mlx-large-v128','input_format':'native_pytorch_cpu_to_mlx','prefill_step_size':None,
        'schema_ref':digest(facts.schema()),'contract_ref':facts.CONTRACT_REF,'memory_limit_bytes':MEMORY_LIMIT,'cache_limit_bytes':CACHE_LIMIT,'memory_limit_kind':'mlx_soft_guideline_with_peak_abort',
        'packages':packages,'library_source_sha256':libraries,'large_engine_sha256':file_hash(ROOT/'critical/lm_engine/local_mlx_large_v128.py'),'parent_engine_sha256':file_hash(ROOT/'critical/lm_engine/local_mlx_v118.py')}
    jobs=[]
    for old in old_jobs:
        job={k:v for k,v in old.items() if k!='request_ref'};assert job['prompt']==facts.prompt(job['program'],TEMPLATE.read_text()) and job['schema']==facts.schema()
        job['identity_ref']=digest(profile);job['request_ref']=digest(job);jobs.append(job)
    protocol={'version':'large-local-observer-diagnostic-v129','cases':12,'case_scope':'Exactly the original balanced12-case v95 training diagnostic. No new selection, held/reserved inputs or fitting.',
        'view':'Pinned32B4bit MLX model; unchanged seven-field prompt/schema, same256-token image budget, greedy nonthinking native JSON. One joint image comparison per case, not per predicate.',
        'bounds':{'workers':1,'max_local_inferences':12,'max_new_tokens':6144,'retries':0},
        'resources':'Exclusive local-GPU experiment lock.24GiB MLX allocation guideline with observed-peak abort; native loading/CPU processing preflight before durable observation attempts.',
        'failures':'No repaired or repeated responses. Stop on first backend error or three consecutive observation failures. Failures remain unavailable.',
        'limits':'Training-only format/semantic diagnostic, not population/pipeline accuracy or policy promotion. No API calls/uploads or reference labels sent to the observer.',
        'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'identity.json',profile);save_json(out/'protocol.json',protocol);save_json(out/'jobs.json',jobs);save_json(out/'references.json',read(PREVIOUS/'references.json'))
    files=[Path(__file__),ROOT/'critical/lm_engine/local_mlx_large_v128.py',ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/lm_engine/local_qwen_v94.py',ROOT/'critical/core/decision/local_rubric_evidence_v94.py',TEMPLATE]
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    save_json(out/'manifest.json',{'identity_ref':digest(profile),'protocol_ref':digest(protocol),'jobs_ref':digest(jobs),'checkpoint_identity_sha256':file_hash(DOWNLOAD),
        'code_sha256':{str(p):file_hash(p) for p in files},'source_hashes':{str(PREVIOUS/p):file_hash(PREVIOUS/p) for p in('jobs.json','manifest.json','references.json')}})
    (out/'run.log').write_text('Prepared frozen12-case32B diagnostic; no inference or uploads.\n');(out/'llm-histories.log').touch();print({'cases':12,'profile_ref':digest(profile),'max_local_tokens':6144},flush=True)


def collect_locked(out):
    import os
    if os.environ.get('LMFE_STRICT_JSON_FIELD_ORDER','false').lower() not in('false','0',''):raise ValueError('Original non-forced field-order decoder required')
    manifest=read(out/'manifest.json');profile=read(out/'identity.json');jobs=read(out/'jobs.json');checkpoint=read(DOWNLOAD)
    assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(read(out/'protocol.json'))==manifest['protocol_ref']
    assert file_hash(DOWNLOAD)==manifest['checkpoint_identity_sha256'] and profile['checkpoint_ref']==digest(checkpoint)
    for p,sha in{**manifest['code_sha256'],**manifest['source_hashes']}.items():assert file_hash(p)==sha
    for p,v in profile['packages'].items():assert version(p)==v
    for p,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(p))==sha
    engine=LargeMLXEngine(checkpoint['destination'],checkpoint,history=LLMHistoryWriter(out/'llm-histories.log'),max_tokens=512,max_pixels=profile['max_pixels_per_image'])
    import mlx.core as mx
    old_memory=mx.set_memory_limit(MEMORY_LIMIT);old_cache=mx.set_cache_limit(CACHE_LIMIT)
    try:
        engine._load();job=jobs[0];media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},{'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}]
        messages,paths=local_messages(job['prompt'],media);inputs,rendered=engine._prepare_inputs(messages,paths)
        if mx.get_peak_memory()>MEMORY_LIMIT:raise RuntimeError('Large-observer preflight exceeds24GiB observed bound')
        save_json(out/'preflight.json',{'passed':True,'neural_calls':0,'active_memory_bytes':mx.get_active_memory(),'peak_memory_bytes':mx.get_peak_memory(),
            'processor':type(engine._processor).__name__,'image_processor':type(engine._processor.image_processor).__name__,'rendered_prompt_ref':digest(rendered),'input_shapes':{k:list(v.shape) for k,v in inputs.items()}});del inputs
        print({'preflight_passed':True,'active_memory_gib':mx.get_active_memory()/1024**3},flush=True)
    except Exception as exc:
        save_json(out/'preflight.json',{'passed':False,'error':type(exc).__name__+': '+str(exc),'neural_calls':0,'peak_memory_bytes':mx.get_peak_memory()});raise
    finally:mx.synchronize();mx.clear_cache();mx.set_memory_limit(old_memory);mx.set_cache_limit(old_cache)
    (out/'responses').mkdir(exist_ok=True);(out/'attempts').mkdir(exist_ok=True);errors=0
    for job in jobs:
        case=job['case'];destination=out/'responses'/(case+'.json');attempt=out/'attempts'/(case+'.json')
        if destination.exists() or attempt.exists():continue
        assert digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        with attempt.open('x') as f:json.dump({'case':case,'request_ref':job['request_ref'],'status':'attempted'},f)
        result={'case':case,'request_ref':job['request_ref'],'observation':None,'record':None,'error':None}
        try:
            result['response']=engine.generate(job['prompt'],[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}],job['schema'])
            if result['response']['finishReason']!='stop':raise ValueError('Large observation reached its frozen token cap')
            value=facts.validate(result['response']['parsed']);record=facts.bind(job['program'],pair,job['identity_ref'],job['prompt_ref'],value);result.update(observation=value,record=record)
        except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
        save_json(destination,result);errors=errors+1 if result['error'] else 0
        with(out/'run.log').open('a') as f:f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case':case,'accepted':result['record'] is not None,'tokens':result.get('response',{}).get('completionTokens'),'latency_s':result.get('response',{}).get('latencySeconds'),'error':result['error']},flush=True)
        if errors>=3 or(result['error'] or '').startswith('RuntimeError:'):break
    rows=[read(p) for p in(out/'responses').glob('*.json')];attempts=len(list((out/'attempts').glob('*.json')));tokens=sum(r.get('response',{}).get('completionTokens',0) for r in rows);reserved=(attempts-sum(r.get('response') is not None for r in rows))*512
    assert attempts<=12 and tokens+reserved<=6144
    result={'cases':12,'attempts':attempts,'responses':len(rows),'accepted':sum(r['record'] is not None for r in rows),'completion_tokens':tokens,'reserved_completion_tokens':reserved,'complete':len(rows)==12,
        'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False};save_json(out/'results.json',result);print(result,flush=True)


def collect(out):
    if(out/'results.json').exists():raise ValueError('This diagnostic is already terminal; do not resume it')
    with Path('/tmp/calitree-local-gpu-experiment.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        collect_locked(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose prepare or collect')
    (prepare if a.prepare else collect)(a.output_dir.resolve())
