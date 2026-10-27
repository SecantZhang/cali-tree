"""Frozen training-only order/consistency diagnostics, one shared local model."""
import argparse
from copy import deepcopy
from importlib.metadata import version,distribution
import json
from pathlib import Path
import shutil

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.lm_engine.local_mlx_evidence_first_v121 import EvidenceFirstEngine,schema
from critical.lm_engine.local_mlx_v118 import MEMORY_LIMIT,CACHE_LIMIT
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_mlx_observer_probe_v119 import read,ROOT,DOWNLOAD

ARMS=('order_only','order_clarified')


def prepare(previous,verified,out):
    if out.exists():raise ValueError('Fresh evidence-order study required')
    audit=read(verified/'verification.json');assert audit['passed'] and audit['complete'] and audit['accepted']==12
    prior=read(previous/'manifest.json');old_jobs=read(previous/'jobs.json');profile=read(previous/'identity.json')
    assert digest(old_jobs)==prior['jobs_ref'] and digest(profile)==prior['identity_ref']
    for file,sha in prior['code_sha256'].items():assert file_hash(file)==sha
    old_template=(previous/'source_snapshot/critical/core/prompts/templates/local_rubric_v94/observe.txt').read_text()
    line='"evidence": a concise visible source-to-edit comparison, at most 45 words.\n'
    assert old_template.count(line)==1
    marker='Return one JSON object with exactly these keys and values:\n';assert marker in old_template
    reordered=old_template.replace(line,'').replace(marker,marker+line)
    clarified=(ROOT/'critical/core/prompts/templates/local_evidence_first_v121/clarifications.txt').read_text()
    out.mkdir(parents=True);sources=[Path(__file__),ROOT/'critical/lm_engine/local_mlx_evidence_first_v121.py',ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/core/prompts/templates/local_evidence_first_v121/clarifications.txt']
    for source in sources:
        dest=out/'source_snapshot'/source.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    code={str(p):file_hash(p) for p in sources}
    for arm in ARMS:
        template=reordered if arm=='order_only' else reordered+'\n'+clarified
        identity=deepcopy(profile);identity.update(engine=EvidenceFirstEngine.name,schema_ref=digest(schema()),strict_field_order=True,evidence_max_chars=360,
            observer_template_ref=digest(template),engine_sha256=file_hash(ROOT/'critical/lm_engine/local_mlx_v118.py'),
            evidence_first_engine_sha256=file_hash(ROOT/'critical/lm_engine/local_mlx_evidence_first_v121.py'))
        jobs=[]
        for old in old_jobs:
            job={k:v for k,v in old.items() if k!='request_ref'};job.update(prompt=facts.prompt(job['program'],template),schema=schema(),identity_ref=digest(identity))
            job['prompt_ref']=digest(job['prompt']);job['request_ref']=digest(job);jobs.append(job)
        folder=out/arm;save_json(folder/'identity.json',identity);save_json(folder/'jobs.json',jobs);save_json(folder/'references.json',read(previous/'references.json'));(folder/'template.txt').write_text(template)
        save_json(folder/'manifest.json',{'identity_ref':digest(identity),'jobs_ref':digest(jobs),'template_ref':digest(template),'code_sha256':code,'checkpoint_identity_sha256':file_hash(DOWNLOAD),
            'prior_manifest_sha256':file_hash(previous/'manifest.json'),'prior_audit_manifest_sha256':file_hash(verified/'manifest.json')})
        (folder/'llm-histories.log').touch();(folder/'run.log').write_text('Frozen training-only evidence-first observation arm.\n')
    protocol={'version':'evidence-first-local-diagnostic-v122','arms':ARMS,'cases_per_arm':12,
        'selection':'Exactly the same12 balanced original-training cases as v119. No new sampling, fitting or held/reserved inputs.',
        'changes':'Both arms use native enforced evidence-first JSON and a360-character evidence limit. Order-only reorders the original prompt field listing; clarified also instructs agreement between visible evidence and categorical states, required relation anchors and comparative progress.',
        'model':'Same pinned Qwen3.5-9B4bit model, original image budget, greedy nonthinking decoding. One shared model, sequential arms, no response reuse or repair.',
        'bounds':{'max_local_inferences':24,'max_new_tokens':12288,'workers':1,'retries':0},
        'limit':'Training-only diagnostic. No population/pipeline accuracy claim or serving change follows. Earlier failed/runtime profiles stay preserved.',
        'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False}
    save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Prepared two frozen evidence-first training diagnostics, no inference.\n');(out/'llm-histories.log').write_text('Per-arm native histories are stored in each arm directory; no root-level inference.\n')
    print({'arms':ARMS,'cases_per_arm':12,'max_local_tokens':12288},flush=True)


def collect(out):
    import os
    if os.environ.get('LMFE_STRICT_JSON_FIELD_ORDER','').lower() not in('true','1'):raise ValueError('Native strict JSON ordering must be enabled')
    checkpoint=read(DOWNLOAD);engine=None;all_results={}
    for arm in ARMS:
        folder=out/arm;manifest=read(folder/'manifest.json');profile=read(folder/'identity.json');jobs=read(folder/'jobs.json')
        assert digest(profile)==manifest['identity_ref'] and digest(jobs)==manifest['jobs_ref'] and file_hash(DOWNLOAD)==manifest['checkpoint_identity_sha256']
        for source,sha in manifest['code_sha256'].items():assert file_hash(source)==sha
        for package,expected in profile['packages'].items():assert version(package)==expected
        for name,sha in profile['library_source_sha256'].items():assert file_hash(distribution('mlx-vlm').locate_file(name))==sha
        if engine is None:engine=EvidenceFirstEngine(checkpoint['destination'],checkpoint,max_tokens=512,max_pixels=profile['max_pixels_per_image'])
        engine.history=LLMHistoryWriter(folder/'llm-histories.log');(folder/'responses').mkdir(exist_ok=True);(folder/'attempts').mkdir(exist_ok=True);errors=0
        for job in jobs:
            case=job['case'];destination=folder/'responses'/(case+'.json');attempt=folder/'attempts'/(case+'.json')
            if destination.exists() or attempt.exists():continue
            assert digest({k:v for k,v in job.items() if k!='request_ref'})==job['request_ref']
            hashes,pair=image_identity(job['evidence']);assert hashes==job['image_hashes'] and pair==job['image_pair_ref']
            with attempt.open('x') as f:json.dump({'case':case,'request_ref':job['request_ref'],'status':'attempted'},f)
            result={'case':case,'request_ref':job['request_ref'],'observation':None,'record':None,'error':None}
            try:
                result['response']=engine.generate(job['prompt'],[
                    {'type':'text','text':'SOURCE image'},{'type':'image','path':job['evidence']['source_image']},
                    {'type':'text','text':'EDITED image'},{'type':'image','path':job['evidence']['edited_image']}],job['schema'])
                if result['response']['finishReason']!='stop':raise ValueError('Evidence-first observation reached its frozen token cap')
                value=facts.validate(result['response']['parsed'])
                assert list(result['response']['parsed'])==schema()['required'],'Native evidence-first field order was not respected'
                record=facts.bind(job['program'],pair,job['identity_ref'],job['prompt_ref'],value);result.update(observation=value,record=record)
            except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
            save_json(destination,result);errors=errors+1 if result['error'] else 0
            with(folder/'run.log').open('a') as f:f.write(case+' '+('accepted' if result['record'] else result['error'])+'\n')
            print({'arm':arm,'case':case,'accepted':result['record'] is not None,'error':result['error']},flush=True)
            if errors>=3 or (result['error'] or '').startswith('RuntimeError:'):break
        rows=[read(p) for p in(folder/'responses').glob('*.json')];attempts=len(list((folder/'attempts').glob('*.json')));tokens=sum(r.get('response',{}).get('completionTokens',0) for r in rows)
        reserved=(attempts-sum(r.get('response') is not None for r in rows))*512
        assert attempts<=12 and tokens+reserved<=6144
        result={'cases':12,'attempts':attempts,'responses':len(rows),'accepted':sum(r['record'] is not None for r in rows),'completion_tokens':tokens,'reserved_completion_tokens':reserved,'complete':len(rows)==12,
            'new_paid_calls':0,'reserved_sources_used':0,'fitting_performed':False};save_json(folder/'results.json',result);all_results[arm]=result
        print({'arm':arm,'result':result},flush=True)
        if not result['complete']:break
    save_json(out/'results.json',all_results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous-probe',type=Path);p.add_argument('--previous-audit',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--collect',action='store_true');a=p.parse_args()
    if a.prepare==a.collect:p.error('Choose prepare or collect')
    if a.prepare:prepare(a.previous_probe.resolve(),a.previous_audit.resolve(),a.output_dir.resolve())
    else:collect(a.output_dir.resolve())
