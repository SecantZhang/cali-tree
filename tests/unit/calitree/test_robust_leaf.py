from copy import deepcopy
from dataclasses import asdict, replace
from itertools import product
import json
import random
from pathlib import Path
import pytest
from critical.checkpoint import CheckpointStore
from critical.core.decision.models import Requirement, Outcome
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, CallFailure, BudgetExhausted, ProviderStopped
from critical.core.decision.robust.models import RobustProgram, Node, Inference, validate, export_program, restore_program
from critical.core.decision.robust.executor import RobustExecutor, RobustChecker
from critical.core.decision.robust.compiler import RobustCompiler
from critical.core.optimization.program.robust.edits import apply_transaction
from critical.core.optimization.program.robust.metrics import RobustEvaluator, RobustPolicy, summarize
from critical.core.optimization.program.robust.frontier import ParetoArchive
from critical.core.optimization.program.robust.proposer import NodeTextGrad, StructuralProposer
from critical.core.optimization.program.robust.search import RobustLeafOptimizer
from critical.core.optimization.program.robust.demo import example_program, revision, DemoCompiler, DemoChecker, DemoGradient, DemoProposer, RUBRIC, run_demo
from critical.core.optimization.program.models import Case
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf, validate_program_leaves

@pytest.fixture
def case(tmp_path):
    for name in ('source', 'edited'):
        (tmp_path/name).write_bytes(name.encode())
    return Case('case', 'Make the square red', {'source_image': str(tmp_path/'source'), 'edited_image': str(tmp_path/'edited')})

class Checker:
    identity = {'checker': 'mock'}
    def __init__(self, states=None, confidence=.9):
        self.states, self.confidence, self.calls = states or {}, confidence, []
    def check(self, program, node, outcome, evidence, dependencies, *, slot, final=False):
        self.calls.append((node.id, slot, final, deepcopy(dependencies)))
        state = self.states.get(node.id, 'complete' if node.role == 'requested' else 'pass')
        if isinstance(state, Exception):
            raise state
        if callable(state):
            state = state(slot)
        return {'status': state, 'evidence': 'Observed visual evidence', 'confidence': self.confidence, 'completion_tokens': 7}


def two_outcomes():
    base = example_program()
    return replace(base, outcomes=(base.outcomes[0], Outcome('o2', ('r',), 'Other part of square', 'square')),
        nodes=(base.nodes[0], replace(base.nodes[0], id='c2', outcome_id='o2')))

@pytest.mark.parametrize('a,b', list(product(('complete','partial','absent','unknown'), repeat=2)))
def test_aggregation_all_combinations(case,a,b):
    p=two_outcomes()
    result=RobustExecutor(Checker({'color':a,'c2':b})).execute(p,case.evidence)
    expected=None if 'unknown' in (a,b) else 'yes' if a==b=='complete' else 'no' if a==b=='absent' else 'partial'
    assert result['label']==expected
    assert len(result['requirements'])==1  # split outcomes do not multiply canonical requirements


def gated(active=('pass',), inference=()):
    p=example_program()
    support=Node('gate','support','', '',(),(), 'Is the target identifiable?', 'pass identifiable, fail absent, unknown ambiguous', 'the square', inference)
    return replace(p,nodes=(support,replace(p.nodes[0],parent='gate',active_on=active,dependencies=('gate',))))


def test_negative_support_dependency_and_routing(case):
    p=gated(('pass','fail'))
    c=Checker({'gate':'fail'})
    r=RobustExecutor(c).execute(p,case.evidence)
    assert r['label']=='yes' and [x[0] for x in c.calls]==['gate','color']
    assert c.calls[1][3][0]['status']=='fail'
    blocked=RobustExecutor(Checker({'gate':'fail'})).execute(gated(),case.evidence)
    assert blocked['label'] is None and not blocked['observations'][1]['queried']
    flat=RobustExecutor(Checker({'gate':'fail'})).execute(gated().view('flat'),case.evidence)
    assert flat['label']=='yes'


def test_unknown_parent_and_independent_sibling(case):
    p=gated(('pass','unknown'))
    p=replace(p,nodes=(*p.nodes,Node('independent','support','', '',(),(), 'Independent?', 'pass/fail/unknown', 'other target')))
    c=Checker({'gate':'unknown'})
    r=RobustExecutor(c).execute(p,case.evidence)
    assert r['label'] is None
    assert [x[0] for x in c.calls]==['gate','independent']


def test_inference_not_fabricated_query(case):
    p=gated(inference=(Inference('fail','o','absent','applicable','Target absent entails no color edit'),))
    r=RobustExecutor(Checker({'gate':'fail'})).execute(p,case.evidence)
    assert r['label']=='no' and r['outcomes']['o']['source']=='inferred:gate'
    assert sum(o['queried'] for o in r['observations'])==1

@pytest.mark.parametrize('app', ['not_applicable','unknown'])
def test_empty_or_unknown_applicability_unresolved(case,app):
    p=example_program();p=replace(p,outcomes=(replace(p.outcomes[0],applicability=app),))
    c=Checker();r=RobustExecutor(c).execute(p,case.evidence)
    assert r['label'] is None and not c.calls


def test_save_reload_cache_and_invalidation(case,tmp_path):
    p=gated();store=CheckpointStore(tmp_path/'observations.jsonl');c=Checker()
    first=RobustExecutor(c,checkpoint=store).execute(p,case.evidence,repeat='r')
    loaded=restore_program(json.loads(json.dumps(export_program(p))))
    assert RobustExecutor(c,checkpoint=CheckpointStore(store.path)).execute(loaded,case.evidence,repeat='r')==first
    assert len(c.calls)==2
    changed=replace(p,nodes=(replace(p.nodes[0],criteria='different support'),p.nodes[1]))
    RobustExecutor(c,checkpoint=store).execute(changed,case.evidence,repeat='r')
    assert len(c.calls)==4
    RobustExecutor(c,checkpoint=store).execute(p,case.evidence,repeat='fresh',final=True)
    assert len(c.calls)==6
    bad=export_program(p);bad['program']['nodes'][0]['question']='tampered'
    with pytest.raises(ValueError):restore_program(bad)


def test_invalid_observation_and_missing_confidence(case):
    p=example_program()
    r=RobustEvaluator(RobustExecutor(Checker(confidence=None))).evaluate(p,case,'yes',repeats=5,namespace='n')
    assert r['coverage']==1 and not RobustPolicy().assess(r,{'accepted':True})['qualified']
    bad=RobustExecutor(Checker({'color':'banana'})).execute(p,case.evidence)
    assert bad['label'] is None and not bad['observations'][0]['valid']


def test_conditional_denominators_and_failure_slots(case):
    p=gated();c=Checker({'gate':lambda slot:'pass' if '/0/' in slot or '/1/' in slot else 'fail'})
    r=RobustEvaluator(RobustExecutor(c)).evaluate(p,case,'yes',repeats=5,namespace='r')
    assert r['nodes']['color']['eligible']==2 and r['nodes']['color']['consistency']==1
    assert 'insufficient_activation:color' in RobustPolicy().assess(r,{'accepted':True})['reasons']
    c=Checker({'color':CallFailure('failure')})
    r=RobustEvaluator(RobustExecutor(c)).evaluate(example_program(),case,'yes',repeats=5,namespace='r')
    assert r['nodes']['color']['eligible']==5 and r['nodes']['color']['consistency']==0 and r['mean_completion_tokens']==1024


def test_four_of_five_and_all_confidence_gate(case):
    c=Checker({'color':lambda slot:'absent' if '/4/' in slot else 'complete'})
    r=RobustEvaluator(RobustExecutor(c)).evaluate(example_program(),case,'yes',repeats=5,namespace='r')
    assert RobustPolicy().assess(r,{'accepted':True})['qualified']
    r['confidence_pass']=False
    assert not RobustPolicy().assess(r,{'accepted':True})['qualified']


def test_immutable_compound_split_and_mappings():
    p=example_program();snapshot=p.to_dict();child=two_outcomes()
    tx={'reason':'split square regions','edits':[
        {'operator':'remove','remove_nodes':['color'],'nodes':[],'remove_outcomes':['o'],'outcomes':[],'node_order':[]},
        {'operator':'split','remove_nodes':[],'nodes':[asdict(n) for n in child.nodes],'remove_outcomes':[],
         'outcomes':[asdict(o) for o in child.outcomes],'node_order':[]}],
        'outcome_mapping':[{'old_outcome':'o','replacements':['o','o2']}]}
    assert apply_transaction(p,tx).outcomes==child.outcomes
    assert p.to_dict()==snapshot
    tx['outcome_mapping']=[]
    # o is identical, but o2 is an additional requested piece of r: semantic audit judges support.
    assert apply_transaction(p,tx).requirements==p.requirements
    tx['edits'][1]['outcomes'][0]['description']='changed'
    with pytest.raises(ValueError,match='mapping'):apply_transaction(p,tx)

@pytest.mark.parametrize('failure',['cycle','dependency','coverage','overcap','provenance'])
def test_structure_rejections(failure):
    p=example_program()
    if failure=='cycle':p=replace(p,nodes=(replace(p.nodes[0],parent='color',active_on=('complete',)),))
    if failure=='dependency':p=replace(p,nodes=(replace(p.nodes[0],dependencies=('missing',)),))
    if failure=='coverage':p=replace(p,requirements=(*p.requirements,Requirement('r2','red','red')))
    if failure=='overcap':p=replace(p,nodes=tuple(replace(p.nodes[0],id=str(i)) for i in range(5)))
    if failure=='provenance':p=replace(p,requirements=(Requirement('r','x','not in instruction'),))
    with pytest.raises(ValueError):validate(p)


def report(a=1,q=1,s=1,k=2,t=100,draws=1):
    return {'agreement':a,'coverage':q,'requirement_consistency':s,'mean_checks':k,'mean_completion_tokens':t,'draws':draws}


def test_pareto_dominance_tiers_pruning_and_sampling():
    f=ParetoArchive(1)
    assert f.update({'a':report(), 'b':report(a=0)})==['a']
    assert set(f.update({'c':report(a=.8,k=1)}))=={'a','c'}
    assert f.sample(random.Random(42),20)==f.sample(random.Random(42),20)
    assert set(f.sample(random.Random(42),100))=={'a','c'}
    with pytest.raises(ValueError):f.update({'wrong':report(draws=5)})
    f=ParetoArchive(1)
    f.update({str(i):report(a=i/10,k=1+i/10,t=100-i) for i in range(10)})
    assert len(f.reports)==6 and '0' in f.reports and '9' in f.reports


def optimizer(case, proposer=None,checker=None,compiler=None,mode='tree', selection='pareto'):
    return RobustLeafOptimizer(compiler or DemoCompiler(),proposer or DemoProposer(),RobustEvaluator(RobustExecutor(checker or DemoChecker())),
                              DemoGradient(),rubric=RUBRIC,mode=mode,selection=selection)


def test_repair_seed_retention_final_slots_and_reload(case,tmp_path):
    opt=optimizer(case)
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'yes'},optimizer_factory=lambda _:opt)
    bundle=json.loads(json.dumps(bundle));validate_program_leaves(bundle)
    node=bundle['nodes']['leaf:'+case.id];r=node['result']
    assert bundle['version']=='calitree-casewise-leaves-v3' and r['status']=='confirmed_local'
    assert r['seed']['program_ref'] in r['candidates'] and r['selected']!=r['seed']
    executed=judge_program_leaf(bundle,node['id'],case.evidence,RobustExecutor(DemoChecker()))
    assert executed['label']=='yes'
    with pytest.raises(ValueError):judge_program_leaf(bundle,node['id'],{**case.evidence,'source_image':case.evidence['edited_image']},RobustExecutor(DemoChecker()))


def test_invalid_first_round_and_neutral_intermediate(case):
    class Proposer:
        def propose(self,p,case,target,feedback,*,slot,limit):
            if 'round/0/' in slot:return [{'reason':'bad','edits':[],'outcome_mapping':[]}]
            assert feedback['rejected_diagnostics']
            return DemoProposer().propose(p,case,target,feedback,slot=slot,limit=limit)
    r=optimizer(case,Proposer()).optimize(case,'yes')
    assert r.status=='confirmed_local' and any('error' in v for v in r.lineage)
    class Neutral:
        def propose(self,p,case,target,feedback,*,slot,limit):
            return [revision(p,'neutral improvement' if 'round/0/' in slot else 'dominant red hue')]
    r=optimizer(case,Neutral()).optimize(case,'yes')
    assert r.status=='confirmed_local' and len(r.candidates)>=3


def test_regression_and_audit_rejection_keep_seed(case):
    seed=replace(example_program(),nodes=(replace(example_program().nodes[0],criteria='dominant red hue'),))
    class Worse:
        def propose(self,p,*args,**kwargs):return [revision(p,'worse'),revision(p,'force yes')]
    r=optimizer(case,Worse()).optimize(case,'yes',seed=seed)
    assert r.selected==export_program(seed)
    assert any(v.get('audit',{}).get('accepted') is False for v in r.candidates.values())


def test_invalid_compile_and_budget_do_not_fabricate_feedback(case):
    class Compiler(DemoCompiler):
        def compile(self,*a,**k):raise ValueError('malformed compile')
    r=optimizer(case,compiler=Compiler()).optimize(case,'yes')
    assert r.seed is None and r.status=='unresolved' and not r.candidates
    class Limited(Checker):
        def check(self,*a,**kw):raise BudgetExhausted('none left')
    r=optimizer(case,checker=Limited()).optimize(case,'yes')
    assert r.status=='budget_exhausted' and r.selected==r.seed

class FakeEngine:
    def __init__(self,fn):self.fn=fn
    def generate(self,prompt,**kw):return self.fn(prompt,kw)

def ledger(tmp_path,fn,**limits):
    return DurableCalls(tmp_path,lambda cap:FakeEngine(fn),identity={'model':'mock'},**limits)


def test_durable_failure_resume_and_scope_limits(tmp_path):
    seen=[]
    def fn(prompt,kw):seen.append(prompt);raise OSError('connection failed')
    calls=ledger(tmp_path,fn,scope_limits={'search':2,'final':1})
    for slot in ('a','b'):
        with pytest.raises(CallFailure):calls.call('check',{}, {},template='check',slot=slot,case_id='x',max_tokens=10)
    resumed=ledger(tmp_path,fn,scope_limits={'search':2,'final':1})
    with pytest.raises(CallFailure):resumed.call('check',{}, {},template='check',slot='a',case_id='x',max_tokens=10)
    with pytest.raises(BudgetExhausted):resumed.call('check',{}, {},template='check',slot='c',case_id='x',max_tokens=10)
    assert len(seen)==2
    with pytest.raises(ProviderStopped):resumed.call('check',{}, {},template='check',slot='d',case_id='y',max_tokens=10)
    assert resumed.budget['calls']==3 and resumed.budget['completion_tokens_or_reserved']==30


def test_budget_reservation_and_interrupted_slot(tmp_path):
    def fn(*args):return {'parsed':{'ok':True},'completionTokens':5}
    calls=ledger(tmp_path,fn,max_calls=3,max_completion_tokens=30,reserve_calls=2,reserve_tokens=20,scope_limits={'search':109,'final':40})
    calls.call('x',{}, {},template='x',slot='1',max_tokens=10,case_id='c')
    with pytest.raises(BudgetExhausted):calls.call('x',{}, {},template='x',slot='2',max_tokens=10,case_id='c')
    calls.call('x',{}, {},template='x',slot='2',max_tokens=10,case_id='c',final=True)
    job=next((tmp_path/'jobs').glob('*.json'));row=json.loads(job.read_text());row['outcome']='interrupted';save_json(job,row)
    with pytest.raises(CallFailure):calls.call('x',{}, {},template='x',slot=row['slot'],max_tokens=10,case_id='c',final=row['phase']=='final')


def test_native_backward_and_label_isolation(case,tmp_path):
    p=example_program(); captured=[]
    def fn(prompt,kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);captured.append(payload)
        props=kw['schema']['properties']
        if 'text' in props:value={'text':'Clarify red hue'}
        elif 'accepted' in props:value={'accepted':True,'reason':'Preserves instruction'}
        elif 'status' in props:value={'status':'complete','evidence':'Red square','confidence':.9}
        else:value={k:p.to_dict()[k] for k in ('requirements','outcomes','nodes')}
        return {'parsed':value,'completionTokens':10,'finishReason':'stop','model':'mock-returned'}
    calls=CaseCalls(ledger(tmp_path,fn),'local')
    compiler=RobustCompiler(calls)
    compiled=compiler.compile(p.instruction,p.rubric,slot='compile')
    compiler.audit(compiled,slot='audit')
    r=RobustEvaluator(RobustExecutor(RobustChecker(calls))).evaluate(compiled,case,'yes',repeats=1,namespace='screen')
    gradients=NodeTextGrad(calls).feedback(compiled,case,'yes',r,slot='gradient')
    assert gradients['color']==['Clarify red hue']
    assert all('reference_label' not in json.dumps(v) for v in captured[:3])
    assert captured[3]['reference_label']=='yes' and 'native_prompt' in captured[3]
    assert calls.budget['calls']==4


def test_arm_caches_are_independent(case,tmp_path):
    def fn(*args):return {'parsed':{'status':'complete','evidence':'red','confidence':.9},'completionTokens':2}
    calls=ledger(tmp_path,fn);cp=CheckpointStore(tmp_path/'obs')
    for arm in ('a','b'):
        RobustExecutor(RobustChecker(CaseCalls(calls,arm)),checkpoint=cp).execute(example_program(),case.evidence,repeat='same')
    assert calls.budget['calls']==2


def test_demo_is_standalone(tmp_path):
    assert run_demo(tmp_path)['status']=='locally_robust'


def test_full_runner_freezes_all_arms_and_zero_call_resume(case,tmp_path):
    from run.calitree_robust_leaf_optimization import execute
    p=example_program();seen=[]
    def fn(prompt,kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);seen.append(payload)
        props=kw['schema']['properties']
        if 'nodes' in props:value={k:p.to_dict()[k] for k in ('requirements','outcomes','nodes')}
        elif 'flat' in props:value={mode:{'accepted':True,'reason':'faithful'} for mode in ('flat','tree')}
        elif 'accepted' in props:value={'accepted':True,'reason':'faithful'}
        elif 'transactions' in props:value={'transactions':[]}
        elif 'text' in props:value={'text':'No faithful repair needed'}
        else:value={'status':'complete','evidence':'Red square','confidence':.99}
        return {'parsed':value,'completionTokens':10,'model':'mock-returned'}
    m={'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','provider':'openai','policy':asdict(RobustPolicy()),
       'random_seed':20261007,'max_calls':3600,'max_completion_tokens':4608000,'reserve_calls':160,'reserve_tokens':163840,
       'scope_limits':{'search':109,'final':40},'cases':[{'id':case.id,'instruction':case.instruction,'evidence':case.evidence,
       'target':'yes','group':'source','rubric':RUBRIC}]}
    result=execute(tmp_path/'run',m,lambda _:FakeEngine(fn));n=len(seen)
    assert result['status']=='completed' and len(result['cases'][case.id])==4
    assert all(r['support_status']=='locally_robust' for r in result['cases'][case.id].values())
    jobs=[json.loads(p.read_text()) for p in (tmp_path/'run/jobs').glob('*.json')]
    slots=json.loads((tmp_path/'run/budget.json').read_text())['attempted_slots']
    ordered={j['execution_ref']:j for j in jobs}
    phases=[ordered[s]['phase'] for s in slots]
    first=phases.index('final');assert all(p=='final' for p in phases[first:])
    # Same program in four arms and seed==selected still uses distinct fresh observations.
    assert sum(j['stage']=='check' and j['phase']=='final' for j in jobs)==40
    resumed=execute(tmp_path/'run',m,lambda _:FakeEngine(fn))
    assert len(seen)==n and resumed['cases']==result['cases']
    # Changing evaluation labels does not alter frozen candidates or send a new request.
    changed=deepcopy(m);changed['cases'][0]['target']='no'
    evaluated=execute(tmp_path/'run',changed,lambda _:FakeEngine(fn))
    assert len(seen)==n and all(r['final']['selected']['agreement']==0 for r in evaluated['cases'][case.id].values())
    assert all(r['acceptance']['reference_conflict_suspected'] for r in evaluated['cases'][case.id].values())


def test_preflight_selects_fixed_groups_and_detects_changed_protocol(tmp_path):
    from run.calitree_robust_leaf_optimization import preflight
    m=preflight(tmp_path/'preflight')
    assert len(m['cases'])==6 and len({r['group'] for r in m['cases']})==6
    assert m['max_calls']==3600 and m['reserve_calls']==960
    assert preflight(tmp_path/'preflight')==m
    m['policy']['confidence']=.5;save_json(tmp_path/'preflight/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'preflight')


def test_returned_failure_is_cached_across_process_replay(case,tmp_path):
    c=Checker({'color':CallFailure('transport')})
    cp=CheckpointStore(tmp_path/'obs')
    RobustExecutor(c,checkpoint=cp).execute(example_program(),case.evidence)
    RobustExecutor(c,checkpoint=CheckpointStore(tmp_path/'obs')).execute(example_program(),case.evidence)
    assert len(c.calls)==1


def test_restart_charges_prior_attempt_and_frozen_resume(tmp_path):
    from run.calitree_robust_leaf_optimization import preflight
    prior=tmp_path/'prior';old=preflight(prior)
    budget={'limits':{'max_calls':3600,'max_completion_tokens':4608000},'calls':3,
            'completion_tokens_or_reserved':6144,'stopped':'Three consecutive transport failures'}
    save_json(prior/'budget.json',budget);save_json(prior/'results.json',{'status':'stopped'})
    new=preflight(tmp_path/'restart',prior)
    assert new['max_calls']==3597 and new['max_completion_tokens']==4601856
    assert preflight(tmp_path/'restart')==new
    assert json.loads((prior/'manifest.json').read_text())==old
    budget['calls']=4;save_json(prior/'budget.json',budget)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'restart')


def test_restart_rejects_running_or_self_attempt(tmp_path):
    from run.calitree_robust_leaf_optimization import preflight
    prior=tmp_path/'prior';preflight(prior)
    save_json(prior/'budget.json',{'stopped':None});save_json(prior/'results.json',{'status':'running'})
    with pytest.raises(ValueError,match='stopped'):preflight(tmp_path/'restart',prior)
    with pytest.raises(ValueError,match='new directory'):preflight(prior,prior)
