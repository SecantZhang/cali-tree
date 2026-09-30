import json
from copy import deepcopy
from run.calitree_observation50 import compile_once, check_once, execute, summary
from critical.core.optimization.prompt.calitree.decomposition import FrozenCriteria, FrozenCriteriaExecutor
from .test_casewise_fitting import Engine, plan, check
from .test_decision_sets import images


def row(tmp_path):
    evidence, hashes = images(tmp_path)
    return {'instruction':'Close curtains','optimized_prompt':'rubric','plan':plan(),'task':'test',
            'plan_origin':'historical_frozen','feedback_used':True,'human_label':'no','criteria_origin':'test',
            'images':[{'path':evidence[k],'sha256':h} for k,h in zip(evidence,hashes)]}


def test_compilation_excludes_labels_feedback_and_images(tmp_path):
    r=row(tmp_path);e=Engine([plan()])
    result=compile_once(e,r,'template')
    assert result['outcome']=='completed'
    payload=json.loads(e.calls[0][0].split('INPUT_JSON: ')[1])
    assert payload=={'instruction':'Close curtains','optimized_prompt':'rubric'}
    assert e.calls[0][1]['media_inputs']==[]


def test_individual_checks_preserve_original_requests(tmp_path):
    r=row(tmp_path);one=Engine([check('absent')]);two=Engine([check('absent')])
    actual=check_once(one,r,r['plan']['conditions'][0])
    FrozenCriteriaExecutor(two,schema_retries=0).observe(FrozenCriteria.bind('rubric','Close curtains',r['plan']),
        prompt='rubric',instruction='Close curtains',evidence=dict(zip(('source_image','edited_image'),[i['path'] for i in r['images']])))
    assert one.calls==two.calls
    assert actual['outcome']=='completed'


def test_transport_failures_are_durable_and_other_checks_continue(tmp_path):
    r=row(tmp_path);out=tmp_path/'run';out.mkdir()
    r['plan']['conditions'].append({**r['plan']['conditions'][0],'id':'c2'})
    raw=[]
    class Responses(Engine):
        def generate(self,prompt,**kwargs):
            value=next(self.outputs);self.calls.append((prompt,kwargs))
            if isinstance(value,Exception):raise value
            return {'parsed':value,'content':json.dumps(value),'completionTokens':5,'promptTokens':10}
    def factory(tokens):
        e=Responses([] if tokens==2048 else [RuntimeError('connection'),check('partial'),check('absent'),check('partial')])
        e.max_tokens=tokens;raw.append(e);return e
    manifest={'rows':{'case':r},'compiler_template':'template'}
    result=execute(out,manifest,factory)
    assert result['usage']['calls']==4 and result['usage']['pending_or_failed']==1
    assert result['summary']['cases']['case']['predictions']==['unresolved','no']
    assert result['summary']['outcomes']=={'transport_error':1,'completed':3}
    replay=execute(out,manifest,lambda tokens: Engine([]))
    assert replay==result
    assert len(raw[1].calls)==4


def test_invalid_compilation_is_not_resampled(tmp_path):
    r=row(tmp_path);r['plan']=None;r['plan_origin']='new_luna'
    out=tmp_path/'run';out.mkdir()
    def factory(tokens):
        e=Engine([{'wrong':'format'}] if tokens==2048 else []);e.max_tokens=tokens;return e
    result=execute(out,{'rows':{'case':r},'compiler_template':'template'},factory)
    assert result['usage']['calls']==1
    assert result['summary']['outcomes']=={'invalid':1}
    assert not result['summary']['cases']['case']['plan_available']


def test_unknown_is_not_resolved_or_consistent_known(tmp_path):
    r=row(tmp_path)
    records={f'check/{i}/case/c1':{'outcome':'completed','check':check('unknown')} for i in range(2)}
    s=summary({'case':r},records)
    assert s['consistent_conditions']==1 and s['consistent_known_conditions']==0
    assert s['cases']['case']['predictions']==['unresolved','unresolved']


def test_three_consecutive_provider_failures_stop_remaining_jobs(tmp_path):
    r=row(tmp_path)
    r['plan']['conditions']=[{**r['plan']['conditions'][0],'id':f'c{i}'} for i in range(3)]
    out=tmp_path/'run';out.mkdir();calls=[]
    class Broken(Engine):
        def generate(self,*args,**kwargs):
            calls.append(1)
            raise RuntimeError('offline provider failure')
    def factory(tokens):
        e=Broken([]);e.max_tokens=tokens;return e
    result=execute(out,{'rows':{'case':r},'compiler_template':'template'},factory)
    assert len(calls)==3
    assert result['stop_reason'].startswith('Three consecutive')
    assert result['usage']['calls']==3
    assert result['summary']['outcomes']=={'transport_error':3}


def test_reserved_interrupted_job_is_not_resampled(tmp_path):
    import hashlib
    r=row(tmp_path);out=tmp_path/'run';(out/'jobs').mkdir(parents=True)
    key='check/0/case/c1'
    (out/'jobs'/(hashlib.sha256(key.encode()).hexdigest()+'.json')).write_text(
        json.dumps({'job_id':key,'outcome':'interrupted_or_pending'}))
    raw=[]
    def factory(tokens):
        e=Engine([check('complete')] if tokens==1024 else []);e.max_tokens=tokens;raw.append(e);return e
    result=execute(out,{'rows':{'case':r},'compiler_template':'template'},factory)
    assert len(raw[1].calls)==1
    assert result['summary']['cases']['case']['predictions']==['unresolved','yes']


def test_total_request_allowance_stops_before_extra_provider_call(tmp_path,monkeypatch):
    import run.calitree_observation50 as pilot
    monkeypatch.setattr(pilot,'MAX_CALLS',1)
    r=row(tmp_path);out=tmp_path/'run';out.mkdir();raw=[]
    def factory(tokens):
        e=Engine([check('complete')]);e.max_tokens=tokens;raw.append(e);return e
    result=execute(out,{'rows':{'case':r},'compiler_template':'template'},factory)
    assert result['usage']['calls']==1
    assert len(raw[1].calls)==1
    assert result['summary']['outcomes']=={'completed':1,'budget_exhausted':1}
