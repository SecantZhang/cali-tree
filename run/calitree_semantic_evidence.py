"""One label-blind semantic-contract extraction for each fixed four-group case."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.semantic_evidence import SCHEMA,SemanticEvidenceExtractor,prompt
from run.calitree_single_call import CAP,IDENTITY,ROOT,fingerprint,read

SOURCE=ROOT/'logs/exps/261013-four-groups-local-v4'
VERSION='fixed-four-groups-semantic-evidence-v5'


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():
        m=read(output/'manifest.json');verify(output,m);return m
    original=read(SOURCE/'manifest.json');cases=original['cases']
    if len(cases)!=48 or len({c['group'] for c in cases})!=48:raise ValueError('Fixed 48 unique cases required')
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_single_call.py']
    code={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);code[rel]=fingerprint(p)
    pinned=[SOURCE/n for n in ('manifest.json','seal.json','results.json','observations.json')]
    (output/'prompt.txt').write_text(prompt())
    m={'version':VERSION,'cases':cases,'judge_identity':IDENTITY,'workers':8,'max_calls':48,
       'draws_per_case':1,'http_attempts_per_slot':1,'presentation':'source_first','max_completion_tokens_per_case':CAP,
       'prompt_ref':digest(prompt()),'schema_ref':digest(SCHEMA),'code_hashes':code,
       'pinned_files':{str(p):fingerprint(p) for p in pinned},
       'scope':'New representation, exactly the fixed four 12-case groups. One new response per case; original responses/failures preserved.',
       'fit_spec':{'clusters':3,'cluster_inputs':'instruction-contract booleans only; no outcomes or labels',
                   'families':['unclustered ordinal score','semantic-cluster ordinal score'],
                   'nonzero_supervised_coefficients_max':4,'shared_thresholds':2,'nonnegative_integer_weights_max':3,
                   'weight_sum_max':6,'cluster_offsets':[-2,-1,0,1,2],'min_cluster_adjustment_sources':2,
                   'min_correct_sources_per_class':2,'primary':'mean of local accuracy and macro-F1'},
       'authorization':'Active goal: improve reusable local calibration/evidence/clustering on the fixed four groups; all LLM calls approved.'}
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)})
    save_json(output/'estimate.json',{'new_image_calls_max':48,'baseline_calls':0,'max_completion_tokens':48*CAP,
              'output_cost_ceiling_usd':48*CAP*10/1_000_000,'input_cost':'Additional; actual returned usage reported.'})
    verify(output,m);return m


def verify(output,m):
    if (digest(m)!=read(output/'seal.json')['manifest_ref'] or m['version']!=VERSION
       or m['judge_identity']!=IDENTITY or m['prompt_ref']!=digest(prompt()) or m['schema_ref']!=digest(SCHEMA)
       or (output/'prompt.txt').read_text()!=prompt()):raise ValueError('Changed semantic extraction protocol')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed fixed group/cache')
    for c in m['cases']:
        for k,p in c['evidence'].items():
            if fingerprint(p)!=c['image_hashes'][k]:raise ValueError('Changed fixed image')
    for rel,h in m['code_hashes'].items():
        if fingerprint(ROOT/rel)!=h or fingerprint(output/'source_snapshot'/rel)!=h:raise ValueError('Changed extractor code')


def execute(output,m,live):
    from critical import config
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT=ROOT;config.CREDENTIALS_FILE=ROOT/'.env';creds=None
    if live:
        require_live(True);creds=load_creds(provider='openai',engine='gpt')
        if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI only')
    def work(case):
        directory=output/'ledgers'/case['case']
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted new API call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort='high',temperature=None,
                max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=CAP,
                           scope_limits={'search':1,'final':1})
        row={k:case[k] for k in ('id','case','batch','instruction')};row.update(extraction=None,error=None)
        try:row['extraction']=SemanticEvidenceExtractor(calls).extract(case['instruction'],case['evidence'],case_id=case['id'],max_tokens=CAP)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            row['error']=type(exc).__name__+': '+str(exc);jobs=list((directory/'jobs').glob('*.json'))
            if jobs and (job:=read(jobs[0]))['outcome']!='completed':row['error']=job.get('error') or job['outcome']
        print({'case':case['case'],'observed':row['extraction'] is not None,'error':row['error']},flush=True);return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool:rows=list(pool.map(work,m['cases']))
    jobs=[read(p) for p in sorted((output/'ledgers').glob('*/jobs/*.json'))];responses=[j['response'] for j in jobs if j.get('response')]
    return {'version':VERSION,'observations':rows,'attempts':len(jobs),'outcomes':dict(Counter(j['outcome'] for j in jobs)),
            'input_tokens':sum(r.get('promptTokens',0) for r in responses),
            'completion_tokens':sum(r.get('completionTokens',0) for r in responses)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true');mode.add_argument('--live',action='store_true');mode.add_argument('--replay',action='store_true')
    a=p.parse_args();output=a.output_dir.resolve()
    if a.replay and not (output/'results.json').exists():raise ValueError('Replay needs results')
    m=prepare(output)
    if a.preflight:print({'ready':True,'cases':48,'max_calls':48,'fit_spec':m['fit_spec']});return
    result=execute(output,m,a.live);verify(output,m)
    if a.replay:
        if read(output/'results.json')!=result:raise ValueError('Replay changed evidence')
        save_json(output/'verification.json',{'exact_replay':True,'new_api_calls':0,'results_sha256':fingerprint(output/'results.json')})
    else:
        if (output/'results.json').exists() and read(output/'results.json')!=result:raise ValueError('Different saved result')
        save_json(output/'results.json',result)
        (output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/llm-histories.log'))))
    print({k:v for k,v in result.items() if k!='observations'})

if __name__=='__main__':main()
