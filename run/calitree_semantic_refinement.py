"""Versioned prose-only execution with teacher-derived semantic boundary anchors."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.calibration.policy_semantics import SemanticConditionPolicy
from critical.core.decision.semantic_policy_executor import prose_observations,schema,interpreted_record
from critical.core.decision.calls import DurableCalls
from critical.core.decision.artifacts import digest,save_json
from run.calitree_policy_translation import SOL_EVIDENCE
from run.calitree_single_call import ROOT,IDENTITY,read,fingerprint

PREVIOUS=ROOT/'logs/exps/261014-policy-semantic-translation-v8'
TEMPLATE=ROOT/'critical/core/prompts/templates/semantic_policy_execution_v9/refine_states.txt'
VERSION='teacher-anchored-semantic-prose-v9'
CAP=8192


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():m=read(output/'manifest.json');verify(output,m);return m
    previous=read(PREVIOUS/'manifest.json')
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_single_call.py']
    code={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);code[rel]=fingerprint(p)
    pinned=[PREVIOUS/'manifest.json',PREVIOUS/'certification.json',PREVIOUS/'language_results.json',SOL_EVIDENCE/'results.json']
    m={'version':VERSION,'cases':previous['cases'],'policies':previous['policies']['sol'],'judge_identity':IDENTITY,
       'max_calls':44,'cap':CAP,'workers':8,'prompt_ref':fingerprint(TEMPLATE),'code_hashes':code,
       'pinned_files':{str(p):fingerprint(p) for p in pinned},
       'change':'Two shared semantic definitions: intended-target scope and bounded residual versus material shortfall.',
       'training_provenance':'Developed after inspecting v8 local disagreements. Definitions general; no case names, specific objects, exact instructions, or reference labels in runtime rules.',
       'scope':'Post-hoc local semantic refinement, not an unbiased held-out or repeat-robustness result. All four fixed groups tested; no label/case substitutions.',
       'inputs':'Same cached Sol evidence prose; grades/scores/teacher labels/human labels stripped; no images.'}
    (output/'prompt.txt').write_text(TEMPLATE.read_text())
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)})
    save_json(output/'estimate.json',{'new_text_calls_max':44,'new_image_calls':0,'output_cost_ceiling_usd':44*CAP*10/1e6,'input_cost':'Additional; usage reported.'})
    verify(output,m);return m


def verify(output,m):
    if m['version']!=VERSION or digest(m)!=read(output/'seal.json')['manifest_ref'] or m['judge_identity']!=IDENTITY or m['prompt_ref']!=fingerprint(TEMPLATE) or (output/'prompt.txt').read_text()!=TEMPLATE.read_text():raise ValueError('Changed refinement protocol')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed source run')
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
    source={r['case']:r for r in read(SOL_EVIDENCE/'results.json')['observations']}
    def work(c):
        row={'case':c['case'],'batch':c['batch'],'execution':None,'error':None};old=source[c['case']]
        if old['extraction'] is None:row['error']='Preserved missing source evidence';return row
        policy=SemanticConditionPolicy.restore(m['policies'][c['batch']]);directory=output/'ledgers'/c['case']
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted API call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort=IDENTITY['reasoning_effort'],temperature=None,
                max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=CAP,scope_limits={'search':1,'final':1})
        try:
            value,ref=calls.call('semantic_policy_refined_states_v9',
                {'instruction':c['instruction'],'learned_semantic_policy':policy.render(),'observations':prose_observations(old['extraction']['observations'])},
                schema(policy),template=TEMPLATE.read_text(),slot='once',case_id=c['id'],max_tokens=CAP)
            record=interpreted_record(policy,value)
            row['execution']={'interpretation':value,'decision':policy.predict_records([record])[0],'execution_ref':ref}
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            row['error']=type(exc).__name__+': '+str(exc);files=list((directory/'jobs').glob('*.json'))
            if files and (job:=read(files[0]))['outcome']!='completed':row['error']=job.get('error') or job['outcome']
        print({'case':c['case'],'executed':row['execution'] is not None,'error':row['error']},flush=True);return row
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
        if result!=read(output/'language_results.json'):raise ValueError('Changed replay')
        save_json(output/'replay.json',{'exact_replay':True,'new_api_calls':0,'results_ref':fingerprint(output/'language_results.json')})
    else:
        if (output/'language_results.json').exists() and read(output/'language_results.json')!=result:raise ValueError('Changed saved run')
        save_json(output/'language_results.json',result)
        (output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/llm-histories.log'))))
    print({k:v for k,v in result.items() if k!='cases'})


if __name__=='__main__':main()
