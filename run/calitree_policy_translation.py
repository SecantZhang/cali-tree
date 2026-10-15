"""Compile learned policies and test grade-blind semantic execution on local cases."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import shutil

from critical.core.calibration.policy_semantics import SemanticConditionPolicy,semantic_record
from critical.core.calibration.visibility_calibration import VisibilityOrdinalCalibrator
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.decision.semantic_policy_executor import SemanticPolicyExecutor,TEMPLATE
from critical.core.decision.calls import DurableCalls
from critical.core.decision.artifacts import digest,save_json
from critical.core.decision.semantic_evidence import QUALITIES,DESCRIPTORS
from run.calitree_instruction_rules import load_inputs,FIXED,SOL,SOL_EVIDENCE,FAST
from run.calitree_single_call import ROOT,IDENTITY,read,fingerprint

VERSION='learned-policy-semantic-translation-v8'
TEXT_CAP=8192


def prepare(output):
    output.mkdir(parents=True,exist_ok=True)
    if (output/'manifest.json').exists():m=read(output/'manifest.json');verify(output,m);return m
    cases=read(FIXED/'manifest.json')['cases']
    source={'cases':cases,'models':['sol','luna','mini_normalized']};data=load_inputs(source)
    policies={k:{g:SemanticConditionPolicy.from_teacher(a).metadata() for g,a in value['old_policies'].items()} for k,value in data.items()}
    files=[p for p in (ROOT/'critical').rglob('*') if p.is_file() and p.suffix in ('.py','.txt','.json')]
    files += [Path(__file__).resolve(),ROOT/'run/calitree_instruction_rules.py',ROOT/'run/calitree_single_call.py',
              ROOT/'tests/unit/calitree/test_policy_semantics.py',ROOT/'tests/unit/calitree/test_semantic_policy_executor.py']
    hashes={}
    for p in files:
        rel=str(p.relative_to(ROOT));dst=output/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);hashes[rel]=fingerprint(p)
    pinned=[FIXED/'manifest.json',SOL/'results.json',SOL_EVIDENCE/'results.json',FAST/'manifest.json',FAST/'results.json',FAST/'observations.json']
    (output/'execution_prompt.txt').write_text(TEMPLATE.read_text())
    for key,groups in policies.items():
        for group,a in groups.items():
            p=SemanticConditionPolicy.restore(a);dst=output/'rules'/key/group;dst.mkdir(parents=True,exist_ok=True)
            save_json(dst/'policy.json',a);(dst/'policy.txt').write_text(p.render()+'\n')
    missing=sum(x is None for x in data['sol']['records'])
    m={'version':VERSION,**source,'policies':policies,'code_hashes':hashes,'pinned_files':{str(p):fingerprint(p) for p in pinned},
       'translation':'Minimal sufficient conjunctions of named semantic evidence states; no arithmetic during rule execution.',
       'certification':'Exhaustive known/full-unknown domain on every dependent feature, plus missing-response invariant and all cached local cases.',
       'live_model':IDENTITY,'workers':8,'live_cases_model':'sol','text_cap':TEXT_CAP,'max_text_calls':48-missing,
       'live_input':'Cached Sol prose only; no images, grades, weights, numerical cuts, teacher predictions, human labels, or examples.',
       'live_output':'Named per-feature states, then deterministic semantic condition execution. One durable call per available case.',
       'scope':'Same-case local translation, not a held-out generalization experiment. No case lookups or new image judgments.',
       'prompt_ref':fingerprint(TEMPLATE)}
    save_json(output/'manifest.json',m);save_json(output/'seal.json',{'manifest_ref':digest(m)})
    save_json(output/'estimate.json',{'new_text_calls_max':m['max_text_calls'],'new_image_calls':0,
        'output_cost_ceiling_usd':m['max_text_calls']*TEXT_CAP*10/1e6,'input_cost':'Additional; returned usage reported.'})
    verify(output,m);return m


def verify(output,m):
    if m['version']!=VERSION or digest(m)!=read(output/'seal.json')['manifest_ref'] or m['live_model']!=IDENTITY or m['prompt_ref']!=fingerprint(TEMPLATE):raise ValueError('Changed semantic-translation protocol')
    for p,h in m['pinned_files'].items():
        if fingerprint(p)!=h:raise ValueError('Changed prior input')
    for rel,h in m['code_hashes'].items():
        if fingerprint(ROOT/rel)!=h or fingerprint(output/'source_snapshot'/rel)!=h:raise ValueError('Changed frozen source '+rel)
    for key,groups in m['policies'].items():
        for g,a in groups.items():
            dst=output/'rules'/key/g
            if read(dst/'policy.json')!=a or (dst/'policy.txt').read_text()!=SemanticConditionPolicy.restore(a).render()+'\n':raise ValueError('Changed semantic rule')


def certify(output,m):
    data=load_inputs(m);result={'version':VERSION,'models':{},'new_api_calls':0}
    for key,d in data.items():
        groups={};all_teacher=[];all_semantic=[];all_targets=[]
        for group,artifact in d['old_policies'].items():
            teacher=VisibilityOrdinalCalibrator.restore(artifact);policy=SemanticConditionPolicy.restore(m['policies'][key][group])
            dependent=[i for i,w in enumerate(artifact['weights']) if w]
            if artifact['uninspectable_label'] is not None:dependent=sorted(set(dependent)|{0,1})
            domain=[]
            for values in product(range(6),repeat=len(dependent)):
                lo=[4]*8;hi=[4]*8
                for i,v in zip(dependent,values):lo[i]=0 if v==5 else v;hi[i]=4 if v==5 else v
                domain.append({'lower':lo,'upper':hi,'descriptor':[1]+[0]*(len(DESCRIPTORS)-1)})
            p=[r['prediction'] for r in teacher.predict_records(domain)]
            q=[r['prediction'] for r in policy.predict_records(map(semantic_record,domain))]
            if p!=q:raise AssertionError('Semantic translation changed the teacher domain')
            missing={'lower':[0]*8,'upper':[4]*8,'descriptor':None}
            if not teacher.predict_records([missing])[0]['prediction']==policy.predict_records([semantic_record(missing)])[0]['prediction']==-1:raise AssertionError('Missing response changed')
            # All cached cases also test use outside the teacher's fitted group.
            all_p=[r['prediction'] for r in teacher.predict_records(d['old_features'])]
            all_q=[r['prediction'] for r in policy.predict_records(map(semantic_record,d['old_features']))]
            if all_p!=all_q:raise AssertionError('Cached prediction fidelity changed')
            idx=[i for i,c in enumerate(m['cases']) if c['batch']==group];targets=[('no','partial','yes').index(m['cases'][i]['reference']) for i in idx]
            local_p=[all_p[i] for i in idx];local_q=[all_q[i] for i in idx]
            groups[group]={'teacher_metrics':classification_metrics(local_p,targets)[0],
                'semantic_metrics':classification_metrics(local_q,targets)[0],'teacher_fidelity':1.0,
                'certified_domain_records':len(domain),'cached_records_tested':48,
                'conditions':{k:len(policy.metadata()[k]) for k in ('at_least_partial','yes')},
                'cases':[{'case':m['cases'][i]['case'],'reference':t,'teacher_prediction':a,'semantic_prediction':b} for i,t,a,b in zip(idx,targets,local_p,local_q)]}
            all_teacher+=local_p;all_semantic+=local_q;all_targets+=targets
            print({'model':key,'group':group,'correct':sum(a==b for a,b in zip(local_q,targets)),'certified':len(domain),'fidelity':True},flush=True)
        result['models'][key]={'groups':groups,'teacher_metrics':classification_metrics(all_teacher,all_targets)[0],
            'semantic_metrics':classification_metrics(all_semantic,all_targets)[0],'teacher_fidelity':1.0}
    if (output/'certification.json').exists() and read(output/'certification.json')!=result:raise ValueError('Changed certification')
    save_json(output/'certification.json',result);return result


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
        row={'case':c['case'],'batch':c['batch'],'execution':None,'error':None}
        original=source[c['case']]
        if original['extraction'] is None:row['error']='Preserved missing source evidence';return row
        directory=output/'ledgers'/c['case'];policy=SemanticConditionPolicy.restore(m['policies']['sol'][c['batch']])
        if not live and not list((directory/'jobs').glob('*.json')):raise ValueError('Missing replay slot')
        def factory(cap):
            if not live:raise AssertionError('Replay attempted new API call')
            return get_engine('gpt',creds=creds,model=IDENTITY['model'],reasoning_effort=IDENTITY['reasoning_effort'],temperature=None,
                max_tokens=cap,timeout=180,max_http_attempts=1,history=LLMHistoryWriter(directory/'llm-histories.log'))
        calls=DurableCalls(directory,factory,identity=IDENTITY,max_calls=1,max_completion_tokens=TEXT_CAP,scope_limits={'search':1,'final':1})
        try:row['execution']=SemanticPolicyExecutor(calls).execute(policy,c['instruction'],original['extraction']['observations'],case_id=c['id'],max_tokens=TEXT_CAP)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            row['error']=type(exc).__name__+': '+str(exc);files=list((directory/'jobs').glob('*.json'))
            if files and (job:=read(files[0]))['outcome']!='completed':row['error']=job.get('error') or job['outcome']
        print({'case':c['case'],'executed':row['execution'] is not None,'error':row['error']},flush=True);return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool:rows=list(pool.map(work,m['cases']))
    jobs=[read(p) for p in sorted((output/'ledgers').glob('*/jobs/*.json'))];responses=[j['response'] for j in jobs if j.get('response')]
    result={'version':VERSION,'cases':rows,'attempts':len(jobs),'outcomes':dict(Counter(j['outcome'] for j in jobs)),
        'input_tokens':sum(r.get('promptTokens',0) for r in responses),'completion_tokens':sum(r.get('completionTokens',0) for r in responses)}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    for name in ('preflight','certify','live','replay'):mode.add_argument('--'+name,action='store_true')
    a=p.parse_args();output=a.output_dir.resolve();m=prepare(output)
    if a.preflight:print(read(output/'estimate.json'));return
    if a.certify:certify(output,m);return
    result=collect(output,m,a.live);verify(output,m)
    if a.replay:
        if result!=read(output/'language_results.json'):raise ValueError('Changed semantic interpretation replay')
        save_json(output/'replay.json',{'exact_replay':True,'new_api_calls':0,'language_results_ref':fingerprint(output/'language_results.json')})
    else:
        if (output/'language_results.json').exists() and read(output/'language_results.json')!=result:raise ValueError('Different saved language results')
        save_json(output/'language_results.json',result)
        (output/'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output/'ledgers').glob('*/llm-histories.log'))))
    print({k:v for k,v in result.items() if k!='cases'})


if __name__=='__main__':main()
