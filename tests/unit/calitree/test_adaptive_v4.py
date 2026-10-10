"""V4 semantics, adaptive search, failure accounting and artifact compatibility."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, RoutedCalls, BudgetExhausted, CallFailure, ProviderStopped
from critical.core.decision.robust.models import restore_program as restore_v3, export_program as export_v3
from critical.core.decision.robust.v4_models import Activation, export_program, restore_program, validate
from critical.core.decision.robust.v4_construction import construct, apply_transaction, ACTION_SCHEMA, EvidenceCompiler
from critical.core.decision.robust.v4_runtime import EvidenceExecutor, EvidenceChecker
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.adaptive import create_adaptive_evidence_optimizer, select_confirmed
from critical.core.optimization.program.robust.adaptive import AdaptiveLeafOptimizer, ProposerPolicy
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.program.robust.metrics import RobustEvaluator, RobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf, validate_program_leaves
from run.calitree_adaptive_leaf import preflight, execute, release_transport_stop, PRIMARY, SOL


def specification():
    return {'supports':[
        {'requirement_id':'r','question':'Did red increase?','criteria':'Compare progress','binding':'square',
         'evidence_from':[],'required_evidence_from':[],'activation_source':0,'activation_states':[]},
        {'requirement_id':'r','question':'Is the square fully red?','criteria':'Inspect endpoint','binding':'square',
         'evidence_from':[1],'required_evidence_from':[],'activation_source':0,'activation_states':[]}],
        'fulfillment_criteria':'Complete if s2 passes even if s1 unknown; otherwise unknown.','fulfillment_required':[]}


def action(op,**values):
    a={k:[] if v['type']=='array' else '' for k,v in ACTION_SCHEMA['properties'].items()}
    a.update(operation=op,**values);return a


def tx(*actions):return {'version':'typed-evidence-v2','reason':'Preserve the original requirement while making independent evidence available.','actions':list(actions)}


def routing_repair():
    return tx(action('revise_support',target_id='s2',requirement_id='r',question='Is the square fully red?',
              criteria='Inspect endpoint',binding='square'),
              action('reorder_supports',support_order=['s2','s1']),
              action('configure_activation',target_id='s1',activation_check='s2',activation_states=['fail','unknown'],
              readout_criteria='Complete if s2 passes. Otherwise assess progress; unresolved necessary evidence stays unknown.'))


@pytest.fixture
def case(tmp_path):
    paths={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        p=tmp_path/f'{key}.png';Image.new('RGB',(8,8),color).save(p);paths[key]=str(p)
    return Case('case',example_program().instruction,paths,'group')


class Checker:
    identity={'model':'mock'}
    def __init__(self):self.seen=[]
    def check(self,p,n,o,e,d,**kw):
        self.seen.append((n.id,d,kw['slot']))
        if n.id=='fulfillment':status='complete' if next(v for v in d if v['check_id']=='s2')['status']=='pass' else 'unknown'
        else:status='unknown' if n.id=='s1' else 'pass'
        return {'status':status,'evidence':'Synthetic observation','confidence':.99,'completion_tokens':10}


def test_advisory_unknown_does_not_block_independent_endpoint_but_strict_gates_fail(case):
    p=construct(example_program(),specification());checker=Checker();e=EvidenceExecutor(checker)
    report=RobustEvaluator(e).evaluate(p,case,'yes',repeats=5,namespace='confirm')
    assert report['coverage']==report['agreement']==1 and len(checker.seen)==15
    assert report['traces'][0]['observations'][0]['event']=='valid_uncertainty'
    assert report['nodes']['s1']['consistency']==0
    assert not RobustPolicy().assess(report,{'accepted':True})['qualified']


def test_required_unknown_blocks_only_dependent_query_not_readout_scheduling(case):
    p=construct(example_program(),specification());p=replace(p,nodes=(p.nodes[0],replace(p.nodes[1],required_dependencies=('s1',)),p.nodes[2]))
    checker=Checker();t=EvidenceExecutor(checker).execute(p,case.evidence)
    assert [v[0] for v in checker.seen]==['s1','fulfillment']
    assert t['observations'][1]['event']=='required_dependency_block' and t['label'] is None


def test_required_readout_unknown_remains_unresolved(case):
    p=construct(example_program(),specification());p=replace(p,nodes=(*p.nodes[:-1],replace(p.nodes[-1],required_dependencies=('s1',))))
    t=EvidenceExecutor(Checker()).execute(p,case.evidence)
    assert t['observations'][-1]['event']=='required_dependency_block' and not t['resolved']


def test_routing_preserves_unknown_accounting_and_can_pass_strict_gates(case):
    seed=construct(example_program(),specification());child=apply_transaction(seed,routing_repair()).program
    r=RobustEvaluator(EvidenceExecutor(Checker())).evaluate(child,case,'yes',repeats=5,namespace='confirmation')
    assert RobustPolicy().assess(r,{'accepted':True})['qualified']
    assert r['nodes']['s1']['assessment']=='untested' and r['mean_checks']==2
    assert r['traces'][0]['observations'][1]['event']=='conditional_skip'
    assert seed.nodes[0].activation is None and child.requirements==seed.requirements


def test_negative_context_stays_valid(case):
    class Negative(Checker):
        def check(self,*args,**kw):
            row=super().check(*args,**kw)
            if args[1].id=='s1':row['status']='fail'
            return row
    p=construct(example_program(),specification());t=EvidenceExecutor(Negative()).execute(p,case.evidence)
    assert t['label']=='yes' and all(o['queried'] for o in t['observations'])


@pytest.mark.parametrize('applicability',['unknown','not_applicable'])
def test_applicability_does_not_fabricate_result(case,applicability):
    p=construct(example_program(),specification());p=replace(p,outcomes=(replace(p.outcomes[0],applicability=applicability),))
    t=EvidenceExecutor(Checker()).execute(p,case.evidence)
    assert not t['resolved'] and t['observations'][-1]['event']=='applicability_skip'


def test_immutable_removal_revises_surviving_context_and_preserves_provenance(case):
    p=construct(example_program(),specification())
    repair=tx(action('revise_support',target_id='s2',requirement_id='r',question=p.nodes[1].question,criteria=p.nodes[1].criteria,binding='square'),
              action('remove_support',target_id='s1',readout_criteria='Complete if s2 passes; otherwise unresolved.'))
    a=apply_transaction(p,repair)
    assert [n.id for n in a.program.nodes]==['s2','fulfillment'] and len(p.nodes)==3
    assert a.program.requirements==p.requirements and a.program.outcomes==p.outcomes
    assert a.details['provenance'][0]['source_phrase']==p.requirements[0].source_phrase
    assert EvidenceExecutor(Checker()).execute(a.program,case.evidence)['label']=='yes'


def test_insertion_replacement_and_compound_split():
    p=construct(example_program(),specification())
    insertion=action('insert_support',after='s2',before='fulfillment',new_check_id='s3',requirement_id='r',
        question='Does red reach the edges?',criteria='Inspect extent',binding='square edges',evidence_from=['s2'],readout_criteria='Use extent plus endpoint; missing required evidence unresolved.')
    c=apply_transaction(p,tx(insertion)).program
    assert [n.id for n in c.nodes]==['s1','s2','s3','fulfillment'] and c.nodes[-1].dependencies==('s1','s2','s3')
    replacement=action('replace_support',target_id='s2',requirement_id='r',question='Is red visible in the center?',criteria='Inspect center',binding='square center')
    assert apply_transaction(p,tx(replacement,insertion)).program.nodes[1].question=='Is red visible in the center?'
    with pytest.raises(ValueError):apply_transaction(c,tx({**insertion,'after':'s3','new_check_id':'s4'}))
    with pytest.raises(ValueError):apply_transaction(p,tx({**insertion,'new_check_id':'s1'}))
    with pytest.raises(ValueError):apply_transaction(p,tx({**insertion,'after':'s1','before':'fulfillment'}))


@pytest.mark.parametrize('repair',[
    tx(action('remove_support',target_id='s1',readout_criteria='complete s2')),
    tx(action('reorder_supports',support_order=['s2','s1'])),
    tx(action('configure_activation',target_id='s1',activation_check='s2',activation_states=['pass'],readout_criteria='complete if s2')),
    tx(action('revise_support',target_id='s2',requirement_id='invented',question='New question',criteria='New rule',binding='square')),
])
def test_atomic_invalid_edits_leave_parent_unchanged(repair):
    p=construct(example_program(),specification());before=p.ref
    with pytest.raises(ValueError):apply_transaction(p,repair)
    assert p.ref==before


def test_cache_slots_version_identity_and_legacy_hashes(case,tmp_path):
    old=export_v3(example_program());assert export_v3(restore_v3(old))==old
    p=construct(example_program(),specification());assert export_program(restore_program(export_program(p)))==export_program(p)
    checker=Checker();e=EvidenceExecutor(checker,checkpoint=CheckpointStore(tmp_path/'checks.jsonl'))
    e.execute(p,case.evidence,repeat='screen');e.execute(p,case.evidence,repeat='screen');assert len(checker.seen)==3
    e.execute(p,case.evidence,repeat='confirmation');assert len(checker.seen)==6
    e.execute(p,case.evidence,repeat='confirmation',final=True);assert len(checker.seen)==9
    child=apply_transaction(p,routing_repair()).program;e.execute(child,case.evidence,repeat='screen');assert len(checker.seen)==11


class Engine:
    def __init__(self,seen,*,sol=False,invalid=False,reject=False):self.seen,self.sol,self.invalid,self.reject=seen,sol,invalid,reject
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);props=kw['schema']['properties'];self.seen.append((payload,kw))
        if 'supports' in props:value=specification()
        elif 'accepted' in props:
            value={'accepted':not self.reject,'reason':'Faithful synthetic rule' if not self.reject else 'Unsupported interpretation',
                'source_clause':payload['instruction'] if self.reject else '', 'counterexample':'A required square edit is omitted' if self.reject else ''}
        elif 'findings' in props:value={'findings':[]}
        elif 'text' in props:value={'text':'Inspect endpoint independently; do not force the target label.'}
        elif 'transactions' in props:value={'transactions':[routing_repair()] if self.sol and payload['program']['nodes'][0]['id']=='s1' else []}
        else:
            n=payload['node']
            value={'status':'complete' if n['role']=='requested' else 'unknown' if n['id']=='s1' else 'pass',
                'evidence':'Synthetic image evidence','confidence':.99,'used_dependency_ids':n['dependencies']}
            if self.invalid:value['used_dependency_ids']=['wrong']
        return {'parsed':value,'model':'gpt-6.1-sol' if self.sol else 'gpt-6-luna','completionTokens':10,'promptTokens':20,'finishReason':'stop'}


def ledger(tmp_path,primary_seen,sol_seen):
    return DurableCalls(tmp_path,lambda _:Engine(primary_seen),identity=PRIMARY,max_calls=600,max_completion_tokens=768000,
        scope_limits={'search':200,'final':40},routes={'sol-proposer':{'identity':SOL,'engine_factory':lambda _:Engine(sol_seen,sol=True)}})


def test_adaptive_escalation_exact_round_and_saved_leaf_reload(case,tmp_path):
    a,b=[],[];calls=ledger(tmp_path,a,b);scope=CaseCalls(calls,case.id);seed=construct(example_program(),specification())
    opt=create_adaptive_evidence_optimizer(scope,example_program(),proposer_policy='luna_then_sol',sol_calls=RoutedCalls(scope,'sol-proposer'))
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'yes'},optimizer_factory=lambda _:opt,seeds={case.id:seed})
    saved=bundle['nodes']['leaf:'+case.id]['result'];events=saved['lineage'][-1]['events']
    assert [e['route'] for e in events]==['primary']*3+['sol-proposer']
    assert [e['stall_before'] for e in events]==[0,1,2,3] and saved['status']=='confirmed_local'
    assert len(b)==1 and events[-1]['improved'] and events[-1]['stall_after']==0
    loaded=json.loads(json.dumps(bundle));validate_program_leaves(loaded)
    t=judge_program_leaf(loaded,'leaf:'+case.id,case.evidence,opt.evaluator.executor,repeat='fresh/inference')
    assert t['program_ref']==saved['selected']['program_ref'] and t['label']=='yes'
    assert bundle['version']=='calitree-casewise-leaves-v4'
    jobs=[json.loads(p.read_text()) for p in (tmp_path/'jobs').glob('*.json')]
    for j in jobs:
        if j['stage'] in ('check_v4','audit_v4','compile_v4','visual_discovery'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check_v4' and j['payload']['node']['role']=='requested':assert j['media_identity']==[]
        if j.get('route'):assert j['stage']=='propose_v4'
    assert not any(j['slot'].startswith('confirm/round/') and j['payload']['node']['id']=='s1' for j in jobs)


def test_mismatched_or_unresolved_screen_never_gets_confirmation(case,tmp_path):
    a,b=[],[];scope=CaseCalls(ledger(tmp_path,a,b),case.id)
    opt=create_adaptive_evidence_optimizer(scope,example_program(),max_rounds=1)
    saved=opt.optimize(case,'no',seed=construct(example_program(),specification()))
    assert saved.selected==saved.seed and not b
    assert all('confirm/round/' not in j['slot'] for j in (json.loads(p.read_text()) for p in (tmp_path/'jobs').glob('*.json')))


def test_regression_guard_uses_comparable_confirmed_evidence():
    policy=RobustPolicy();baseline={'draws':5,'agreement':.4,'coverage':1,'requirement_consistency':1,'mean_checks':3,'mean_completion_tokens':30}
    # These reports intentionally cannot qualify: this tests conservative fallback ranking.
    for r in [baseline]:r.update(confidence_pass=False,nodes={})
    better={**baseline,'agreement':.8};regressed={**baseline,'agreement':1,'coverage':.8};cheap={**baseline,'agreement':.2,'mean_checks':1}
    reports={'seed':baseline,'better':better,'regression':regressed,'cheap':cheap}
    assert select_confirmed({},reports,{r:{'accepted':True} for r in reports},'seed',policy)=='better'


def test_audit_rejection_does_not_score_or_select(case,tmp_path):
    seen=[];calls=DurableCalls(tmp_path,lambda _:Engine(seen,reject=True),identity=PRIMARY,scope_limits={'search':109,'final':40})
    opt=create_adaptive_evidence_optimizer(CaseCalls(calls,case.id),example_program(),max_rounds=1)
    result=opt.optimize(case,'yes',seed=construct(example_program(),specification()))
    assert not any('screen' in v for v in result.candidates.values()) and result.status!='confirmed_local'


def test_invalid_acknowledgment_and_missing_confidence(case,tmp_path):
    seen=[];calls=DurableCalls(tmp_path,lambda _:Engine(seen,invalid=True),identity=PRIMARY)
    t=EvidenceExecutor(EvidenceChecker(CaseCalls(calls,case.id))).execute(construct(example_program(),specification()),case.evidence)
    assert not t['resolved'] and all(o['event']=='invalid_response' for o in t['observations'])
    class Missing(Checker):
        def check(self,*a,**kw):return {**super().check(*a,**kw),'confidence':None}
    r=RobustEvaluator(EvidenceExecutor(Missing())).evaluate(construct(example_program(),specification()),case,'yes',repeats=5,namespace='missing')
    assert r['coverage']==1 and not r['confidence_pass']


def manifest(case):
    return {'cases':[{'id':case.id,'instruction':case.instruction,'rubric':example_program().rubric,'evidence':case.evidence,
        'target':'yes','group':case.group,'original':export_v3(example_program())}],
        'arms':['luna_only','luna_then_sol'],'scope':'Synthetic test','primary_identity':PRIMARY,'routes':{'sol-proposer':SOL},
        'max_calls':600,'max_completion_tokens':768000,'reserve_calls':80,'reserve_tokens':81920,
        'scope_limits':{'search':109,'final':40},'policy':asdict(RobustPolicy()),'max_rounds':15,'max_sol_proposal_calls':144}


def test_whole_paired_workflow_reservations_final_isolation_and_zero_call_resume(case,tmp_path):
    a,b=[],[];out=tmp_path/'experiment';m=manifest(case);save_json(out/'manifest.json',m)
    first=execute(out,m,lambda _:Engine(a),lambda _:Engine(b,sol=True),progress=False)
    assert first['status']=='completed' and first['cases'][case.id]['luna_then_sol']['support_status']=='locally_robust'
    assert first['cases'][case.id]['luna_only']['support_status']!='locally_robust'
    jobs={p.stem:json.loads(p.read_text()) for p in (out/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in first['budget']['attempted_slots']];split=next(i for i,j in enumerate(ordered) if j['phase']=='final')
    assert all(j['phase']=='final' and j['stage']=='check_v4' for j in ordered[split:])
    assert len(list((out/'frozen').rglob('*.json')))==2
    freeze=(out/'selection_freeze.json').read_bytes()
    n=len(a)+len(b);second=execute(out,m,lambda _:Engine(a),lambda _:Engine(b,sol=True),progress=False)
    assert len(a)+len(b)==n and second['cases']==first['cases']
    assert (out/'selection_freeze.json').read_bytes()==freeze


def test_preflight_preserves_twelve_ids_hashes_and_frozen_configuration(tmp_path):
    m=preflight(tmp_path/'run');assert len(m['cases'])==len({c['group'] for c in m['cases']})==12
    assert {t:sum(c['target']==t for c in m['cases']) for t in ['yes','partial','no']}=={'yes':4,'partial':4,'no':4}
    assert m['reserve_calls']==960 and m['max_calls']==3600 and preflight(tmp_path/'run')==m
    m['stall_threshold']=4;save_json(tmp_path/'run/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'run')


def test_budget_exhaustion_retains_seed_and_final_reservation(case,tmp_path):
    a=[];calls=DurableCalls(tmp_path,lambda _:Engine(a),identity=PRIMARY,max_calls=3,max_completion_tokens=10000,
        reserve_calls=1,reserve_tokens=1024,scope_limits={'search':109,'final':40})
    opt=create_adaptive_evidence_optimizer(CaseCalls(calls,case.id),example_program())
    r=opt.optimize(case,'yes',seed=construct(example_program(),specification()))
    assert r.selected==r.seed and r.stop_reason.startswith('budget_exhausted') and calls.budget['calls']==2


def test_transport_stop_and_retained_failed_slot_are_durable(tmp_path):
    seen=[]
    class Fail:
        def generate(self,*a,**kw):seen.append(1);raise OSError('synthetic TLS failure')
    calls=DurableCalls(tmp_path,lambda _:Fail(),identity=PRIMARY)
    from critical.core.decision.compiler import object_schema,TEXT
    def invoke(i):return calls.call('test',{'i':i},object_schema({'v':TEXT}),template='test',slot=str(i),max_tokens=1024)
    for i in [0,1]:
        with pytest.raises(CallFailure):invoke(i)
    with pytest.raises(ProviderStopped):invoke(2)
    with pytest.raises(CallFailure):invoke(0)
    assert len(seen)==3 and calls.budget['completion_tokens_or_reserved']==3072


def synthetic_search(case,tmp_path,script,max_rounds=8):
    seed=construct(example_program(),specification())
    class Calls:
        directory=tmp_path
        budget={'cases':{}}
        case_id=case.id
    class Compiler:
        calls=Calls();original=example_program()
        def audit(self,p,**kw):return {'accepted':True,'reason':'Synthetic audit'}
    class Gradient:
        def feedback(self,*a,**kw):return {}
    class Diagnosis:
        def discover(self,*a,**kw):return {'findings':[],'failures':[]}
    class Proposer:
        def propose(self,p,c,target,feedback,*,slot,route):return script(p,int(slot.split('/')[1]),route)
    class CostChecker(Checker):
        def check(self,*a,**kw):
            row=super().check(*a,**kw);criteria=a[0].nodes[-1].criteria
            row['completion_tokens']=5 if criteria.endswith('cheap') else 20 if criteria.endswith('expensive') else 10
            return row
    opt=AdaptiveLeafOptimizer(Compiler(),Proposer(),RobustEvaluator(EvidenceExecutor(CostChecker())),Gradient(),Diagnosis(),
        proposer_policy=ProposerPolicy('luna_then_sol'),max_rounds=max_rounds)
    return opt.optimize(case,'yes',seed=seed)


def test_escalation_stall_resets_after_comparable_improvement(case,tmp_path):
    def script(p,r,route):
        if r==2:return [tx(action('revise_readout',target_id='fulfillment',criteria=p.nodes[-1].criteria+' cheap'))]
        return [routing_repair()] if route=='sol-proposer' else []
    result=synthetic_search(case,tmp_path,script)
    events=result.lineage[-1]['events']
    assert [e['route'] for e in events]==['primary']*6+['sol-proposer']
    assert events[2]['improved'] and events[2]['stall_after']==0
    assert result.status=='confirmed_local'


def test_transport_round_does_not_advance_stall_counter(case,tmp_path):
    def script(p,r,route):
        if r==0:raise CallFailure('Synthetic failed proposal')
        return [routing_repair()] if route=='sol-proposer' else []
    result=synthetic_search(case,tmp_path,script)
    events=result.lineage[-1]['events']
    assert not events[0]['completed'] and events[0]['stall_after']==0
    assert [e['route'] for e in events]==['primary']*4+['sol-proposer']


def test_rejected_proposal_recovery_and_one_intermediate_followup(case,tmp_path):
    def script(p,r,route):
        if r==0:return [tx(action('revise_readout',target_id='fulfillment',criteria=p.nodes[-1].criteria+' expensive'))]
        if r==2:return [{'invalid':'proposal'}]
        return [routing_repair()] if route=='sol-proposer' else []
    result=synthetic_search(case,tmp_path,script)
    events=result.lineage[-1]['events']
    assert events[1]['parent']!=events[0]['parent'] and events[2]['parent']==events[0]['parent']
    assert result.lineage[1]['error'] and result.status=='confirmed_local'


def test_interrupted_search_resume_keeps_attempted_slots_and_escalation(case,tmp_path):
    out=tmp_path/'experiment';m=manifest(case);a,b=[],[];save_json(out/'manifest.json',m)
    interrupted=[]
    class Interrupt(Engine):
        def generate(self,prompt,**kw):
            if 'transactions' in kw['schema']['properties'] and not interrupted:
                interrupted.append(True);raise KeyboardInterrupt('synthetic interruption')
            return super().generate(prompt,**kw)
    with pytest.raises(KeyboardInterrupt):execute(out,m,lambda _:Interrupt(a),lambda _:Engine(b,sol=True),progress=False)
    before=json.loads((out/'budget.json').read_text());failed={p.stem for p in (out/'jobs').glob('*.json') if json.loads(p.read_text())['outcome']=='interrupted'}
    resumed=execute(out,m,lambda _:Engine(a),lambda _:Engine(b,sol=True),progress=False)
    assert resumed['status']=='completed' and failed
    assert resumed['budget']['attempted_slots'][:len(before['attempted_slots'])]==before['attempted_slots']
    assert all(json.loads((out/'jobs'/f'{k}.json').read_text())['outcome']=='interrupted' for k in failed)
    logical=[(j['case_id'],j['stage'],j['slot']) for j in (json.loads(p.read_text()) for p in (out/'jobs').glob('*.json'))]
    assert len(logical)==len(set(logical))
    final=resumed['cases'][case.id]['luna_then_sol']
    assert final['support_status']=='locally_robust'


def test_transport_continuation_releases_only_latch_and_preserves_accounting(tmp_path):
    original={'calls':17,'completion_tokens_or_reserved':1000,'stopped':'Three consecutive transport failures',
              'consecutive_errors':3,'attempted_slots':['a','b'],'cases':{'case':{'search':17,'final':0}}}
    save_json(tmp_path/'budget.json',original);release_transport_stop(tmp_path)
    resumed=json.loads((tmp_path/'budget.json').read_text())
    for key in ('calls','completion_tokens_or_reserved','attempted_slots','cases'):assert resumed[key]==original[key]
    assert resumed['stopped'] is None and resumed['consecutive_errors']==0 and len(resumed['authorized_resumes'])==1
    with pytest.raises(ValueError):release_transport_stop(tmp_path)
    save_json(tmp_path/'budget.json',{**original,'stopped':'Provider rejected the request'})
    with pytest.raises(ValueError):release_transport_stop(tmp_path)


def test_independent_case_escalation_and_measurements(case,tmp_path):
    m=manifest(case);m['cases'].append({**m['cases'][0],'id':'independent-second-case','group':'second-group'})
    m.update(max_calls=900,max_completion_tokens=1152000,reserve_calls=160,reserve_tokens=163840)
    a,b=[],[];r=execute(tmp_path/'batch',m,lambda _:Engine(a),lambda _:Engine(b,sol=True),progress=False)
    assert r['status']=='completed'
    for c in m['cases']:
        events=r['cases'][c['id']]['luna_then_sol']['escalation_events']
        assert [e['route'] for e in events]==['primary']*3+['sol-proposer']
    assert len(b)==2
