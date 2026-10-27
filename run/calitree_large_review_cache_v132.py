"""Collect the fixed224 review inputs under a verified bounded32B profile."""
import argparse
import fcntl
from importlib.metadata import distribution,version
import json
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.decision.bounded_local_schema_v131 import schema
from critical.lm_engine.local_mlx_large_v128 import LargeMLXEngine,MEMORY_LIMIT
from critical.lm_engine.local_mlx_v118 import CACHE_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_large_observer_probe_v129 import ROOT,DOWNLOAD,read


def prepare(legacy,legacy_audit,probe,probe_audit,out):
    if out.exists():raise ValueError('Fresh32B review-cache directory required')
    verified=read(legacy_audit/'verification.json');assert verified['passed'] and verified['complete'] and not verified['snapshot_only']
    assert read(legacy_audit/'manifest.json')['cache_manifest_sha256']==file_hash(legacy/'manifest.json')
    for file,sha in read(legacy_audit/'manifest.json')['source_hashes'].items():assert file_hash(file)==sha
    diagnostic=read(probe_audit/'verification.json');assert diagnostic['passed'] and diagnostic['complete'] and diagnostic['accepted']==12 and not diagnostic['snapshot_only']
    for file,sha in read(probe_audit/'manifest.json')['source_hashes'].items():assert file_hash(file)==sha
    profile=read(probe/'identity.json');assert profile['engine']==LargeMLXEngine.name and profile['evidence_max_chars']==360 and profile['schema_ref']==digest(schema())
    original=read(legacy/'jobs.json');memberships=read(legacy/'memberships.json');assert len(original)==224
    assert digest(original)==read(legacy/'manifest.json')['jobs_ref'] and digest(memberships)==read(legacy/'manifest.json')['memberships_ref']
    jobs=[]
    for old in original:
        j={k:v for k,v in old.items() if k!='request_ref'};j.update(identity_ref=digest(profile),schema=schema());j['request_ref']=digest(j);jobs.append(j)
    protocol={'version':'bounded32B-fixed-review-cache-v132','cases':224,'review_threshold':.8,
        'selection':'Exactly the frozen v96 actual/genuine-source-excluded review union and each fold membership. No reference/error-dependent new selection or source expansion.',
        'fold_control':'Each controller uses only its own actual/OOS review mask. Other-fold union availability or records outside that mask cannot become features or fit selectors.',
        'view':'Same verified bounded32B probe profile, original task/preservation prompt, original256 image-token budget and512 output tokens. Local joint comparison, not one call per predicate.',
        'cache':'Exact probe jobs may be reused with origin path/SHA, including failures. All other slots receive one attempt; no resampling or output repair.',
        'bounds':{'workers':1,'max_fresh_local_inferences':224,'max_new_tokens':114688,'retries':0},
        'protection':'No fitting during collection. Future scores include all276 development cases, all99/144 original checks and unchanged prior v72/v87 priority. Missing/failed records keep the prior decision.',
        'scope':'No API calls, uploads, reserved images or human-reference data sent to the observer. Training-diagnostic results are not a population accuracy claim.',
        'new_paid_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);save_json(out/'identity.json',profile);save_json(out/'jobs.json',jobs);save_json(out/'memberships.json',memberships)
    template=(probe/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text();dest=out/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt';dest.parent.mkdir(parents=True);dest.write_text(template)
    assert all(j['prompt']==facts.prompt(j['program'],template) for j in jobs)
    files=[Path(__file__),ROOT/'critical/lm_engine/local_mlx_large_v128.py',ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/lm_engine/local_qwen_v94.py',ROOT/'critical/core/decision/local_rubric_evidence_v94.py',ROOT/'critical/core/decision/bounded_local_schema_v131.py']
    for p in files:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    save_json(out/'manifest.json',{'identity_ref':digest(profile),'jobs_ref':digest(jobs),'memberships_ref':digest(memberships),'protocol_ref':digest(protocol),'template_ref':digest(template),
        'checkpoint_identity_sha256':file_hash(DOWNLOAD),'code_sha256':{str(p):file_hash(p) for p in files},'legacy_cache':str(legacy),'legacy_audit':str(legacy_audit),
        'legacy_manifest_sha256':file_hash(legacy/'manifest.json'),'legacy_audit_manifest_sha256':file_hash(legacy_audit/'manifest.json'),'probe':str(probe),'probe_audit':str(probe_audit),
        'probe_manifest_sha256':file_hash(probe/'manifest.json'),'probe_audit_manifest_sha256':file_hash(probe_audit/'manifest.json')})
    (out/'run.log').write_text('Prepared fixed224-input bounded32B review collection; no inference or fitting.\n');(out/'llm-histories.log').touch()
    save_json(out/'diagnostic_admission.json',{'warrant_correct_of12':diagnostic['new_warrant_correct_of12'],'old_warrant_correct_of12':diagnostic['old_warrant_correct_of12'],'limit':'Training diagnostic only; future276-case source-held evaluation is still required.'})
    print({'prepared':224,'profile_ref':digest(profile),'max_fresh_tokens':114688},flush=True)


def collect_locked(out):
    import os
    if os.environ.get('LMFE_STRICT_JSON_FIELD_ORDER','false').lower() not in('false','0',''):raise ValueError('Non-forced field-order profile required')
    manifest=read(out/'manifest.json');profile=read(out/'identity.json');jobs=read(out/'jobs.json');checkpoint=read(DOWNLOAD)
    assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and digest(read(out/'memberships.json'))==manifest['memberships_ref'] and digest(read(out/'protocol.json'))==manifest['protocol_ref']
    assert file_hash(DOWNLOAD)==manifest['checkpoint_identity_sha256'] and digest(checkpoint)==profile['checkpoint_ref']
    for p,sha in manifest['code_sha256'].items():assert file_hash(p)==sha
    for name,expected in profile['packages'].items():assert version(name)==expected
    for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
    probe=Path(manifest['probe']);assert file_hash(probe/'manifest.json')==manifest['probe_manifest_sha256']
    assert file_hash(Path(manifest['probe_audit'])/'manifest.json')==manifest['probe_audit_manifest_sha256']
    prior_jobs={j['case']:j for j in read(probe/'jobs.json')}
    engine=LargeMLXEngine(checkpoint['destination'],checkpoint,history=LLMHistoryWriter(out/'llm-histories.log'),max_tokens=512,max_pixels=profile['max_pixels_per_image'])
    (out/'responses').mkdir(exist_ok=True);(out/'attempts').mkdir(exist_ok=True);errors=0
    for job in jobs:
        case=job['case'];destination=out/'responses'/(case+'.json');attempt=out/'attempts'/(case+'.json')
        assert digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
        if destination.exists() or attempt.exists():continue
        prior=probe/'responses'/(case+'.json')
        if prior.exists():
            assert prior_jobs[case]==job
            result=read(prior);assert result['request_ref']==job['request_ref'];result.update(cache_origin=str(prior),cache_origin_sha256=file_hash(prior));save_json(destination,result)
            print({'case':case,'reused':True,'saved':len(list((out/'responses').glob('*.json')))},flush=True);continue
        hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
        with attempt.open('x') as f:json.dump({'case':case,'request_ref':job['request_ref'],'status':'attempted'},f)
        result={'case':case,'request_ref':job['request_ref'],'observation':None,'record':None,'error':None}
        try:
            result['response']=engine.generate(job['prompt'],[{'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}],job['schema'])
            if result['response']['finishReason']!='stop':raise ValueError('Large review observation reached its frozen output cap')
            value=facts.validate(result['response']['parsed'])
            if len(value['evidence'])>360:raise ValueError('Native bounded evidence exceeded360 characters')
            record=facts.bind(job['program'],pair,job['identity_ref'],job['prompt_ref'],value);result.update(observation=value,record=record)
        except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
        save_json(destination,result);errors=errors+1 if result['error'] else 0
        with(out/'run.log').open('a') as f:f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
        print({'case':case,'accepted':result['record'] is not None,'saved':len(list((out/'responses').glob('*.json'))),'latency_s':result.get('response',{}).get('latencySeconds'),'error':result['error']},flush=True)
        if errors>=3 or(result['error'] or '').startswith('RuntimeError:'):break
    rows=[read(p) for p in(out/'responses').glob('*.json')];fresh=[r for r in rows if 'cache_origin' not in r];attempts=len(list((out/'attempts').glob('*.json')))
    tokens=sum(r.get('response',{}).get('completionTokens',0) for r in fresh);reserved=(attempts-sum(r.get('response') is not None for r in fresh))*512
    assert attempts<=224 and tokens+reserved<=114688
    result={'cases':224,'responses':len(rows),'fresh_attempts':attempts,'reused':sum('cache_origin' in r for r in rows),'accepted':sum(r['record'] is not None for r in rows),'fresh_completion_tokens':tokens,'reserved_completion_tokens':reserved,
        'complete':len(rows)==224,'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False,'pipeline_accuracy_claim':False};save_json(out/'results.json',result);print(result,flush=True)


def collect(out):
    if(out/'results.json').exists():raise ValueError('Collector is terminal; do not resume')
    with Path('/tmp/calitree-local-gpu-experiment.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);collect_locked(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('legacy-cache','legacy-audit','probe','probe-audit'):p.add_argument('--'+name,type=Path)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose prepare or collect')
    if a.prepare:prepare(a.legacy_cache.resolve(),a.legacy_audit.resolve(),a.probe.resolve(),a.probe_audit.resolve(),a.output_dir.resolve())
    else:collect(a.output_dir.resolve())
