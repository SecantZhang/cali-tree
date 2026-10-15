"""One text-only interpretation per observed development source; labels excluded."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.semantic_interpretation_v5 import VERSION, PROMPT, make_input, schema, validate
from critical.core.decision.bound_evidence_v2 import VERSION as M1_VERSION
from run.calitree_single_call import ROOT, IDENTITY, read, fingerprint

M0=ROOT/'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
SOURCES={'train':ROOT/'logs/exps/261014-m2-m4-bound-training48-v1',
         'validation':ROOT/'logs/exps/261014-m1-bound-evidence-development12-v2'}
CAP=8192


def inputs(partition):
    cases=read(M0/'splits'/(partition+'.json'))['cases']
    excluded={c['group'] for c in read(M0/'splits/test.json')['cases']}
    raw={r['case']:r for r in read(SOURCES[partition]/'observations.json')};result=[]
    for case in cases:
        assert case['group'] not in excluded
        row=raw[case['case']];payload=None
        if row['compilation'] is not None and row['observation'] is not None:
            pair=digest([M1_VERSION,'source_first',case['image_hashes']['source_image'],case['image_hashes']['edited_image']])
            p=row['compilation']['program'];assert p['instruction']==case['instruction']
            payload=make_input(p,row['observation']['observation'],pair)
        result.append({'case':case['case'],'source_group':case['group'],'payload':payload})
    return result


def exact(path,value):
    if path.exists():
        if read(path)!=value:raise ValueError('Changed saved interpretation artifact: '+str(path))
    else:save_json(path,value)


def prepare(out,partition):
    out.mkdir(parents=True,exist_ok=True);rows=inputs(partition)
    code=[Path(__file__).resolve(),ROOT/'critical/core/decision/semantic_interpretation_v5.py',
          ROOT/'critical/core/decision/calls.py',ROOT/'critical/core/decision/bound_evidence_v2.py',
          ROOT/'critical/core/decision/bound_evidence.py',ROOT/'critical/core/decision/compiler.py',
          ROOT/'run/calitree_single_call.py']
    sources=[M0/'completion_seal.json',M0/'splits'/(partition+'.json'),M0/'splits/test.json',SOURCES[partition]/'observations.json']
    manifest={'version':VERSION,'partition':partition,'identity':IDENTITY,'max_calls':sum(r['payload'] is not None for r in rows),
              'max_tokens_per_call':CAP,'workers':8,'image_calls':0,'attempts_per_case':1,'inputs_ref':digest(rows),
              'prompt_ref':digest(PROMPT),'schema_refs':{r['case']:digest(schema(r['payload'])) for r in rows if r['payload']},
              'code_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in code},
              'source_hashes':{str(p.relative_to(ROOT)):fingerprint(p) for p in sources},
              'scope':'Label-blind text interpretation of cached public AURORA instructions/physical observations. No final-test cases or new image presentations. One fixed model/profile; no retries.',
              'cost_change':'This experimental path adds one text-only interpretation call after the two M1 calls for a fresh case.'}
    exact(out/'manifest.json',manifest);exact(out/'inputs.json',rows)
    exact(out/'estimate.json',{'max_new_calls':manifest['max_calls'],'max_completion_tokens':CAP*manifest['max_calls'],
                             'new_image_calls':0,'reserved_test_calls':0,'prior_extraction_calls':143,
                             'budget_scope':'Separate bounded M2 interpretation experiment; original M0/M1 budgets and seals unchanged.'})
    for source in code:
        target=out/'source_snapshot'/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert fingerprint(target)==fingerprint(source)
        else:shutil.copyfile(source,target)
    return rows,manifest


def run(out,partition,mode):
    rows,manifest=prepare(out,partition)
    if mode=='preflight':print(read(out/'estimate.json'));return
    from critical import config
    from critical.lm_engine import get_engine,load_creds,require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT=ROOT;config.CREDENTIALS_FILE=ROOT/'.env';creds=None
    if mode=='live':
        require_live(True);creds=load_creds(provider='openai',engine='gpt')
        assert creds.provider=='openai' and creds.endpoints==['https://api.openai.com/v1']
    def work(row):
        case=row['case'];path=out/'cases'/(case+'.json');payload=row['payload']
        if payload is None:
            value={'case':case,'interpretation':None,'error':'missing_original_observation','execution_ref':None}
            exact(path,value);return value
        directory=out/'ledgers'/case
        if mode=='replay' and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if mode!='live':raise AssertionError('Replay attempted a model call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort=IDENTITY['reasoning_effort'],
                temperature=None,max_tokens=cap,timeout=180,max_http_attempts=1,
                history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=CAP,scope_limits={'search':1,'final':1})
        try:
            interpreted,ref=calls.call('instruction_relative_interpretation',payload,schema(payload),template=PROMPT,
                                        slot='once',max_tokens=CAP,case_id=case)
            validate(payload,interpreted)
            value={'case':case,'interpretation':interpreted,'error':None,'execution_ref':ref}
        except Exception as exc:
            value={'case':case,'interpretation':None,'error':type(exc).__name__+': '+str(exc),'execution_ref':None}
        exact(path,value);print({'case':case,'interpreted':value['interpretation'] is not None,'error':value['error']},flush=True)
        return value
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:result=list(pool.map(work,rows))
    exact(out/'interpretations.json',result)
    jobs=[read(p) for p in sorted((out/'ledgers').glob('*/jobs/*.json'))]
    assert len(jobs)<=manifest['max_calls'] and all(not j['media_identity'] for j in jobs)
    for row in rows:
        if row['payload']:
            found=[j for j in jobs if j['case_id']==row['case']]
            assert len(found)==1 and found[0]['payload']==row['payload']
    summary={'valid_interpretations':sum(r['interpretation'] is not None for r in result),'cases':len(rows),
             'attempts':len(jobs),'new_image_calls':0,'reserved_test_calls':0,
             'input_tokens':sum(j.get('response',{}).get('promptTokens',0) or 0 for j in jobs),
             'completion_tokens_returned':sum(j.get('response',{}).get('completionTokens',0) or 0 for j in jobs),
             'failures':[r for r in result if r['interpretation'] is None]}
    exact(out/'results.json',summary)
    if mode=='replay':exact(out/'replay.json',{'exact_replay':True,'new_model_calls':0,'results_sha256':fingerprint(out/'results.json')})
    print(summary)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--partition',choices=tuple(SOURCES),required=True)
    m=p.add_mutually_exclusive_group(required=True)
    for mode in ('preflight','live','replay'):m.add_argument('--'+mode,action='store_true')
    a=p.parse_args();run(a.output_dir.resolve(),a.partition,next(k for k in ('preflight','live','replay') if getattr(a,k)))
