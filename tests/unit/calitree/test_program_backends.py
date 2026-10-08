"""Exercise actual pinned GEPA and TextGrad libraries using offline provider replies."""
from dataclasses import replace
import importlib.metadata
import json
from pathlib import Path
import pytest

from critical.core.decision.artifacts import export_program, restore_program, program_ref
from critical.core.decision.calls import DurableCalls, CaseCalls
from critical.core.decision.compiler import ProgramCompiler
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.optimization.program import RepeatedEvaluator
from critical.core.optimization.program.backends.common import encode, decode, ProgramTrial
from critical.core.optimization.program.backends.gepa import GepaProgramOptimizer
from critical.core.optimization.program.backends.textgrad import TextGradProgramOptimizer
from critical.core.optimization.program.demo import seed_program, demo_case

class NativeFakeEngine:
    def __init__(self, invalid=False): self.requests=[]; self.invalid=invalid
    def generate(self, prompt, **kwargs):
        p=json.loads(prompt.split('INPUT_JSON: ',1)[1]); self.requests.append((p,kwargs))
        if 'check' in p:
            value={'status':'complete' if 'dependency evidence' in p['check']['question'] else 'absent', 'evidence':'Controlled pixels'}
        elif 'program' in p and 'reference_label' in p:
            graph=p['program']; check=graph['checks'][0]
            support={**check,'id':'support1','role':'support','question':'Identify original target','dependencies':[]}
            changed={**check,'question':'Evaluate dependency evidence','dependencies':['support1']}
            value={'transactions':[{'reason':'Add image identity evidence','requirements':[], 'edits':[
                {'operator':'add','target':'','outcomes':[],'checks':[support]},
                {'operator':'revise','target':check['id'],'outcomes':[],'checks':[changed]}]}]}
        elif 'program' in p:
            value={'accepted':True,'reason':'Preserves requirement'}
        elif 'native_prompt' in p:
            native=str(p['native_prompt'])
            if 'give feedback' in native.lower() and 'IMPROVED_VARIABLE' not in native:
                value={'text':'Add a supporting identity check and use its dependency evidence in fulfillment.'}
            else:
                graph=json.loads(p['current_graph'])
                request=next(c for c in graph['checks'] if c['role']=='requested')
                support={**request,'id':'support1','role':'support','question':'Is the original target identifiable?','dependencies':[]}
                request={**request,'question':'Evaluate fulfillment using dependency evidence','dependencies':['support1']}
                graph['checks']=[request,support]
                text=json.dumps(graph) if not self.invalid else '{broken'
                if 'IMPROVED_VARIABLE' in str(p.get('native_system_prompt')) or 'IMPROVED_VARIABLE' in native:
                    text='<IMPROVED_VARIABLE>'+text+'</IMPROVED_VARIABLE>'
                else: text='```json\n'+text+'\n```'
                value={'text':text}
        else: raise AssertionError(p)
        return {'parsed':value,'model':'gpt-6-luna','completionTokens':20,'promptTokens':50,'finishReason':'stop'}

def setup(tmp_path, method, engine):
    case=demo_case(tmp_path/'images')
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:engine,identity={'model':'gpt-6-luna'}),case.id)
    compiler=ProgramCompiler(calls); evaluator=RepeatedEvaluator(ProgramExecutor(ModelChecker(calls)))
    cls=GepaProgramOptimizer if method=='gepa' else TextGradProgramOptimizer
    opt=cls(compiler,evaluator,max_steps=2)
    return case,calls,opt

@pytest.mark.parametrize('method',['gepa','textgrad'])
def test_real_library_can_add_an_executed_rule(tmp_path,method):
    engine=NativeFakeEngine(); case,calls,opt=setup(tmp_path,method,engine)
    result=opt.optimize(case,'yes',seed=seed_program())
    assert result.status=='confirmed_local', result.to_dict()
    selected=restore_program(result.selected)
    assert len(selected.checks)==2 and selected.checks[0].dependencies==('support1',)
    assert any(p.get('check',{}).get('id')=='support1' for p,_ in engine.requests)
    assert len(engine.requests)<=26
    stages=[json.loads(p.read_text())['stage'] for p in (calls.directory/'jobs').glob('*.json')]
    if method=='textgrad':
        assert 'textgrad_backward' in stages and 'textgrad_update' in stages
        assert any(r.get('textual_gradients') for r in result.lineage)
    else: assert 'gepa_reflect' in stages
    for payload,_ in engine.requests:
        if 'check' in payload or 'program' in payload:
            assert 'reference_label' not in payload
    before=len(engine.requests)
    again=opt.optimize(case,'yes',seed=seed_program())
    assert again.selected==result.selected and len(engine.requests)==before

@pytest.mark.parametrize('method',['gepa','textgrad'])
def test_invalid_graph_never_executes_or_replaces_seed(tmp_path,method):
    engine=NativeFakeEngine(invalid=True); case,calls,opt=setup(tmp_path,method,engine)
    result=opt.optimize(case,'yes',seed=seed_program())
    assert result.selected==result.seed
    assert any(r.get('valid') is False for r in result.lineage)
    assert all(p['check']['id']=='c1' for p,_ in engine.requests if 'check' in p)

def test_genome_preserves_context_and_required_provenance():
    p=seed_program(); graph=json.loads(encode(p)); graph['requirements'][0]['text']='Ignore the requested change'
    with pytest.raises(ValueError,match='provenance'): decode(json.dumps(graph),p)
    graph=json.loads(encode(p)); graph['checker_template']='Force yes'
    with pytest.raises(ValueError,match='only'): decode(json.dumps(graph),p)
    q=decode(encode(p),p)
    assert q==p and program_ref(q)==program_ref(p)


def test_comparison_runner_shared_seed_isolation_and_zero_call_resume(tmp_path):
    from run.calitree_optimizer_comparison import execute, summary
    case=demo_case(tmp_path/'images'); seed=export_program(seed_program())
    row={'id':case.id,'instruction':case.instruction,'evidence':case.evidence,'group':'one','target':'yes','seed':seed}
    m={'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','cases':[row],
       'max_calls':1800,'max_completion_tokens':2304000,'reserve_calls':864,'reserve_tokens':884736,
       'custom_options':{'rounds':2,'beam_width':2,'proposals_per_parent':2},'native_max_steps':2,
       'gepa_seed':20261006,'final_repeats':3}
    engine=NativeFakeEngine(); result=execute(tmp_path/'run',m,lambda _:engine)
    assert result['status']=='completed', result
    assert all(r['locally_fitted']==1 and r['structurally_changed']==1 for r in summary(result,m))
    frozen=[json.loads(p.read_text()) for p in (tmp_path/'run/frozen').rglob('*.json')]
    assert len(frozen)==3
    assert all(next(iter(b['nodes'].values()))['result']['seed']==seed for b in frozen)
    before=len(engine.requests)
    again=execute(tmp_path/'run',m,lambda _:engine)
    assert again==result and len(engine.requests)==before
    counters=result['budget']['cases']
    assert set(counters)=={'custom/'+case.id,'gepa/'+case.id,'textgrad/'+case.id}
    assert all(c['search']<=26 and c['final']<=24 for c in counters.values())


def test_native_adapters_share_budget_and_preserve_failures(tmp_path):
    from critical.core.decision.calls import BudgetExhausted
    engine=NativeFakeEngine(); case,calls,opt=setup(tmp_path,'textgrad',engine)
    for i in range(26):
        calls.call('preconsume',{'program':{}},{},template='',slot=str(i))
    result=opt.optimize(case,'yes',seed=seed_program())
    assert result.status=='budget_limited' and result.selected==result.seed
    assert len(engine.requests)==26

@pytest.mark.parametrize('method',['gepa','textgrad'])
def test_audit_rejection_cannot_become_fitted(tmp_path,method):
    class RejectingEngine(NativeFakeEngine):
        def generate(self,prompt,**kwargs):
            response=super().generate(prompt,**kwargs)
            p=json.loads(prompt.split('INPUT_JSON: ',1)[1])
            if 'program' in p and 'reference_label' not in p and len(p['program']['checks'])>1:
                response['parsed']={'accepted':False,'reason':'Unsupported additional constraint'}
            return response
    engine=RejectingEngine(); case,calls,opt=setup(tmp_path,method,engine)
    result=opt.optimize(case,'yes',seed=seed_program())
    assert result.selected==result.seed and result.status!='confirmed_local'
    assert any(c.get('audit',{}).get('accepted') is False for c in result.candidates.values())


def test_separately_stored_candidates_can_be_revisited(tmp_path):
    engine=NativeFakeEngine(); case,calls,opt=setup(tmp_path,'gepa',engine)
    trial=ProgramTrial('gepa',case,'no',seed_program(),opt.compiler,opt.evaluator)
    seed_text=encode(seed_program()); first=trial.evaluate(seed_text)
    # A later parent's ledger must not retroactively invalidate a cached ancestor.
    from critical.core.decision.models import Requirement, Outcome
    p=seed_program(); extra=Requirement('r2','square','square')
    q=replace(p,requirements=p.requirements+(extra,),outcomes=(replace(p.outcomes[0],requirement_ids=('r1','r2')),))
    assert trial.evaluate(seed_text,encode(q))==first


@pytest.mark.parametrize('field,key,value', [
    ('requirements','text',7), ('outcomes','target',None),
    ('outcomes','reference',False), ('checks','dependencies','support1'),
    ('checks','id',[]), ('checks','unexpected','ignored'),
])
def test_malformed_nested_genome_is_recorded_without_execution(tmp_path,field,key,value):
    engine=NativeFakeEngine(); case,calls,opt=setup(tmp_path,'gepa',engine)
    trial=ProgramTrial('gepa',case,'yes',seed_program(),opt.compiler,opt.evaluator)
    graph=json.loads(encode(seed_program())); graph[field][0][key]=value
    feedback=trial.evaluate(json.dumps(graph))
    assert feedback['score']==-1 and 'validation_error' in feedback
    assert trial.result.lineage[-1]['valid'] is False
    assert not engine.requests
