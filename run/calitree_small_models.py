"""Matched fast-model flat/evidence calls on the immutable four AURORA groups."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.semantic_evidence import SemanticEvidenceExtractor,SCHEMA,prompt
from critical.lm_engine.provider_api import chat_request
from run.calitree_benchmark36 import FLAT_SCHEMA,infer_arm
from run.calitree_single_call import ROOT,CAP,read,fingerprint

VERSION='fixed-four-groups-fast-models-v1'
FIXED=ROOT/'logs/exps/261013-four-groups-local-v4'
SOL=ROOT/'logs/exps/261014-semantic-visibility-calibration-v6'
MODELS={'luna':{'provider':'openai','model':'gpt-6-luna','reasoning_effort':'none','temperature':0},
        'mini':{'provider':'openai','model':'gpt-5.4-mini','reasoning_effort':'none','temperature':0}}
PRICES={'luna':{'input':.1,'output':.5},'mini':{'input':.75,'output':4.5}}
DOCS={'luna':'https://developers.openai.com/api/docs/models/gpt-6-luna',
      'mini':'https://developers.openai.com/api/docs/models/gpt-5.4-mini'}


def validate_settings():
    for identity in MODELS.values():
        # The existing adapter sets reasoning=none automatically for these
        # models; passing an explicit effort to this older adapter is rejected.
        _,body,_,_=chat_request('https://api.openai.com/v1','not-a-key',identity['model'],[],CAP,0,provider='openai')
        if body['reasoning_effort']!=identity['reasoning_effort'] or body['temperature']!=identity['temperature']:
            raise ValueError('Wire settings differ from declared fast profile')


def prepare(output,model_keys=('luna',)):
    output.mkdir(parents=True,exist_ok=True);validate_settings()
    selected={key:MODELS[key] for key in model_keys}
    if (output/'manifest.json').exists():
        m=read(output/'manifest.json')
        if m['models']!=selected:raise ValueError('Changed selected models')
        verify(output,m);return m
    cases=read(FIXED/'manifest.json')['cases']
    if len(cases)!=48 or len({c['group'] for c in cases})!=48:raise ValueError('Fixed 48 distinct sources required')
    for batch in ('G1','G2','G3','G4'):
        if Counter(c['reference'] for c in cases if c['batch']==batch)!={'no':4,'partial':4,'yes':4}:raise ValueError('Changed group balance')
    flat=FIXED/'flat_prompt.txt'
    if not flat.exists():flat=ROOT/'logs/exps/261013-flat-sol-high-balanced12/prompt.txt'
    (output/'flat_prompt.txt').write_text(flat.read_text());(output/'evidence_prompt.txt').write_text(prompt())
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_benchmark36.py',ROOT/'run/calitree_single_call.py']
    code={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dst);code[rel]=fingerprint(p)
    pinned=[FIXED/'manifest.json',FIXED/'results.json',SOL/'results.json',SOL/'fit_seal.json',flat]
    m={'version':VERSION,'cases':cases,'models':selected,'prices_per_million':{key:PRICES[key] for key in model_keys},'official_docs':{key:DOCS[key] for key in model_keys},
       'workers':8,'max_calls':96*len(selected),'max_completion_tokens_per_call':CAP,'draws_per_arm_per_case':1,
       'http_attempts_per_slot':1,'presentation':'source_first','arms':['flat','evidence'],
       'flat_prompt_ref':digest(flat.read_text()),'evidence_prompt_ref':digest(prompt()),
       'schemas':{'flat':digest(FLAT_SCHEMA),'evidence':digest(SCHEMA)},'code_hashes':code,
       'pinned_files':{str(p):fingerprint(p) for p in pinned},
       'fit_protocol':{'primary':'Refit the existing shared v6 policy separately within each unchanged 12-case group.',
          'controls':['same-model flat','frozen Sol shared v6 rules','matched-budget cluster-offset v6 rules'],
          'new_evidence_only':True,'router_inputs':'instruction-derived booleans only; no labels or grades',
          'budgets':'unchanged v6: four nonzero terms including offsets/visibility verdict, two shared cuts',
          'class_floor':2,'unresolved':'Retain all 12 references in scoring and all 48 in pooled metrics.',
          'infeasible':'Report no qualifying fit; retain all group cases as unresolved, no relaxed fallback.'},
       'scope':'Two fast profiles, same fixed cases/prompts. Local fitting is not held-out evaluation. No repeat judgments or substitutions.'}
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)})
    save_json(output/'estimate.json',{'max_calls':m['max_calls'],'per_model_calls':96,
       'max_output_cost_usd':{key:96*CAP*PRICES[key]['output']/1e6 for key in model_keys},
       'input_cost':'Additional. Output ceilings use full caps; expected usage is much lower. Failed calls may have unreturned usage.'})
    verify(output,m);return m


def verify(output,m):
    if (m['version']!=VERSION or digest(m)!=read(output/'seal.json')['manifest_ref'] or not m['models']
       or any(key not in MODELS or identity!=MODELS[key] for key,identity in m['models'].items())
       or digest((output/'evidence_prompt.txt').read_text())!=m['evidence_prompt_ref'] or digest(prompt())!=m['evidence_prompt_ref']
       or digest((output/'flat_prompt.txt').read_text())!=m['flat_prompt_ref']
       or m['schemas']!={'flat':digest(FLAT_SCHEMA),'evidence':digest(SCHEMA)}):raise ValueError('Changed fast-model protocol')
    if m['cases']!=read(FIXED/'manifest.json')['cases']:raise ValueError('Changed fixed cases')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed reference artifact')
    for rel,h in m['code_hashes'].items():
        if fingerprint(ROOT/rel)!=h or fingerprint(output/'source_snapshot'/rel)!=h:raise ValueError('Changed frozen code '+rel)
    for c in m['cases']:
        for k,p in c['evidence'].items():
            if fingerprint(p)!=c['image_hashes'][k]:raise ValueError('Changed image')


def collect(output,m,live):
    from critical import config
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT=ROOT;config.CREDENTIALS_FILE=ROOT/'.env';creds=None
    if live:
        require_live(True);creds=load_creds(provider='openai',engine='gpt')
        if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI only')
    tasks=[]
    for i,c in enumerate(m['cases']):
        for key in m['models']:
            for arm in (('flat','evidence') if i%2==0 else ('evidence','flat')):tasks.append((c,key,arm))
    def work(task):
        c,key,arm=task;identity=m['models'][key];directory=output/'ledgers'/key/c['case']/arm
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted an API call')
            return get_engine('gpt',creds=creds,model=identity['model'],temperature=0,max_tokens=cap,timeout=180,
                max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=identity,max_calls=1,max_completion_tokens=CAP,scope_limits={'search':1,'final':1})
        row={k:c[k] for k in ('case','id','batch','instruction')};row.update(model_key=key,arm=arm,error=None,prediction=None,extraction=None)
        try:
            if arm=='flat':row.update(infer_arm(c,'flat',calls,policy=None,flat_prompt=(output/'flat_prompt.txt').read_text()))
            else:row['extraction']=SemanticEvidenceExtractor(calls).extract(c['instruction'],c['evidence'],case_id=c['id'],max_tokens=CAP)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            row['error']=type(exc).__name__+': '+str(exc);jobs=list((directory/'jobs').glob('*.json'))
            if jobs and (job:=read(jobs[0]))['outcome']!='completed':row['error']=job.get('error') or job['outcome']
        print({'model':key,'case':c['case'],'arm':arm,'observed':row['extraction'] is not None if arm=='evidence' else row['prediction'] is not None,
               'error':row['error']},flush=True);return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool:rows=list(pool.map(work,tasks))
    return {'version':VERSION,'observations':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--models',nargs='+',choices=tuple(MODELS),default=['luna'])
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true');mode.add_argument('--live',action='store_true');mode.add_argument('--replay',action='store_true')
    a=p.parse_args();output=a.output_dir.resolve();m=prepare(output,a.models)
    if a.preflight:print(read(output/'estimate.json'));return
    if a.replay and not (output/'observations.json').exists():raise ValueError('Replay requires completed saved observations')
    observed=collect(output,m,a.live);verify(output,m)
    if a.replay:
        if observed!=read(output/'observations.json'):raise ValueError('Replay changed observations')
        save_json(output/'replay.json',{'exact_replay':True,'new_api_calls':0,'observations_ref':fingerprint(output/'observations.json')})
    else:
        if (output/'observations.json').exists() and read(output/'observations.json')!=observed:raise ValueError('Different saved observations')
        save_json(output/'observations.json',observed)
        (output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/*/*/llm-histories.log'))))
    print({'rows':len(observed['observations']),'errors':sum(r['error'] is not None for r in observed['observations'])})


if __name__=='__main__':main()
