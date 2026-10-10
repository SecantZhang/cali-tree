"""Typed actions, saved chalk regressions and bounded end-to-end replay."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

from PIL import Image
import pytest
from critical.checkpoint import CheckpointStore
from critical.core.decision.calls import DurableCalls, CaseCalls, BudgetExhausted
from critical.core.decision.artifacts import save_json
from critical.core.decision.robust.models import Node, GATES, export_program, restore_program, validate
from critical.core.decision.robust.errors import GraphValidationError
from critical.core.decision.robust.refinement import template, EvidenceRefinementChecker
from critical.core.decision.robust.construction import construct_ordered_program, TypedEvidenceCompiler
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.optimization.program.robust.typed import apply_typed_transaction, create_typed_evidence_optimizer, nested_nodes, PROTOCOL
from critical.core.optimization.program.robust.edits import apply_transaction
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.program.models import Case
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf
from run.calitree_typed_evidence import execute, preflight, ARMS, ROOT


def seed():
    p=example_program()
    a=Node('n1','support','','',(),(),'Is some red present?','pass red, fail none, unknown unclear','square')
    b=Node('n2','support','','n1',GATES,(),'Is the intended square identifiable?','pass target, fail absent, unknown unclear','square')
    c=replace(p.nodes[0],id='n3',parent='n2',active_on=GATES,dependencies=('n1','n2'),
        criteria='complete both features; partial known progress with incomplete edit; absent no progress; unknown insufficient')
    return replace(p,nodes=(a,b,c),checker_template=template('check'))


def action(operation,**kwargs):
    return {**{k:'' for k in ('after','before','new_check_id','target_id','requirement_id','question','criteria','binding','readout_criteria')},
            'evidence_from':[],'operation':operation,**kwargs}


def transaction(*actions):
    return {'version':PROTOCOL,'reason':'Investigate the requested extent without forcing a label','actions':list(actions)}


def insertion():
    return action('insert_support',after='n2',before='n3',new_check_id='n4',requirement_id='r',
        question='Is red conversion complete across the square?',criteria='pass full extent; fail incomplete; unknown unclear',
        binding='same square',evidence_from=['n2'],readout_criteria='complete full extent; partial known red with incomplete extent; absent no progress; unknown insufficient')


@pytest.fixture
def case(tmp_path):
    evidence={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        p=tmp_path/(key+'.png');Image.new('RGB',(8,8),color).save(p);evidence[key]=str(p)
    return Case('square',example_program().instruction,evidence)


def test_insert_owns_graph_provenance_and_expansion():
    p=seed();before=p.to_dict();applied=apply_typed_transaction(p,transaction(insertion()))
    child=applied.program
    assert [n.id for n in child.nodes]==['n1','n2','n4','n3']
    assert [n.parent for n in child.nodes]==['','n1','n2','n4']
    assert child.nodes[-1].dependencies==('n1','n2','n4') and child.nodes[2].dependencies==('n2',)
    assert p.to_dict()==before and child.requirements==p.requirements and child.outcomes==p.outcomes
    assert applied.details['provenance']==[{'node_id':'n4','requirement_id':'r','source_phrase':p.instruction}]
    assert apply_transaction(p,applied.details['expanded_transaction'])==child
    assert applied.details['parent_ref']==p.ref and applied.details['child_ref']==child.ref


@pytest.mark.parametrize('index',[0,2])
def test_both_archived_rejections_construct_valid_chain_without_mutating_artifacts(index):
    path=ROOT/'logs/exps/261008-nested-evidence-small-seeded-v1/frozen/decomposed-greedy/0.json'
    before=path.read_bytes();r=next(iter(json.loads(before)['nodes'].values()))['result']
    rows=[h for h in r['lineage'] if 'transaction' in h];row=rows[index]
    assert row['error'] and row.get('audit') is None
    raw=row['transaction'];new=raw['edits'][0]['nodes'][0];readout=raw['edits'][1]['nodes'][0]
    request=action('insert_support',after=new['parent'],before=readout['id'],new_check_id=new['id'],
        requirement_id=raw['evidence_mapping'][0]['requirement_id'],question=new['question'],criteria=new['criteria'],
        binding=new['binding'],evidence_from=new['dependencies'],readout_criteria=readout['criteria'])
    parent=restore_program(r['candidates'][row['parent']]);child=apply_typed_transaction(parent,transaction(request)).program
    assert [n.id for n in child.nodes]==['n1','n2','n4','n3'] and child.nodes[-1].parent=='n4'
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',['duplicate','edge','provenance','manual','forward','missing','overcap'])
def test_invalid_actions_are_atomic(fault):
    p=seed();a=insertion();before=p.to_dict()
    if fault=='duplicate':a['new_check_id']='n2'
    if fault=='edge':a['before']='n1'
    if fault=='provenance':a['requirement_id']='invented'
    if fault=='manual':a['parent']='n2'
    if fault=='forward':a['evidence_from']=['n3']
    if fault=='missing':a['evidence_from']=['missing']
    if fault=='overcap':p=apply_typed_transaction(p,transaction(a)).program;a['after']='n4';a['new_check_id']='n5';before=p.to_dict()
    with pytest.raises(ValueError) as caught:apply_typed_transaction(p,transaction(a))
    if fault=='missing':assert caught.value.code=='missing_dependency'
    assert p.to_dict()==before


def test_replace_split_remove_and_explicit_context_migration():
    p=seed();revision=action('replace_support',target_id='n2',requirement_id='r',question='Is the source target bound?',
        criteria='pass identifiable; fail missing; unknown unclear',binding='same source square',evidence_from=['n1'])
    c=apply_typed_transaction(p,transaction(revision,insertion())).program
    assert c.nodes[1].id=='n2' and c.nodes[1].dependencies==('n1',)
    removal=action('remove_support',target_id='n2',readout_criteria='Use remaining red and extent evidence; unknown insufficient')
    with pytest.raises(GraphValidationError,match='missing') as dangling:apply_typed_transaction(c,transaction(removal))
    assert dangling.value.code=='missing_dependency' and dangling.value.dependency_id=='n2'
    migrate=action('revise_support',target_id='n4',requirement_id='r',question=c.nodes[2].question,
        criteria=c.nodes[2].criteria,binding=c.nodes[2].binding,evidence_from=['n1'])
    reduced=apply_typed_transaction(c,transaction(removal,migrate)).program
    assert [n.id for n in reduced.nodes]==['n1','n4','n3'] and reduced.nodes[-1].dependencies==('n1','n4')
    with pytest.raises(ValueError):apply_typed_transaction(seed(),transaction(action('remove_support',target_id='n2',readout_criteria='unchanged')))


def specification():
    return {'supports':[{'requirement_id':'r','question':'Is some red present?','criteria':'pass red; fail none; unknown unclear',
        'binding':'square','evidence_from':[]},{'requirement_id':'r','question':'Is red across the entire square?',
        'criteria':'pass whole; fail partial coverage; unknown unclear','binding':'square','evidence_from':[1]}],
        'fulfillment_criteria':'complete full red; partial known progress; absent no red; unknown insufficient'}


def test_ordered_compiler_builds_roles_ids_and_dependencies():
    p,provenance=construct_ordered_program(example_program(),specification())
    assert [n.id for n in p.nodes]==['s1','s2','fulfillment']
    assert [n.parent for n in p.nodes]==['','s1','s2']
    assert p.nodes[-1].dependencies==('s1','s2') and p.nodes[1].dependencies==('s1',)
    assert all(n.outcome_id=='' for n in p.nodes[:-1]) and len(provenance)==2
    for fault in ['forward','manual','provenance']:
        spec=specification()
        if fault=='forward':spec['supports'][0]['evidence_from']=[2]
        if fault=='manual':spec['supports'][0]['parent']=''
        if fault=='provenance':spec['supports'][0]['requirement_id']='missing'
        with pytest.raises(ValueError):construct_ordered_program(example_program(),spec)


def test_structured_graph_diagnostics():
    p=seed();a,b,c=p.nodes
    sibling=Node('n4','support','','n2',GATES,(),'Extent?','pass/fail/unknown','square')
    with pytest.raises(GraphValidationError) as caught:validate(replace(p,nodes=(a,b,sibling,replace(c,dependencies=('n1','n2','n4')))))
    assert caught.value.to_dict()['relationship']=='sibling' and caught.value.dependency_id=='n4'
    with pytest.raises(GraphValidationError,match='missing'):validate(replace(p,nodes=(replace(a,parent='missing',active_on=GATES),b,c)))
    with pytest.raises(GraphValidationError) as cycle:validate(replace(p,nodes=(replace(a,parent='n2',active_on=GATES),b,c)))
    assert cycle.value.code=='cycle'
    d=replace(sibling,id='n5',parent='n4')
    with pytest.raises(GraphValidationError) as depth:validate(replace(p,nodes=(a,b,sibling,d,replace(c,parent='n5',dependencies=('n1','n2','n4','n5')))))
    assert depth.value.code=='depth_limit'


class Engine:
    def __init__(self,seen,*,unknown=False,reject=False,empty=False):self.seen,self.unknown,self.reject,self.empty=seen,unknown,reject,empty
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.seen.append((deepcopy(payload),kw))
        props=kw['schema']['properties']
        if 'supports' in props:value=specification()
        elif 'accepted' in props:value={'accepted':not self.reject and (len(payload['program']['nodes'])==4 or 'repaired' in str(payload['program'])),
                                      'reason':'Synthetic faithful extent contract'}
        elif 'findings' in props:value={'findings':[]}
        elif 'text' in props:value={'text':'Investigate full requested extent; never force an answer.'}
        elif 'transactions' in props:
            if self.empty or len(payload['program']['nodes'])==4:value={'transactions':[]}
            elif payload['profile']=='criterion-only':
                value={'transactions':[transaction(action('revise_support',target_id='n2',requirement_id='r',
                    question='Is the requested extent established?',criteria='repaired extent boundary',binding='square'))]}
            else:value={'transactions':[transaction(insertion())]}
        else:
            node=payload['node'];status=('unknown' if self.unknown else 'fail') if node['id']=='n4' or 'repaired' in node['criteria'] else 'pass'
            if node['role']=='requested':status='partial' if any(d['status']=='fail' for d in payload['dependencies']) else 'complete'
            value={'status':status,'evidence':'Synthetic observed evidence','confidence':.99,'used_dependency_ids':node['dependencies']}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'mock-returned','finishReason':'stop'}


def scoped(tmp_path,seen,**kw):
    return CaseCalls(DurableCalls(tmp_path,lambda _:Engine(seen,**kw),identity={'model':'mock'},
        max_calls=300,reserve_calls=80,max_completion_tokens=384000,reserve_tokens=81920,scope_limits={'search':109,'final':40}),'square')


def test_nested_workflow_fresh_slots_reload_label_isolation(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen);checkpoint=CheckpointStore(tmp_path/'observations')
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required',checkpoint=checkpoint)
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'partial'},optimizer_factory=lambda _:opt,seeds={case.id:seed()})
    r=bundle['nodes']['leaf:'+case.id]['result'];p=restore_program(r['selected'])
    assert r['status']=='confirmed_local' and nested_nodes(p,seed())==['n4']
    assert r['candidates'][p.ref]['confirmation']['draws']==5
    assert any(h.get('construction',{}).get('child_ref')==p.ref for h in r['lineage'])
    for payload,kw in seen:
        if 'transactions' not in kw['schema']['properties'] and 'text' not in kw['schema']['properties']:
            assert 'reference_label' not in payload and 'feedback' not in payload
        if 'status' in kw['schema']['properties'] and payload['node']['role']=='requested':assert kw['media_inputs']==[]
    n=len(seen);saved=json.loads(json.dumps(bundle));executor=RobustExecutor(EvidenceRefinementChecker(calls),checkpoint=checkpoint)
    trace=judge_program_leaf(saved,'leaf:'+case.id,case.evidence,executor,repeat='fresh-inference')
    assert trace['label']=='partial' and trace['observations'][2]['status']=='fail'
    assert trace['observations'][2]['dependencies'][0]['check_id']=='n2' and len(seen)==n+4
    replay=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required',checkpoint=CheckpointStore(checkpoint.path))
    again=replay.optimize(case,'partial',seed=seed());assert again.selected==r['selected'] and len(seen)==n+4


@pytest.mark.parametrize('fault',['empty','reject'])
def test_no_nested_qualification_from_criterion_or_seed(fault,case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen,**{fault:True})
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required')
    r=opt.optimize(case,'yes',seed=seed())
    assert r.status=='structural_failure' and r.selected==r.seed and not r.lineage[-1]['selection_eligible']


def test_unknown_nested_blocks_readout_and_changes_invalidate_cache(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen,unknown=True);p=apply_typed_transaction(seed(),transaction(insertion())).program
    checkpoint=CheckpointStore(tmp_path/'observations');executor=RobustExecutor(EvidenceRefinementChecker(calls),checkpoint=checkpoint)
    first=executor.execute(p,case.evidence,repeat='same');assert first['label'] is None and len(seen)==3
    assert not first['observations'][-1]['queried']
    changed=apply_typed_transaction(p,transaction(action('revise_support',target_id='n4',requirement_id='r',
        question=p.nodes[2].question,criteria='New extent criterion',binding='square',evidence_from=['n2']))).program
    executor.execute(changed,case.evidence,repeat='same');assert len(seen)==4  # unchanged durable support slots reused


def test_two_arm_runner_frozen_finals_and_zero_call_resume(case,tmp_path):
    from critical.core.optimization.program.robust.metrics import RobustPolicy
    manifest={'case':{'id':case.id,'instruction':case.instruction,'rubric':seed().rubric,'target':'partial','evidence':case.evidence,
                     'group':'synthetic','broad_seed':export_program(example_program())},'seed':export_program(seed()),'arms':list(ARMS),
        'scope':'Synthetic two-arm typed test','policy':asdict(RobustPolicy()),'random_seed':42,'model':'mock','provider':'mock',
        'temperature':0,'reasoning_effort':'none','max_calls':300,'max_completion_tokens':384000,'reserve_calls':80,'reserve_tokens':81920,
        'scope_limits':{'search':109,'final':40}}
    output=tmp_path/'run';seen=[];save_json(output/'manifest.json',manifest)
    result=execute(output,manifest,lambda _:Engine(seen));assert result['status']=='completed'
    assert all(r['support_status']=='locally_robust' for r in result['arms'].values())
    assert result['arms']['nested-required']['nested_checks']==['n4'] and result['arms']['criterion-only']['checks']==3
    jobs={p.stem:json.loads(p.read_text()) for p in (output/'jobs').glob('*.json')}
    ordered=[jobs[r] for r in result['budget']['attempted_slots']];first=next(i for i,j in enumerate(ordered) if j['phase']=='final')
    assert all(j['stage']=='check' and j['phase']=='final' for j in ordered[first:])
    assert sum(j['case_id'].startswith('prepare/') for j in jobs.values())==2
    n=len(seen);again=execute(output,manifest,lambda _:Engine(seen));assert len(seen)==n and again['arms']==result['arms']
    altered=deepcopy(manifest);altered['case']['target']='no'
    evaluated=execute(output,altered,lambda _:Engine(seen));assert len(seen)==n
    assert all(r['final']['selected']['agreement']==0 for r in evaluated['arms'].values())


def test_preflight_freezes_saved_seed_code_images_and_budgets(tmp_path):
    m=preflight(tmp_path/'run');assert m['max_calls']==300 and m['reserve_calls']==80 and len(m['seed']['program']['nodes'])==3
    assert preflight(tmp_path/'run')==m
    m['policy']['confidence']=.1;save_json(tmp_path/'run/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'run')


def test_structured_rejection_guides_next_round(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen)
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required')
    class Proposer:
        def propose(self,p,case,target,feedback,*,slot,limit):
            if 'round/0/' in slot:
                a=insertion();a['before']='n1';return [transaction(a)]
            if len(p.nodes)==4:return []
            assert any(d.get('validation',{}).get('code')=='edge_not_found' for d in feedback['rejected_diagnostics'])
            return [transaction(insertion())]
    opt.proposer=Proposer();r=opt.optimize(case,'partial',seed=seed())
    assert r.status=='confirmed_local' and r.lineage[0]['validation']['node_id']=='n1'


def test_qualifying_seed_protected_from_more_expensive_candidate(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen)
    p=replace(seed(),nodes=(seed().nodes[0],replace(seed().nodes[1],criteria='repaired extent boundary'),seed().nodes[2]))
    opt=create_typed_evidence_optimizer(calls,example_program(),max_rounds=2,stop_on_confirmation=False)
    r=opt.optimize(case,'partial',seed=p)
    assert r.status=='confirmed_local' and r.selected==export_program(p)
    assert any(len(c['program']['nodes'])==4 for c in r.candidates.values())


def test_no_search_budget_never_consumes_final_reservation(case,tmp_path):
    seen=[];ledger=DurableCalls(tmp_path/'calls',lambda _:Engine(seen),identity={'model':'mock'},
        max_calls=80,reserve_calls=80,max_completion_tokens=384000,reserve_tokens=81920)
    opt=create_typed_evidence_optimizer(CaseCalls(ledger,case.id),example_program(),profile='nested-required')
    r=opt.optimize(case,'partial',seed=seed())
    assert r.selected==r.seed and r.status=='structural_failure' and r.stop_reason.startswith('budget_exhausted')
    assert ledger.budget['calls']==0 and not seen


def test_invalid_ordered_probe_has_single_durable_attempt(case,tmp_path):
    seen=[]
    class Invalid(Engine):
        def generate(self,prompt,**kw):
            row=super().generate(prompt,**kw);row['parsed']['supports'][0]['evidence_from']=[2];return row
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:Invalid(seen),identity={'model':'mock'}),case.id)
    compiler=TypedEvidenceCompiler(calls,example_program())
    for _ in range(2):
        with pytest.raises(GraphValidationError):compiler.compile(case.instruction,example_program().rubric,slot='probe')
    assert calls.budget['calls']==1 and len(seen)==1


def test_invalid_compilation_remains_unresolved_without_fake_feedback(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen)
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required')
    def invalid(*args,**kwargs):raise ValueError('Invalid ordered support specifications')
    opt.compiler.compile=invalid
    r=opt.optimize(case,'partial')
    assert r.status=='unresolved' and r.seed is None and r.selected is None and not r.candidates
    assert not seen and calls.budget['calls']==0


def test_failed_insert_is_parent_of_next_round_and_repaired(case,tmp_path):
    seen=[]
    class ExtentEngine(Engine):
        def generate(self,prompt,**kw):
            row=super().generate(prompt,**kw)
            payload=seen[-1][0]
            if 'status' in kw['schema']['properties'] and payload['node']['id']=='n4' and 'repaired' not in payload['node']['criteria']:
                row['parsed']['status']='pass'  # valid added check still leaves the aggregate wrong
            return row
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:ExtentEngine(seen),identity={'model':'mock'},
        scope_limits={'search':109,'final':40}),case.id)
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required')
    parents=[]
    class Proposer:
        def propose(self,p,case,target,feedback,*,slot,limit):
            parents.append(p.ref)
            if len(p.nodes)==3:return [transaction(insertion())]
            assert feedback['report']['draws']==5 and feedback['report']['agreement']==0
            assert any(d.get('program_ref')==p.ref and 'target_mismatch' in d.get('confirmation_rejection',{}).get('reasons',[])
                       for d in feedback['rejected_diagnostics'])
            return [transaction(action('revise_support',target_id='n4',requirement_id='r',question=p.nodes[2].question,
                criteria='repaired extent boundary',binding=p.nodes[2].binding,evidence_from=['n2']))]
    opt.proposer=Proposer();r=opt.optimize(case,'partial',seed=seed())
    first=apply_typed_transaction(seed(),transaction(insertion())).program
    assert parents==[seed().ref,first.ref]  # does not fall back to the cheaper seed
    assert r.status=='confirmed_local' and r.stop_reason=='confirmation_qualified'
    schedule=r.lineage[-1]['search_schedule']
    assert len(schedule['round_batches'])==15 and schedule['rounds_completed']==2
    assert r.lineage[-1]['events'][2]['parent_reason']=='failed_confirmation_follow_up'
    assert r.candidates[r.selected['program_ref']]['confirmation']['agreement']==1


def test_fifteen_round_limit_does_not_stop_on_empty_proposals(case,tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen,empty=True)
    r=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required').optimize(case,'partial',seed=seed())
    schedule=r.lineage[-1]['search_schedule']
    assert schedule['rounds_started']==schedule['rounds_completed']==15
    assert r.stop_reason=='round_limit' and r.status=='structural_failure'
    assert r.lineage[-1]['selection_failure']=='no_eligible_nested_candidate'
    assert sum('transactions' in kw['schema']['properties'] for _,kw in seen)==15


def test_round_configuration_is_bounded_and_manifest_frozen(tmp_path):
    seen=[];calls=scoped(tmp_path/'calls',seen)
    for value in [0,16,True,1.5]:
        with pytest.raises(ValueError):create_typed_evidence_optimizer(calls,example_program(),max_rounds=value)
    m=preflight(tmp_path/'fifteen')
    assert m['max_rounds']==15 and m['round_batches']==[1]*15
    assert m['stop_on_confirmation'] and m['repair_failed_candidate'] and m['budget_may_limit_search']


def test_budget_stop_reports_incomplete_search_without_fifteen_claim(case,tmp_path):
    seen=[];ledger=DurableCalls(tmp_path/'calls',lambda _:Engine(seen,empty=True),identity={'model':'mock'},
        max_calls=8,reserve_calls=1,max_completion_tokens=384000,reserve_tokens=1024)
    opt=create_typed_evidence_optimizer(CaseCalls(ledger,case.id),example_program(),profile='nested-required')
    r=opt.optimize(case,'partial',seed=seed())
    assert r.stop_reason.startswith('budget_exhausted') and ledger.budget['calls']==7
    assert r.lineage[-1]['search_schedule']['rounds_completed']<15


def test_late_repair_can_succeed_in_fifteenth_round(case,tmp_path):
    seen=[]
    class ExtentEngine(Engine):
        def generate(self,prompt,**kw):
            row=super().generate(prompt,**kw);payload=seen[-1][0]
            if 'status' in kw['schema']['properties'] and payload['node']['id']=='n4' and 'repaired' not in payload['node']['criteria']:
                row['parsed']['status']='pass'
            return row
    calls=CaseCalls(DurableCalls(tmp_path/'calls',lambda _:ExtentEngine(seen),identity={'model':'mock'},
        scope_limits={'search':109,'final':40}),case.id)
    # Keep this test focused on scheduling; native backward/discovery are covered
    # separately. Checker/audit draws still use the real durable accounting layer.
    opt=create_typed_evidence_optimizer(calls,example_program(),profile='nested-required')
    class Gradient:
        def feedback(self,*args,**kw):return {'n4':['Investigate missed extent without forcing an answer']}
    class Discovery:
        def discover(self,*args,**kw):return {'findings':[]}
    class Proposer:
        def propose(self,p,case,target,feedback,*,slot,limit):
            if 'round/0/' in slot:return [transaction(insertion())]
            assert len(p.nodes)==4 and feedback['report']['agreement']==0
            if 'round/14/' not in slot:return []
            return [transaction(action('revise_support',target_id='n4',requirement_id='r',question=p.nodes[2].question,
                criteria='repaired extent boundary',binding='square',evidence_from=['n2']))]
    opt.gradient,opt.diagnosis,opt.proposer=Gradient(),Discovery(),Proposer()
    r=opt.optimize(case,'partial',seed=seed())
    assert r.status=='confirmed_local' and r.stop_reason=='confirmation_qualified'
    assert r.lineage[-1]['search_schedule']['rounds_completed']==15
    assert r.candidates[r.selected['program_ref']]['confirmation']['agreement']==1
