"""Offline contracts for local structural optimization and durable execution."""
from dataclasses import replace
import json
import pytest

from critical.core.decision.models import Outcome, Check, Requirement, Observation
from critical.core.decision.validation import validate_program
from critical.core.decision.aggregation import aggregate
from critical.core.decision.artifacts import export_program, restore_program, program_ref
from critical.core.decision.executor import ProgramExecutor, ModelChecker
from critical.core.decision.calls import DurableCalls, CaseCalls, BudgetExhausted, CallFailure, ProviderStopped
from critical.core.decision.compiler import ProgramCompiler
from critical.core.optimization.program import CasewiseOptimizer, RepeatedEvaluator, Edit, Transaction
from critical.core.optimization.program.edits import apply_transaction
from critical.core.optimization.program.proposer import ModelEditProposer
from critical.core.optimization.program.demo import seed_program, DemoCompiler, DemoChecker, DemoProposer, demo_case, RUBRIC
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf, validate_program_leaves

@pytest.fixture
def case(tmp_path):
    return demo_case(tmp_path / 'images')

def two_outcomes():
    p = seed_program()
    return replace(p, outcomes=p.outcomes + (replace(p.outcomes[0], id='o2'),),
                   checks=p.checks + (replace(p.checks[0], id='c2', outcome_id='o2'),))

@pytest.mark.parametrize('states,label', [(('complete','complete'),'yes'), (('absent','absent'),'no'),
    (('partial','partial'),'partial'), (('complete','absent'),'partial'), (('absent','partial'),'partial'),
    (('complete','partial'),'partial'), (('unknown','complete'),None), (('unknown','absent'),None)])
def test_aggregation(states, label):
    rows = tuple(Observation('c'+str(i+1), s, 'evidence', str(i)) for i,s in enumerate(states))
    assert aggregate(two_outcomes(), rows)[0] == label

@pytest.mark.parametrize('app,label', [('applicable','yes'),('unknown',None),('not_applicable',None)])
def test_applicability(app, label):
    p = seed_program(); p = replace(p, outcomes=(replace(p.outcomes[0], applicability=app),))
    assert aggregate(p, (Observation('c1','complete','e','r'),))[0] == label

def support_program():
    p=seed_program(); support=replace(p.checks[0], id='support', role='support')
    return replace(p, checks=(replace(p.checks[0], dependencies=('support',)), support))

class CounterChecker:
    identity={'test':'counter'}
    def __init__(self, states=None): self.calls=[]; self.states=states or {}
    def check(self, program, check, outcome, evidence, dependencies, *, slot, final=False):
        self.calls.append((check.id, dependencies, slot))
        return {'status':self.states.get(check.id,'complete'),'evidence':'Observed evidence','completion_tokens':1}

def test_negative_support_is_evidence(case):
    checker=CounterChecker({'support':'absent','c1':'absent'}); executor=ProgramExecutor(checker)
    row=executor.execute(support_program(),case.evidence)
    assert row.label=='no'
    assert [c[0] for c in checker.calls]==['support','c1']
    assert checker.calls[-1][1][0]['status']=='absent'

def test_unknown_support_blocks(case):
    checker=CounterChecker({'support':'unknown'}); row=ProgramExecutor(checker).execute(support_program(),case.evidence)
    assert row.label is None and len(checker.calls)==1

def test_invalid_missing_duplicate():
    p=seed_program(); o=Observation('c1','complete','e','r',False)
    assert aggregate(p,[o])[0] is None
    assert aggregate(p,[])[0] is None
    assert aggregate(p,[o,o])[0] is None

def test_graph_validation():
    p=support_program()
    with pytest.raises(ValueError,match='Cyclic'):
        validate_program(replace(p,checks=(p.checks[0],replace(p.checks[1],dependencies=('support',)))))
    with pytest.raises(ValueError,match='Broken'):
        validate_program(replace(p,checks=(replace(p.checks[0],dependencies=('missing',)),p.checks[1])))
    with pytest.raises(ValueError,match='exactly one'):
        validate_program(replace(p,checks=p.checks+(replace(p.checks[0],id='duplicate'),)))

def test_compound_edits_and_immutability():
    p=seed_program(); before=p.to_dict()
    support=replace(p.checks[0],id='support',role='support')
    revised=replace(p.checks[0],question='Inspect intended square',dependencies=('support',))
    tx=Transaction((Edit('add',checks=(support,)),Edit('revise','c1',checks=(revised,)),
                    Edit('rebind','o1',outcomes=(replace(p.outcomes[0],target='central square'),))), 'Repair target and evidence')
    candidate,mapping=apply_transaction(p,tx)
    assert len(candidate.checks)==2 and candidate.outcomes[0].target=='central square'
    assert p.to_dict()==before and mapping==[{'before':'o1','after':['o1']}]
    assert Transaction.from_dict(json.loads(json.dumps(tx.to_dict())))==tx

def test_split_remove_and_required_coverage():
    p=seed_program(); os=tuple(replace(p.outcomes[0],id=f'o{i}') for i in (2,3))
    cs=tuple(replace(p.checks[0],id=f'c{i}',outcome_id=f'o{i}') for i in (2,3))
    split,mapping=apply_transaction(p,Transaction((Edit('split','o1',os,cs),),'Decompose requirement'))
    assert mapping==[{'before':'o1','after':['o2','o3']}]
    reduced,_=apply_transaction(split,Transaction((Edit('remove','o2'),),'Remove redundant outcome'))
    assert len(reduced.outcomes)==1
    with pytest.raises(ValueError): apply_transaction(p,Transaction((Edit('remove','o1'),),'Delete required edit'))
    with pytest.raises(ValueError): apply_transaction(p,Transaction((Edit('remove','c1'),),'Remove sole check'))
    with pytest.raises(ValueError): apply_transaction(p,Transaction((Edit('add',checks=cs*3),),'Oversized'))

def test_add_missing_requirement_and_applicability():
    p=seed_program(); new=Requirement('r2','square', 'square')
    o=Outcome('o2',('r2',),'square evidence','square')
    c=replace(p.checks[0],id='c2',outcome_id='o2')
    q,_=apply_transaction(p,Transaction((Edit('add',outcomes=(o,),checks=(c,)),),'New requirement',(new,)))
    assert len(q.requirements)==2
    q,_=apply_transaction(q,Transaction((Edit('applicability','o2',outcomes=(replace(o,applicability='unknown'),)),),'Uncertain scope'))
    assert q.outcomes[1].applicability=='unknown'
    with pytest.raises(ValueError):
        apply_transaction(p,Transaction((Edit('rebind','o1',outcomes=(replace(p.outcomes[0],requirement_ids=()),)),),'Drop provenance'))

def test_identity_cache_and_reload(case):
    p=support_program(); checker=CounterChecker(); executor=ProgramExecutor(checker)
    executor.execute(p,case.evidence); executor.execute(restore_program(export_program(p)),case.evidence)
    assert len(checker.calls)==2
    q=replace(p,checks=(p.checks[0],replace(p.checks[1],question='New supporting criterion')))
    assert program_ref(q)!=program_ref(p)
    executor.execute(q,case.evidence); assert len(checker.calls)==4
    executor.execute(q,case.evidence,repeat='fresh'); assert len(checker.calls)==6
    artifact=export_program(q); artifact['program']['outcomes'][0]['target']='different'
    with pytest.raises(ValueError,match='hash'): restore_program(artifact)
    artifact['program']['version']='decision-program-v1'
    with pytest.raises(ValueError,match='version'): restore_program(artifact)

def optimizer(proposer=None, checker=None, compiler=None, **kwargs):
    return CasewiseOptimizer(compiler or DemoCompiler(),proposer or DemoProposer(),
               RepeatedEvaluator(ProgramExecutor(checker or DemoChecker())),rubric=RUBRIC,**kwargs)

def test_synthetic_repair_and_leaf_reload(case):
    opt=optimizer(); bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'yes'},optimizer_factory=lambda _:opt)
    bundle=json.loads(json.dumps(bundle)); node=bundle['nodes']['leaf:'+case.id]
    assert node['result']['status']=='confirmed_local'
    assert node['result']['seed']['program_ref']!=node['program_ref']
    assert judge_program_leaf(bundle,node['id'],case.evidence,opt.evaluator.executor).label=='yes'
    assert node['fit_scope']==[case.id]
    with pytest.raises(ValueError): validate_program_leaves({**bundle,'version':'calitree-program-leaves-v1'})

class InvalidFirst(DemoProposer):
    def __init__(self): self.feedback=[]
    def propose(self,*args,**kwargs):
        self.feedback.append(args[3])
        if len(self.feedback)==1:
            return [Transaction((Edit('remove','o1'),),'Invalid deletion')]
        return super().propose(*args,**kwargs)

def test_invalid_proposal_does_not_end_search(case):
    proposer=InvalidFirst(); result=optimizer(proposer=proposer).optimize(case,'yes')
    assert result.status=='confirmed_local' and len(proposer.feedback)==2
    assert proposer.feedback[1]['diagnostics']

class NeutralThenRepair:
    def propose(self,p,case,label,feedback,*,slot,limit):
        if 'central' not in p.outcomes[0].target:
            return [Transaction((Edit('rebind','o1',outcomes=(replace(p.outcomes[0],target='central square'),)),),'Identify square')]
        return DemoProposer().propose(p,case,label,feedback,slot=slot,limit=limit)

def test_neutral_intermediate_and_seed_retention(case):
    result=optimizer(proposer=NeutralThenRepair()).optimize(case,'yes')
    assert result.status=='confirmed_local' and len(result.lineage)>=2
    assert result.seed['program_ref'] in result.candidates

def test_seed_success_and_regression_rejection(case):
    result=optimizer(checker=CounterChecker()).optimize(case,'yes')
    assert result.status=='confirmed_local' and not result.lineage and result.selected==result.seed
    # Contradictory feedback must not manufacture a fitting result.
    result=optimizer(checker=CounterChecker()).optimize(case,'no')
    assert result.status=='unmatched' and result.selected==result.seed

def test_audit_rejected_candidate_cannot_be_selected(case):
    class Auditor(DemoCompiler):
        def audit(self,p,*,slot): return {'accepted':'SOURCE comparison' not in p.checks[0].question,'reason':'Not faithful'}
    result=optimizer(compiler=Auditor()).optimize(case,'yes')
    assert result.selected==result.seed and result.status!='confirmed_local'

def test_compilation_failure_not_semantic_feedback(case):
    class Broken(DemoCompiler):
        def compile(self,*args,**kwargs): raise ValueError('Invalid binding')
    result=optimizer(compiler=Broken()).optimize(case,'yes')
    assert result.selected is None and not result.lineage and result.stop_reason.startswith('compilation_failed')

def test_budget_exhaustion_returns_seed(case):
    class Broke(DemoProposer):
        def propose(self,*args,**kwargs): raise BudgetExhausted('case limit')
    result=optimizer(proposer=Broke()).optimize(case,'yes')
    assert result.status=='budget_limited' and result.selected==result.seed

class FakeEngine:
    def __init__(self, behavior=None): self.requests=[]; self.behavior=behavior
    def generate(self,prompt,**kwargs):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]); self.requests.append((payload,kwargs))
        if self.behavior: return self.behavior(payload,kwargs)
        if 'check' in payload: parsed={'status':'complete','evidence':'Visible red square'}
        elif 'program' in payload and 'reference_label' not in payload: parsed={'accepted':True,'reason':'Faithful'}
        elif 'reference_label' in payload: parsed={'transactions':[]}
        else:
            p=seed_program(payload['instruction']); parsed={k:p.to_dict()[k] for k in ('requirements','outcomes','checks')}
        return {'parsed':parsed,'model':'gpt-6-luna','completionTokens':10,'promptTokens':30,'finishReason':'stop'}

def ledger(tmp_path,engine,**kwargs):
    return DurableCalls(tmp_path,lambda _:engine,identity={'model':'gpt-6-luna'},**kwargs)

def test_label_isolation_and_media(tmp_path,case):
    engine=FakeEngine(); calls=CaseCalls(ledger(tmp_path/'ledger',engine),case.id)
    compiler=ProgramCompiler(calls); p=compiler.compile(case.instruction,RUBRIC,slot='compile')
    compiler.audit(p,slot='audit'); executor=ProgramExecutor(ModelChecker(calls))
    executor.execute(p,{**case.evidence,'reference_label':'SECRET','metadata':'SECRET'})
    ModelEditProposer(calls).propose(p,case,'yes',{'report':'local'},slot='proposal',limit=2)
    for payload, kwargs in engine.requests[:3]:
        assert 'reference_label' not in payload and 'SECRET' not in json.dumps(payload)
    assert engine.requests[-1][0]['reference_label']=='yes'
    assert len(engine.requests[-1][1]['media_inputs'])==4

def test_confirmation_and_final_slots_fresh(tmp_path,case):
    engine=FakeEngine(); calls=CaseCalls(ledger(tmp_path/'ledger',engine),case.id)
    executor=ProgramExecutor(ModelChecker(calls)); evaluator=RepeatedEvaluator(executor)
    opt=CasewiseOptimizer(ProgramCompiler(calls),ModelEditProposer(calls),evaluator,rubric=RUBRIC)
    result=opt.optimize(case,'yes'); p=restore_program(result.selected)
    report=evaluator.evaluate(p,case,'yes',repeats=3,namespace='final',final=True)
    assert report['independent_cases']==1 and report['repeat_count']==3
    check_jobs=[json.loads(p.read_text()) for p in (calls.directory/'jobs').glob('*.json') if json.loads(p.read_text())['stage']=='check']
    assert len(check_jobs)==7 and len({j['slot'] for j in check_jobs})==7

def test_durable_reuse_and_per_case_budget(tmp_path):
    engine=FakeEngine(lambda p,k:{'parsed':{},'completionTokens':1})
    parent=ledger(tmp_path,engine); scoped=CaseCalls(parent,'one')
    for i in range(26): scoped.call('test',{}, {},template='',slot=str(i))
    with pytest.raises(BudgetExhausted): scoped.call('test',{}, {},template='',slot='27')
    scoped.call('test',{}, {},template='',slot='0')
    assert len(engine.requests)==26
    resumed=CaseCalls(ledger(tmp_path,engine),'one')
    resumed.call('test',{}, {},template='',slot='0'); assert len(engine.requests)==26
    for i in range(24): resumed.call('test',{}, {},template='',slot='f'+str(i),final=True)
    with pytest.raises(BudgetExhausted): resumed.call('test',{}, {},template='',slot='f25',final=True)
    CaseCalls(parent,'two').call('test',{}, {},template='',slot='0')

def test_reserve_survives_interleaved_finals(tmp_path):
    engine=FakeEngine(lambda p,k:{'parsed':{},'completionTokens':1})
    calls=ledger(tmp_path,engine,max_calls=4,max_completion_tokens=4096,reserve_calls=2,reserve_tokens=2048)
    calls.call('x',{}, {},template='',slot='s0',max_tokens=1024)
    calls.call('x',{}, {},template='',slot='f0',max_tokens=1024,final=True)
    calls.call('x',{}, {},template='',slot='s1',max_tokens=1024)
    with pytest.raises(BudgetExhausted): calls.call('x',{}, {},template='',slot='s2',max_tokens=1024)
    calls.call('x',{}, {},template='',slot='f1',max_tokens=1024,final=True)

def test_failure_and_interrupt_accounting(tmp_path):
    def fail(p,k): raise RuntimeError('connection timed out')
    engine=FakeEngine(fail); calls=ledger(tmp_path/'failure',engine)
    for i in range(2):
        with pytest.raises(CallFailure): calls.call('x',{}, {},template='',slot=str(i))
    with pytest.raises(CallFailure): calls.call('x',{}, {},template='',slot='0')
    assert len(engine.requests)==2
    with pytest.raises(ProviderStopped): calls.call('x',{}, {},template='',slot='2')
    assert calls.budget['calls']==3
    def interrupt(p,k): raise KeyboardInterrupt()
    engine=FakeEngine(interrupt); calls=ledger(tmp_path/'interrupt',engine)
    with pytest.raises(KeyboardInterrupt): calls.call('x',{}, {},template='')
    calls=ledger(tmp_path/'interrupt',engine)
    with pytest.raises(CallFailure): calls.call('x',{}, {},template='')
    assert calls.budget['calls']==1 and len(engine.requests)==1

def test_runner_round_trip_resume_and_independent_leaves(tmp_path,case):
    from run.calitree_program_optimization import execute_live
    engine=FakeEngine()
    rows=[{'id':str(i),'instruction':case.instruction,'evidence':case.evidence,'group':str(i),'target':'yes'} for i in range(2)]
    manifest={'model':'gpt-6-luna','temperature':0,'reasoning_effort':'none','cases':rows,'rubric':RUBRIC,
              'max_calls':600,'max_completion_tokens':768000,'reserve_calls':288,'reserve_tokens':294912,
              'rounds':2,'beam_width':2,'proposals_per_parent':2}
    first=execute_live(tmp_path/'run',manifest,lambda _:engine); count=len(engine.requests)
    second=execute_live(tmp_path/'run',manifest,lambda _:engine)
    assert first==second and len(engine.requests)==count
    assert all(r['support_status']=='locally_fitted' for r in first['cases'].values())
    bundle=json.loads((tmp_path/'run/leaves.json').read_text())
    assert len(bundle['nodes'])==2 and all(len(n['fit_scope'])==1 for n in bundle['nodes'].values())

def test_original_cohort_identity():
    from run.calitree_program_optimization import frozen_cases, ORIGINAL
    if not ORIGINAL.exists(): pytest.skip('Historical pilot unavailable')
    old=json.loads(ORIGINAL.read_text()); rows=frozen_cases()
    before={r['id']:r['image_hashes'] for p in old['partitions'].values() for r in p}
    assert {r['id']:r['image_hashes'] for r in rows}==before and len({r['group'] for r in rows})==12

def test_token_ceiling_and_provider_rejection(tmp_path):
    engine=FakeEngine(lambda p,k:{'parsed':{},'completionTokens':10})
    calls=ledger(tmp_path/'tokens',engine,max_completion_tokens=1024)
    with pytest.raises(BudgetExhausted): calls.call('x',{}, {},template='',max_tokens=2048)
    assert not engine.requests and calls.budget['calls']==0
    def reject(p,k): raise RuntimeError('HTTP 403 model permission rejected')
    engine=FakeEngine(reject); calls=ledger(tmp_path/'rejected',engine)
    with pytest.raises(ProviderStopped): calls.call('x',{}, {},template='')
    with pytest.raises(ProviderStopped): calls.call('x',{}, {},template='',slot='new')
    assert len(engine.requests)==1

def test_invalid_response_and_missing_job_reservation_never_retry(tmp_path):
    engine=FakeEngine(lambda p,k:{'parsed':None,'completionTokens':10})
    calls=ledger(tmp_path,engine)
    with pytest.raises(CallFailure): calls.call('x',{}, {},template='')
    with pytest.raises(CallFailure): ledger(tmp_path,engine).call('x',{}, {},template='')
    assert len(engine.requests)==1
    # Simulate a crash after the budget reservation but before job persistence.
    next((tmp_path/'jobs').glob('*.json')).unlink()
    with pytest.raises(CallFailure,match='reservation'): ledger(tmp_path,engine).call('x',{}, {},template='')
    assert len(engine.requests)==1

def test_binding_evidence_and_configuration_cache_invalidation(case):
    checker=CounterChecker(); executor=ProgramExecutor(checker); p=seed_program()
    executor.execute(p,case.evidence)
    q=replace(p,outcomes=(replace(p.outcomes[0],target='different square'),))
    executor.execute(q,case.evidence); assert len(checker.calls)==2
    checker.identity={'test':'different version'}
    executor.execute(q,case.evidence); assert len(checker.calls)==3
    from PIL import Image
    Image.new('RGB',(16,16),'green').save(case.evidence['edited_image'])
    executor.execute(q,case.evidence); assert len(checker.calls)==4
    executor.execute(replace(q,checker_template=q.checker_template+'\nClarify.'),case.evidence)
    assert len(checker.calls)==5

def test_local_leaf_rejects_different_evidence(case,tmp_path):
    opt=optimizer(); bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'yes'},optimizer_factory=lambda _:opt)
    from PIL import Image
    other=tmp_path/'other.png'; Image.new('RGB',(16,16),'yellow').save(other)
    with pytest.raises(ValueError,match='different case'):
        judge_program_leaf(bundle,'leaf:'+case.id,{**case.evidence,'edited_image':str(other)},opt.evaluator.executor)

def test_confirmed_regression_keeps_seed(case):
    class Variable(CounterChecker):
        def check(self,program,check,outcome,evidence,dependencies,*,slot,final=False):
            is_candidate='SOURCE comparison' in check.question
            status=('complete' if '/screen/' in slot or (not is_candidate and '/confirm/' in slot and slot.endswith('/0')) else 'absent')
            return {'status':status,'evidence':'Controlled regression','completion_tokens':1}
    result=optimizer(checker=Variable()).optimize(case,'yes')
    assert result.selected==result.seed and result.status=='unstable'
    assert any('confirmation' in c for c in result.candidates.values())
