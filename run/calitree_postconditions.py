"""Instruction-only postcondition compilation for the fixed cached fact cases."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.postcondition_binding import PostconditionCompiler,SCHEMA,TEMPLATE
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.calls import DurableCalls
from run.calitree_observable_facts import prepare as facts_prepare
from run.calitree_single_call import ROOT,IDENTITY,read,fingerprint

FACTS=ROOT/'logs/exps/261014-observable-semantic-facts-v10'
VERSION='instruction-bound-physical-programs-v12'
CAP=4096


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():m=read(output/'manifest.json');verify(output,m);return m
    parent=facts_prepare(FACTS);observed=read(FACTS/'facts.json');available={r['case'] for r in observed['cases'] if r['extraction']}
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_single_call.py']
    code={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);code[rel]=fingerprint(p)
    m={'version':VERSION,'cases':parent['cases'],'available_cases':sorted(available),'identity':IDENTITY,
       'max_calls':len(available),'workers':8,'cap':CAP,'prompt_ref':fingerprint(TEMPLATE),'schema_ref':digest(SCHEMA),
       'code_hashes':code,'facts_ref':fingerprint(FACTS/'facts.json'),
       'input':'Instruction and closed physical predicate definitions only. No observations, ratings, teacher decisions or human labels.',
       'scope':'Local semantic-program induction; physical evidence is unchanged and no new images are used.'}
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)});(output/'prompt.txt').write_text(TEMPLATE.read_text())
    save_json(output/'estimate.json',{'max_text_calls':len(available),'new_images':0,'output_cost_ceiling_usd':len(available)*CAP*10/1e6,'input_cost':'Additional; returned usage reported.'})
    verify(output,m);return m


def verify(output,m):
    if digest(m)!=read(output/'seal.json')['manifest_ref'] or m['version']!=VERSION or m['identity']!=IDENTITY or m['prompt_ref']!=fingerprint(TEMPLATE) or m['schema_ref']!=digest(SCHEMA) or m['facts_ref']!=fingerprint(FACTS/'facts.json'):raise ValueError('Changed postcondition protocol')
    for rel,h in m['code_hashes'].items():
        if fingerprint(ROOT/rel)!=h or fingerprint(output/'source_snapshot'/rel)!=h:raise ValueError('Changed frozen source '+rel)


def collect(output,m,live):
    from critical import config
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT=ROOT;config.CREDENTIALS_FILE=ROOT/'.env';creds=None
    if live:
        require_live(True);creds=load_creds(provider='openai',engine='gpt')
        if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI only')
    def work(c):
        row={'case':c['case'],'compilation':None,'error':None}
        if c['case'] not in m['available_cases']:row['error']='Preserved missing observations';return row
        directory=output/'ledgers'/c['case']
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted new model call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort=IDENTITY['reasoning_effort'],temperature=None,
                max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=CAP,scope_limits={'search':1,'final':1})
        try:row['compilation']=PostconditionCompiler(calls).compile(c['instruction'],case_id=c['id'],max_tokens=CAP)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:row['error']=type(exc).__name__+': '+str(exc)
        print({'case':c['case'],'compiled':row['compilation'] is not None,'error':row['error']},flush=True);return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool:rows=list(pool.map(work,m['cases']))
    jobs=[read(p) for p in sorted((output/'ledgers').glob('*/jobs/*.json'))];responses=[j['response'] for j in jobs if j.get('response')]
    return {'version':VERSION,'cases':rows,'attempts':len(jobs),'outcomes':dict(Counter(j['outcome'] for j in jobs)),
       'input_tokens':sum(r.get('promptTokens',0) for r in responses),'completion_tokens':sum(r.get('completionTokens',0) for r in responses)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    for name in ('preflight','live','replay'):mode.add_argument('--'+name,action='store_true')
    a=p.parse_args();output=a.output_dir.resolve();m=prepare(output)
    if a.preflight:print(read(output/'estimate.json'));return
    result=collect(output,m,a.live);verify(output,m)
    if a.replay:
        if result!=read(output/'programs.json'):raise ValueError('Changed replay')
        save_json(output/'replay.json',{'exact_replay':True,'new_api_calls':0,'programs_ref':fingerprint(output/'programs.json')})
    else:
        if (output/'programs.json').exists() and read(output/'programs.json')!=result:raise ValueError('Changed saved programs')
        save_json(output/'programs.json',result);(output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/llm-histories.log'))))
    print({k:v for k,v in result.items() if k!='cases'})


if __name__=='__main__':main()
