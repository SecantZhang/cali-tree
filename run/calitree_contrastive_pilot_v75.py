"""Prepare a paid-gated, training-only matched-contrast semantic-judge pilot."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.optimization.prompt.calitree import contrastive_rubric_v75 as rubric
from critical.core.optimization.prompt.calitree import task_coverage as regular
from critical.core.decision.compiler import media_inputs
from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_rubric_v70 import data, FROZEN, VISION, ROOT, read, fingerprint
from run.calitree_m0 import pixel_hash

TEMPLATE = ROOT/'critical/core/prompts/templates/semantic_contrastive_v75/judge.txt'
LUNA = {'provider':'openai','model':'gpt-6-luna','temperature':0,'wire_reasoning_effort':'none'}
SOL = {'provider':'openai','model':'gpt-6.1-sol','temperature':None,'reasoning_effort':'medium'}
ARMS = {'regular_luna':(None,2048),'semantic_luna':(None,4096),'semantic_sol':('sol',8192)}
MAX_CALLS, MAX_OUTPUT = 72, 24*(2048+4096+8192)


def prepare(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    examples,_,_=data();raw={r['case']:r for r in read(FROZEN/'replay_inputs_without_references.json')}
    original=examples[:99];original_sources={e['source_group'] for e in original}
    rows=[{**e,'program':raw[e['case']]['program'],'evidence':raw[e['case']]['evidence']} for e in examples]
    available={e['case']:e for e in rows}
    selected,seen=[],set()
    # Choose scarce error strata first, independently of retrieval or new models.
    for correct,amount in ((False,3),(True,5)):
        labels=sorted((0,1,2),key=lambda label:sum(e['reference']==label and (e['regular']==e['reference'])==correct for e in original))
        for label in labels:
            candidates=sorted((e for e in original if e['reference']==label and (e['regular']==e['reference'])==correct),
                              key=lambda e:digest([rubric.VERSION,correct,label,e['source_group'],e['case']]))
            picked=0
            for e in candidates:
                if e['source_group'] in seen:continue
                selected.append(available[e['case']]);seen.add(e['source_group']);picked+=1
                if picked==amount:break
            if picked!=amount:raise ValueError('Insufficient distinct-source training error/control strata')
    selected.sort(key=lambda e:e['case'])
    assert len(selected)==len(seen)==24 and Counter(e['reference'] for e in selected)=={0:8,1:8,2:8}
    pool=[e for e in rows if e['source_group'] in original_sources and e['source_group'] not in seen and e['covered']]
    for e in pool:e['edited_pixel_hash']=pixel_hash(e['evidence']['edited_image'])
    recent_sources={e['source_group'] for e in examples[99:375]}
    reserved=read(ROOT/'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json')
    reserved_sources={e['source_group'] for e in reserved}
    assert not original_sources & (recent_sources|reserved_sources)
    jobs=[];images={}
    for i,query in enumerate(selected):
        chosen=rubric.contrasts(pool,query,seen)
        spec=rubric.request(query,chosen)
        contrast_sources=[a['source_group'] for a,b in chosen]
        for a,b in chosen:
            assert pixel_hash(a['evidence']['source_image'])==a['source_group']==pixel_hash(b['evidence']['source_image'])
        assert pixel_hash(query['evidence']['source_image'])==query['source_group']
        arms=list(ARMS);arms=arms[i%3:]+arms[:i%3]
        for arm in arms:
            route,cap=ARMS[arm]
            is_regular=arm=='regular_luna'
            job={'case':query['case'],'arm':arm,'route':route,'max_tokens':cap,
                 'payload':{'instruction':query['program']['instruction']} if is_regular else spec['payload'],
                 'media':media_inputs(query['evidence']) if is_regular else spec['media'],
                 'schema':regular.SCHEMA if is_regular else rubric.schema(spec['payload']),
                 'template':(regular.TEMPLATES/'regular.txt').read_text() if is_regular else TEMPLATE.read_text(),
                 'contrast_sources':[] if is_regular else contrast_sources,
                 'contrast_cases':[] if is_regular else [[a['case'],b['case']] for a,b in chosen]}
            jobs.append(job)
            for m in job['media']:
                if m['type']=='image':images[m['path']]=fingerprint(m['path'])
    out.mkdir(parents=True)
    protocol={'version':rubric.VERSION,'cases':24,'query_sources':24,'labels_per_class':8,
        'cached_errors':9,'cached_correct_controls':15,'arms':list(ARMS),'identities':{'luna':LUNA,'sol':SOL},
        'max_requests':MAX_CALLS,'max_completion_tokens':MAX_OUTPUT,'transport_retries':0,'certificate_repairs':0,
        'media_per_regular_request':2,'media_per_semantic_request':8,
        'scope':'Training diagnostic only. All24 query sources and all84 development sources are excluded from contrast retrieval. All80 reserved sources remain unused.',
        'retrieval':'Two matched source/instruction pairs: No versus Partial, and Partial versus Yes. Profile matching uses requested outcome kinds and fixed operation cues; never the query reference.',
        'rubric':'Explicit endpoint/progress/target/authorization/collateral grading principles, operation-specific checks and a bound query evidence certificate.',
        'cost':{'pricing_source':'https://developers.openai.com/api/docs/pricing','checked_on':'2026-10-23',
                'luna_input_per_million':.10,'luna_output_per_million':.50,'sol_input_per_million':2.,'sol_output_per_million':10.,
                'expected_usd_range':[.5,2.0],'completion_cap_usd':24*(2048+4096)*.5/1e6+24*8192*10/1e6,
                'input_charges_additional':True,'forecast_note':'Planning range from prior paired image diagnostics, without cache discounts; not a hard invoice or input-token cap.'},
        'paid_authorization_required':True,'new_model_calls':0,'serving_changed':False}
    code=[Path(__file__),Path(rubric.__file__),TEMPLATE,ROOT/'critical/core/decision/calls.py',ROOT/'critical/lm_engine/provider_api.py']
    save_json(out/'protocol.json',protocol);save_json(out/'cases.json',selected);save_json(out/'training_pool.json',pool);save_json(out/'jobs.json',jobs)
    save_json(out/'manifest.json',{'protocol_ref':digest(protocol),'jobs_ref':digest(jobs),'cases_ref':digest(selected),
        'pool_ref':digest(pool),'image_hashes':images,'code_sha256':{str(p):fingerprint(p) for p in code},
        'source_root':'/Users/zzhang/Documents/Projects/Adobe/calitree-mlsys'})
    (out/'run.log').write_text('Prepared24 training-only queries, source-excluded matched contrast retrieval and72 paid-gated requests. No paid calls authorized yet.\n')
    (out/'llm-histories.log').write_text('Zero model calls.\n')
    verify(out)
    print({'prepared_cases':24,'requests':72,'max_completion_tokens':MAX_OUTPUT,'cost':protocol['cost']},flush=True)


def verify(out):
    protocol,manifest=read(out/'protocol.json'),read(out/'manifest.json')
    jobs,cases,pool=read(out/'jobs.json'),read(out/'cases.json'),read(out/'training_pool.json')
    assert digest(protocol)==manifest['protocol_ref'] and digest(jobs)==manifest['jobs_ref']
    assert digest(cases)==manifest['cases_ref'] and digest(pool)==manifest['pool_ref']
    for name,sha in {**manifest['image_hashes'],**manifest['code_sha256']}.items():assert fingerprint(name)==sha,name
    assert len(jobs)==72 and sum(j['max_tokens'] for j in jobs)==MAX_OUTPUT
    assert Counter(j['arm'] for j in jobs)=={arm:24 for arm in ARMS}
    assert len({c['source_group'] for c in cases})==24
    query_sources={c['source_group'] for c in cases};query_by_case={c['case']:c for c in cases}
    assert not query_sources & {p['source_group'] for p in pool}
    for j in jobs:
        assert not query_sources & set(j['contrast_sources'])
        assert query_by_case[j['case']]['source_group'] not in j['contrast_sources']
        assert 'reference' not in j['payload'] and 'human_label' not in j['payload']
        assert j['payload']['instruction']==query_by_case[j['case']]['program']['instruction']
    return protocol


def collect_with_calls(out,calls):
    from critical.core.decision.calls import ProviderStopped,BudgetExhausted
    for j in read(out/'jobs.json'):
        target=out/'responses'/(j['case']+'-'+j['arm']+'.json')
        if target.exists():continue
        value,ref,error=None,None,None
        try:
            value,ref=calls.call('semantic_contrastive_v75',j['payload'],j['schema'],template=j['template'],
                media=j['media'],case_id=j['case'],slot=j['arm'],route=j['route'],max_tokens=j['max_tokens'])
            if j['arm']=='regular_luna':
                if set(value)!={'label','rationale'} or value['label'] not in (*rubric.LABELS,'unresolved') or not value['rationale'].strip():
                    raise ValueError('Invalid regular judgment')
            else:rubric.validate_certificate(j['payload'],value)
        except (ProviderStopped,BudgetExhausted):raise
        except (ValueError,RuntimeError,KeyError,TypeError) as exc:
            value,error=None,type(exc).__name__
        save_json(target,{'judgment':value,'execution_ref':ref,'error':error})
        print({'case':j['case'],'arm':j['arm'],'error':error},flush=True)


def collect(out,live=False):
    if not live:raise ValueError('Separate paid authorization and --live required')
    if (out/'mock_only.json').exists():raise ValueError('A mock rehearsal must never make paid calls')
    verify(out)
    from critical import config
    from critical.core.decision.calls import DurableCalls
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT=Path(read(out/'manifest.json')['source_root']);config.CREDENTIALS_FILE=config.PROJECT_ROOT/'.env'
    creds=load_creds(provider='openai',engine='gpt')
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official endpoint required')
    history=LLMHistoryWriter(out/'ledger/llm-histories.log')
    def luna(cap):return get_engine('gpt',creds=creds,model=LUNA['model'],temperature=0,max_tokens=cap,timeout=180,max_http_attempts=1,history=history)
    def sol(cap):return get_engine('gpt',creds=creds,model=SOL['model'],temperature=None,reasoning_effort='medium',max_tokens=cap,timeout=180,max_http_attempts=1,history=history)
    calls=DurableCalls(out/'ledger',luna,identity=LUNA,max_calls=MAX_CALLS,max_completion_tokens=MAX_OUTPUT,
        scope_limits={'search':3,'final':0},routes={'sol':{'identity':SOL,'engine_factory':sol}})
    collect_with_calls(out,calls);report(out)


def report(out):
    verify(out)
    rows=[]
    for case in read(out/'cases.json'):
        row={'case':case['case'],'reference':case['reference'],'cached_regular':case['regular']}
        for arm in ARMS:
            value=read(out/'responses'/(case['case']+'-'+arm+'.json'))['judgment']
            row[arm]=rubric.LABELS.index(value['label']) if value is not None and value['label'] in rubric.LABELS else -1
        rows.append(row)
    result={'cases':24,'scope':'Training-only diagnostic; not a generalization or over85% result.',
            'correct':{arm:sum(r[arm]==r['reference'] for r in rows) for arm in ('cached_regular',*ARMS)},'rows':rows}
    save_json(out/'results.json',result);print(result,flush=True)


def rehearse(prepared,out):
    """Exercise all durable slots and both model routes without network access."""
    import json
    from critical.core.decision.calls import DurableCalls
    verify(prepared)
    if out.exists():raise ValueError('Fresh mock output directory required')
    out.mkdir(parents=True)
    for name in ('protocol.json','manifest.json','jobs.json','cases.json','training_pool.json'):
        shutil.copyfile(prepared/name,out/name)
    save_json(out/'mock_only.json',{'network_calls':0,'benchmark_accuracy_not_computed':True})
    class Engine:
        def generate(self,prompt,**kwargs):
            payload=json.loads(prompt.split('INPUT_JSON: ',1)[1])
            if 'query_checks' not in payload:
                value={'label':'unresolved','rationale':'Offline rehearsal; no image judgment performed.'}
            else:
                check=next(c for c in payload['query_checks'] if c['role']=='outcome')
                value={'target_status':'uncertain','endpoint_status':'uncertain','progress_status':'uncertain',
                       'collateral_status':'uncertain','criterion':'insufficient_visual_evidence','label':'unresolved',
                       'rationale':'Offline rehearsal; no image judgment performed.',
                       'witnesses':[{'check_id':check['id'],'state':'unknown','source_observation':'Mock source.',
                                     'edited_observation':'Mock edited image.'}]}
            return {'parsed':value,'finishReason':'stop','completionTokens':1,'promptTokens':1}
    factory=lambda cap:Engine()
    calls=DurableCalls(out/'ledger',factory,identity=LUNA,max_calls=MAX_CALLS,max_completion_tokens=MAX_OUTPUT,
                       scope_limits={'search':3,'final':0},routes={'sol':{'identity':SOL,'engine_factory':factory}})
    collect_with_calls(out,calls)
    first=calls.budget['calls'];collect_with_calls(out,calls)
    assert first==calls.budget['calls']==72
    responses=[read(p) for p in (out/'responses').glob('*.json')]
    assert len(responses)==72 and not any(r['error'] for r in responses)
    result={'passed':True,'mock_requests':72,'requests_added_on_resume':0,'real_api_calls':0,
            'completion_reservation_cap':MAX_OUTPUT,'benchmark_accuracy_not_computed':True}
    save_json(out/'verification.json',result)
    (out/'run.log').write_text('All72 mock durable slots and Sol/Luna routes pass; resume makes zero new calls. No benchmark accuracy is inferred.\n')
    (out/'llm-histories.log').write_text('Mock only. Zero real model calls.\n')
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--prepared-dir',type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    for name in ('prepare','verify','live','report','rehearse'):mode.add_argument('--'+name,action='store_true')
    a=p.parse_args();out=a.output_dir.resolve()
    if a.prepare:prepare(out)
    elif a.verify:print(verify(out))
    elif a.live:collect(out,True)
    elif a.rehearse:
        if a.prepared_dir is None:p.error('--prepared-dir is required for rehearsal')
        rehearse(a.prepared_dir.resolve(),out)
    else:report(out)
