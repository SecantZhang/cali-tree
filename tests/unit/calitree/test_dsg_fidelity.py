"""Offline contracts for DSG graph semantics and original-score fidelity."""
from copy import deepcopy
import json
import pytest

from critical.core.decision import dsg
from critical.core.decision.artifacts import export_program
from critical.core.decision.calls import DurableCalls,CaseCalls
from critical.core.optimization.program.demo import seed_program,demo_case
from run.calitree_dsg_fidelity import execute,case_metrics,summary


def ingredients():
    tuples={'representable':True,'reason':'','nodes':[
        {'id':'A1','kind':'attribute','terms':['square','red'],'proposition':'The square is red',
         'source_quote':'red','role':'requested','outcome_ids':['o1']},
        {'id':'E1','kind':'entity','terms':['square'],'proposition':'The square is visible',
         'source_quote':'square','role':'support','outcome_ids':[]}]}
    questions={'questions':[{'id':'A1','question':'Is the square red?'},{'id':'E1','question':'Is the square visible?'}]}
    dependencies={'dependencies':[{'id':'A1','parents':['E1']},{'id':'E1','parents':[]}],'warnings':[]}
    return tuples,questions,dependencies


class Engine:
    def __init__(self,entity='yes',attribute='yes',audit=False,interrupt=False):
        self.entity=entity;self.attribute=attribute;self.audit=audit;self.interrupt=interrupt;self.requests=[]
    def generate(self,prompt,**kwargs):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.requests.append((payload,kwargs));tuples,questions,dependencies=ingredients()
        if 'max_tuples' in payload:value=tuples
        elif 'tuples' in payload:value=questions if prompt.startswith('Translate') else dependencies
        elif 'check' in payload:value={'status':'complete','evidence':'Red square visible'}
        elif 'tuple' in payload:
            if self.interrupt:self.interrupt=False;raise KeyboardInterrupt('Simulated interrupted VQA')
            value={'answer':self.entity if payload['tuple']['id']=='E1' else self.attribute,'evidence':'Visible fact'}
        elif 'observations' in payload:
            answers=[o['answer'] for o in payload['observations']]
            status='unknown' if 'unknown' in answers else 'absent' if 'no' in answers else 'complete'
            value={'outcomes':{'o1':{'status':status,'evidence':'From supplied observations'}}}
        elif 'graph' in payload:value={'accepted':self.audit,'issues':[] if self.audit else ['Diagnostic concern']}
        else:raise AssertionError(payload)
        return {'parsed':value,'model':'gpt-6-luna','completionTokens':15,'promptTokens':60,'finishReason':'stop'}


def manifest(case):
    return {'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','repeats':5,
        'max_calls':450,'max_completion_tokens':512000,'reserve_calls':370,'reserve_tokens':378880,'scope':'offline',
        'cases':[{'id':case.id,'instruction':case.instruction,'target':'no','evidence':case.evidence,'seed':export_program(seed_program())}]}


def test_full_comparison_preserves_original_and_isolates_labels(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);engine=Engine();root=tmp_path/'run'
    result=execute(root,m,lambda _:engine);assert result['status']=='completed'
    assert len(engine.requests)==24 # four preparation, five original, fifteen DSG
    row=result['cases'][case.id];metric=case_metrics(row,'no')
    assert metric['paired_agreement']==metric['paired_coverage']==1
    assert metric['original_reference_agreement']==metric['dsg_reference_agreement']==0
    assert metric['independent_cases']==1 and metric['repeats']==5
    assert metric['ordinal_mae']==0
    # A diagnostic audit does not silently discard the graph or cherry-pick scores.
    assert row['preparation']['audit']['accepted'] is False and row['completed']
    for payload,kwargs in engine.requests:
        assert not {'reference_label','target_label','original_prediction','feedback'} & set(payload)
        if 'check' in payload or 'tuple' in payload:assert len(kwargs['media_inputs'])==4
        else:assert kwargs['media_inputs']==[]
    before=len(engine.requests);budget=(root/'budget.json').read_bytes()
    assert execute(root,m,lambda _:engine)==result
    assert len(engine.requests)==before and (root/'budget.json').read_bytes()==budget
    changed=deepcopy(m);changed['cases'][0]['target']='yes'
    assert execute(root,changed,lambda _:engine)==result
    assert summary(result,changed)['dsg_reference_agreement']==1
    assert len(engine.requests)==before


@pytest.mark.parametrize('entity,answer,score,label',[('no','no',0,'no'),('unknown','unknown',None,None)])
def test_dependency_masking_and_unknowns(tmp_path,entity,answer,score,label):
    engine=Engine(entity=entity);case=demo_case(tmp_path/'images');graph=dsg.build_graph(seed_program(),*ingredients())
    assert [n['id'] for n in graph['nodes']]==['E1','A1']
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:engine,identity={'model':'gpt-6-luna'}),'dsg')
    row=dsg.execute(calls,graph,case.evidence,0)
    assert len(engine.requests)==2 # root and readout; dependent VQA skipped
    assert row['observations'][1]['answer']==answer and not row['observations'][1]['queried']
    assert row['dsg_score']==score and row['label']==label


def test_native_fraction_differs_from_requested_progress(tmp_path):
    engine=Engine(attribute='no');case=demo_case(tmp_path/'images');graph=dsg.build_graph(seed_program(),*ingredients())
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:engine,identity={'model':'gpt-6-luna'}),'dsg')
    row=dsg.execute(calls,graph,case.evidence,0)
    assert row['dsg_score']==0.5 and row['requested_fraction']==0 and row['label']=='no'


@pytest.mark.parametrize('fault',['cycle','orphan','missing_question','duplicate','arity','provenance','missing_coverage','too_many'])
def test_structural_validation(fault):
    t,q,p=ingredients()
    if fault=='cycle':p['dependencies'][1]['parents']=['A1']
    elif fault=='orphan':p['dependencies'][0]['parents']=[]
    elif fault=='missing_question':q['questions'].pop()
    elif fault=='duplicate':q['questions'][1]['question']=q['questions'][0]['question']
    elif fault=='arity':t['nodes'][0]['terms']=['red']
    elif fault=='provenance':t['nodes'][0]['source_quote']='unsupported words'
    elif fault=='missing_coverage':t['nodes'][0]['outcome_ids']=[]
    else:t['nodes']*=3
    with pytest.raises(ValueError):dsg.build_graph(seed_program(),t,q,p)


def test_single_global_property_is_allowed():
    t={'representable':True,'reason':'','nodes':[{'id':'G','kind':'global','terms':['red rendering'],
        'proposition':'Red rendering','source_quote':'red','role':'requested','outcome_ids':['o1']}]}
    graph=dsg.build_graph(seed_program(),t,{'questions':[{'id':'G','question':'Is the image rendered in red?'}]},
        {'dependencies':[{'id':'G','parents':[]}],'warnings':[]})
    assert len(graph['nodes'])==1


def test_schema_valid_hyphenated_ids_preserve_references():
    t,q,p=ingredients()
    mapping={'A1':'square-is-red','E1':'source-square'}
    for rows in (t['nodes'],q['questions'],p['dependencies']):
        for row in rows:
            row['id']=mapping[row['id']]
            if 'parents' in row:row['parents']=[mapping[key] for key in row['parents']]
    graph=dsg.build_graph(seed_program(),t,q,p)
    assert graph['nodes'][1]['parents']==['source-square']


def test_unresolved_agreement_is_not_success():
    row={'draws':{'original':[{'label':None}]*5,'dsg':[{'label':None,'dsg_score':None}]*5}}
    metric=case_metrics(row,'yes')
    assert metric['paired_agreement']==metric['paired_coverage']==0
    assert metric['resolved_pair_agreement'] is None and not metric['mode_match']
    assert metric['original_self_disagreement']==1


def test_interrupted_vqa_is_not_resampled(tmp_path):
    case=demo_case(tmp_path/'images');m=manifest(case);engine=Engine(interrupt=True);root=tmp_path/'run'
    with pytest.raises(KeyboardInterrupt):execute(root,m,lambda _:engine)
    result=execute(root,m,lambda _:engine)
    assert result['status']=='completed' and len(engine.requests)==23 # skipped dependent on interrupted root
    assert result['cases'][case.id]['draws']['dsg'][0]['label'] is None
    jobs=[json.loads(p.read_text()) for p in (root/'jobs').glob('*.json')]
    assert sum(j['outcome']=='interrupted' for j in jobs)==1
    before=len(engine.requests);assert execute(root,m,lambda _:engine)==result;assert len(engine.requests)==before
