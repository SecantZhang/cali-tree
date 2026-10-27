"""Prepare/collect a separate12-case training-only compact-MLX observation view."""
import argparse
from importlib.metadata import version,distribution
import json
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.lm_engine.local_mlx_v118 import LocalMLXEngine,MEMORY_LIMIT,CACHE_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash,local_messages
from critical.logging.llm_history import LLMHistoryWriter

ROOT=Path(__file__).resolve().parents[1]
DOWNLOAD=ROOT/'logs/exps/261023-local-mlx-download-v116-r1/identity.json'
PREVIOUS=ROOT/'logs/exps/261023-local-grammar-v95-smoke-r1'
TEMPLATE=ROOT/'critical/core/prompts/templates/local_rubric_v94/observe.txt'
PACKAGES=('mlx','mlx-metal','mlx-lm','mlx-vlm','transformers','tokenizers','torch','torchvision','lm-format-enforcer','numpy','Pillow')


def read(path):return json.loads(Path(path).read_text())


def prepare(out):
    if out.exists():raise ValueError('Fresh MLX probe required')
    checkpoint=read(DOWNLOAD);assert checkpoint['status']=='complete'
    jobs=read(PREVIOUS/'jobs.json');references=read(PREVIOUS/'references.json');old_manifest=read(PREVIOUS/'manifest.json')
    assert digest(jobs)==old_manifest['jobs_ref'] and len(jobs)==12 and set(references)=={j['case'] for j in jobs}
    packages={p:version(p) for p in PACKAGES};assert packages['mlx-vlm']=='0.3.12' and packages['mlx']=='0.30.4' and packages['mlx-lm']=='0.30.7'
    assert packages['torch']=='2.9.0' and packages['torchvision']=='0.24.0' and packages['transformers']=='5.1.0' and packages['lm-format-enforcer']=='0.11.3'
    library_hashes={}
    for name in('mlx_vlm/generate.py','mlx_vlm/utils.py','mlx_vlm/models/qwen3_5/qwen3_5.py'):
        library_hashes[name]=file_hash(distribution('mlx-vlm').locate_file(name))
    profile={'checkpoint_ref':digest(checkpoint),'model':checkpoint['model'],'revision':checkpoint['revision'],'engine':LocalMLXEngine.name,
        'device':'metal','quantization':checkpoint['quantization'],'max_new_tokens':512,'max_pixels_per_image':256*32*32,'min_pixels_per_image':64*32*32,
        'do_sample':False,'enable_thinking':False,'decoder':'native-json-prefix-mlx-core-v118','termination':'recognized_model_and_tokenizer_end_tokens','schema_ref':digest(facts.schema()),'contract_ref':facts.CONTRACT_REF,
        'image_processor':'native_huggingface_fast','input_format':'native_pytorch_cpu_to_mlx','prefill_step_size':None,'memory_limit_bytes':MEMORY_LIMIT,'cache_limit_bytes':CACHE_LIMIT,
        'memory_limit_kind':'mlx_soft_guideline_with_peak_abort','engine_sha256':file_hash(ROOT/'critical/lm_engine/local_mlx_v118.py'),
        'packages':packages,'library_source_sha256':library_hashes}
    identity_ref=digest(profile);frozen=[]
    for original in jobs:
        j={k:v for k,v in original.items() if k!='request_ref'};assert j['schema']==facts.schema() and j['prompt']==facts.prompt(j['program'],TEMPLATE.read_text())
        j['identity_ref']=identity_ref;j['request_ref']=digest(j);frozen.append(j)
    protocol={'version':'compact-mlx-observer-probe-v119','cases':12,
        'selection':'Exactly the original v95 training-only balanced diagnostic (four/class, half old regular errors). No new sampling or held/reserved sources. Labels are stored only for offline analysis, never sent to the observer.',
        'view':'New pinned Qwen3.5-9B4bit MLX checkpoint with the same seven-field task/preservation prompt/schema and original image budget. Greedy, thinking disabled,512 output tokens. Native processor/model, no output repair.',
        'preflight':'Load/hash checkpoint/tokenizer/parser and rehearse first-input CPU image processing before any durable observation attempt. No task image is forwarded through the model during preflight. Runtime failure remains separate from observations.',
        'bounds':{'workers':1,'max_local_inferences':12,'max_new_tokens':6144,'retries':0},
        'protection':'No fitting or policy changes. Every failure remains failed; stop immediately on a native backend error, or after three consecutive observation/format failures. No API calls, uploads or reserved inputs.',
        'limit':'Training diagnostic and format/binding/semantic agreement only; not a population/pipeline accuracy result. A different model is not automatically more accurate.',
        'new_paid_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'identity.json',profile);save_json(out/'protocol.json',protocol);save_json(out/'jobs.json',frozen);save_json(out/'references.json',references)
    files=[Path(__file__),ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/lm_engine/local_qwen_v94.py',ROOT/'critical/core/decision/local_rubric_evidence_v94.py',TEMPLATE]
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    source_hashes={str(PREVIOUS/name):file_hash(PREVIOUS/name) for name in('jobs.json','manifest.json','references.json')}
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'identity_ref':identity_ref,'jobs_ref':digest(frozen),'checkpoint_identity_sha256':file_hash(DOWNLOAD),
        'source_hashes':source_hashes,'code_sha256':{str(p):file_hash(p) for p in files}})
    (out/'run.log').write_text('Prepared frozen12-case training-only compact-MLX observation probe; no inference/uploads.\n');(out/'llm-histories.log').touch()
    print({'cases':[j['case'] for j in frozen],'identity_ref':identity_ref,'max_tokens':6144,'new_paid_calls':0},flush=True)


def collect(out):
    manifest=read(out/'manifest.json');profile=read(out/'identity.json');checkpoint=read(DOWNLOAD);jobs=read(out/'jobs.json')
    assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(read(out/'protocol.json'))==manifest['protocol_ref']
    assert digest(checkpoint)==profile['checkpoint_ref'] and file_hash(DOWNLOAD)==manifest['checkpoint_identity_sha256']
    for p,sha in {**manifest['code_sha256'],**manifest['source_hashes']}.items():assert file_hash(p)==sha,p
    for package,expected in profile['packages'].items():assert version(package)==expected,package
    for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
    engine=LocalMLXEngine(checkpoint['destination'],checkpoint,history=LLMHistoryWriter(out/'llm-histories.log'),max_tokens=512,max_pixels=profile['max_pixels_per_image'])
    import mlx.core as mx
    previous_memory=mx.set_memory_limit(MEMORY_LIMIT);previous_cache=mx.set_cache_limit(CACHE_LIMIT)
    try:
        engine._load()
        first=jobs[0]
        media=[{'type':'text','text':'SOURCE image'},{'type':'image','path':first['evidence']['source_image']},
               {'type':'text','text':'EDITED image'},{'type':'image','path':first['evidence']['edited_image']}]
        messages,paths=local_messages(first['prompt'],media)
        prepared,rendered=engine._prepare_inputs(messages,paths)
        if mx.get_peak_memory()>MEMORY_LIMIT:raise RuntimeError('MLX model preflight exceeded8GiB; no observation may start')
        save_json(out/'preflight.json',{'passed':True,'neural_calls':0,'active_memory_bytes':mx.get_active_memory(),'peak_memory_bytes':mx.get_peak_memory(),
            'image_processor':type(engine._processor.image_processor).__name__,'tokenizer':type(engine._processor.tokenizer).__name__,'schema_ref':profile['schema_ref'],
            'processor_rehearsal_case':first['case'],'rendered_prompt_ref':digest(rendered),'input_shapes':{k:list(v.shape) for k,v in prepared.items()}})
        del prepared
        print({'preflight_passed':True,'active_memory_gib':mx.get_active_memory()/1024**3},flush=True)
    except Exception as exc:
        save_json(out/'preflight.json',{'passed':False,'error':type(exc).__name__+': '+str(exc),'neural_calls':0,
            'active_memory_bytes':mx.get_active_memory(),'peak_memory_bytes':mx.get_peak_memory()});raise
    finally:
        mx.synchronize();mx.clear_cache();mx.set_memory_limit(previous_memory);mx.set_cache_limit(previous_cache)
    (out/'responses').mkdir(exist_ok=True);(out/'attempts').mkdir(exist_ok=True);errors=0
    for job in jobs:
        case=job['case'];destination=out/'responses'/(case+'.json');attempt=out/'attempts'/(case+'.json')
        assert digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
        if destination.exists() or attempt.exists():continue
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        with attempt.open('x') as f:json.dump({'case':case,'request_ref':job['request_ref'],'status':'attempted'},f)
        result={'case':case,'request_ref':job['request_ref'],'observation':None,'record':None,'error':None}
        try:
            result['response']=engine.generate(job['prompt'],[
                {'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}],job['schema'])
            if result['response']['finishReason']!='stop':raise ValueError('MLX observation reached its frozen output cap')
            value=facts.validate(result['response']['parsed']);record=facts.bind(job['program'],pair,job['identity_ref'],job['prompt_ref'],value)
            facts.project(job['program'],pair,job['identity_ref'],job['prompt_ref'],record);result.update(observation=value,record=record)
        except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
        save_json(destination,result);errors=errors+1 if result['error'] else 0
        with (out/'run.log').open('a') as f:f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case':case,'accepted':result['record'] is not None,'latency_s':result.get('response',{}).get('latencySeconds'),'error':result['error']},flush=True)
        if errors>=3 or (result['error'] or '').startswith('RuntimeError:'):break
    responses=[read(p) for p in(out/'responses').glob('*.json')];attempts=len(list((out/'attempts').glob('*.json')))
    tokens=sum(r.get('response',{}).get('completionTokens',0) for r in responses);reserved=sum(r.get('response') is None for r in responses)*512+(attempts-len(responses))*512
    assert attempts<=12 and tokens+reserved<=6144
    result={'cases':12,'responses':len(responses),'attempted':attempts,'accepted':sum(r['record'] is not None for r in responses),'completion_tokens':tokens,'reserved_completion_tokens':reserved,
        'complete':len(responses)==12,'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False,'scope':'Training-only local observation diagnostic; not pipeline/population accuracy.'}
    save_json(out/'results.json',result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose --prepare or --collect')
    (prepare if a.prepare else collect)(a.output_dir.resolve())
