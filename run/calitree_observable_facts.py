"""Single label-blind extraction of operation-specific facts from cached prose."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.observable_facts import ObservableFactExtractor,PREDICATES,SCHEMA,TEMPLATE
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.calls import DurableCalls
from run.calitree_single_call import ROOT,IDENTITY,read,fingerprint

SOURCE=ROOT/'logs/exps/261014-semantic-contract-evidence-v5'
TEACHER=ROOT/'logs/exps/261014-semantic-visibility-calibration-v6'
VERSION='policy-to-grounded-facts-v10'
CAP=16384


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():m=read(output/'manifest.json');verify(output,m);return m
    cases=read(SOURCE/'manifest.json')['cases'];facts=read(SOURCE/'results.json')
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_single_call.py',ROOT/'tests/unit/calitree/test_observable_facts.py']
    code={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);code[rel]=fingerprint(p)
    pinned=[SOURCE/'manifest.json',SOURCE/'results.json',TEACHER/'results.json']
    m={'version':VERSION,'cases':cases,'judge_identity':IDENTITY,'predicate_bank':PREDICATES,
       'max_calls':sum(r['extraction'] is not None for r in facts['observations']),'workers':8,'cap':CAP,
       'prompt_ref':fingerprint(TEMPLATE),'schema_ref':digest(SCHEMA),'code_hashes':code,
       'pinned_files':{str(p):fingerprint(p) for p in pinned},
       'input':'Only instruction, fixed physical predicate questions, and grade-free cached prose. No teacher policy or case labels reach the fact extractor.',
       'fit_plan':{'families':['teacher-distilled factual tree','human-refined factual tree'],
          'primary_model':'sol/high','groups':['G1','G2','G3','G4'],'target_correct':[10,12,10,10],
          'inputs':'Boolean/NA/unknown observable facts only. No ordinal quality, score, ID, exact-instruction, object-name or operation-only class priors.',
          'max_depth':4,'max_leaves':6,'min_definite_leaf_sources':2,'min_correct_per_class':2,
          'objective':'Mean accuracy and macro-F1; worst recall and teacher fidelity as ties; then fewer splits.',
          'scope':'Fit and score the same fixed local cases. No held-out or repeat-robustness claim. Keep all missing/failed cases.'}}
    (output/'prompt.txt').write_text(TEMPLATE.read_text());save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)})
    save_json(output/'estimate.json',{'text_calls_max':m['max_calls'],'new_image_calls':0,'output_cost_ceiling_usd':m['max_calls']*CAP*10/1e6,'input_cost':'Additional, returned usage reported.'})
    verify(output,m);return m


def verify(output,m):
    if m['version']!=VERSION or digest(m)!=read(output/'seal.json')['manifest_ref'] or m['judge_identity']!=IDENTITY or m['predicate_bank']!=PREDICATES or m['prompt_ref']!=fingerprint(TEMPLATE) or m['schema_ref']!=digest(SCHEMA):raise ValueError('Changed observable-fact protocol')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed source')
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
    source={r['case']:r for r in read(SOURCE/'results.json')['observations']}
    def work(c):
        row={'case':c['case'],'batch':c['batch'],'extraction':None,'error':None};old=source[c['case']]
        if old['extraction'] is None:row['error']='Preserved missing source observation';return row
        directory=output/'ledgers'/c['case']
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted new model call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort=IDENTITY['reasoning_effort'],temperature=None,
               max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=CAP,scope_limits={'search':1,'final':1})
        try:row['extraction']=ObservableFactExtractor(calls).extract(c['instruction'],old['extraction']['observations'],case_id=c['id'],max_tokens=CAP)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            row['error']=type(exc).__name__+': '+str(exc);files=list((directory/'jobs').glob('*.json'))
            if files and (job:=read(files[0]))['outcome']!='completed':row['error']=job.get('error') or job['outcome']
        print({'case':c['case'],'extracted':row['extraction'] is not None,'error':row['error']},flush=True);return row
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
        if result!=read(output/'facts.json'):raise ValueError('Changed replay')
        save_json(output/'replay.json',{'exact_replay':True,'new_api_calls':0,'facts_ref':fingerprint(output/'facts.json')})
    else:
        if (output/'facts.json').exists() and read(output/'facts.json')!=result:raise ValueError('Changed saved facts')
        save_json(output/'facts.json',result)
        (output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/llm-histories.log'))))
    print({k:v for k,v in result.items() if k!='cases'})


if __name__=='__main__':main()
