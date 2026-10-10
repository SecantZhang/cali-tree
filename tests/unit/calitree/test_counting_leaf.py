"""Simple counting has no semantic auditor and no model-based final decision."""
from copy import deepcopy
from dataclasses import replace
import itertools
import json

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, CallFailure
from critical.core.decision.counting import CountingProgram, Decision, CountingExecutor, count_states, export_program, restore_program, apply_transaction, template
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.counting import create_counting_leaf_optimizer
from critical.core.optimization.program.robust.metrics import RobustEvaluator, NoAuditRobustPolicy
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf
from run.calitree_adaptive_leaf import execute, preflight, PRIMARY, SOL


def program():
    original=example_program()
    return CountingProgram(original.instruction,original.rubric,original.requirements,original.outcomes,
        (Decision('d1','r','Is the upper half red?','Pass red; fail otherwise; unknown unclear','upper square'),
         Decision('d2','r','Is the lower half red?','Pass red; fail otherwise; unknown unclear','lower square')),template('check'))


@pytest.fixture
def case(tmp_path):
    evidence={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        p=tmp_path/f'{key}.png';Image.new('RGB',(8,8),color).save(p);evidence[key]=str(p)
    return Case('synthetic',example_program().instruction,evidence,'group')


@pytest.mark.parametrize('states',list(itertools.product(('pass','fail','unknown'),repeat=3)))
def test_all_some_none_and_unknown(states):
    expected='unknown' if 'unknown' in states else 'complete' if all(s=='pass' for s in states) else 'absent' if all(s=='fail' for s in states) else 'partial'
    assert count_states(list(states))==expected


def test_empty_or_failed_set_never_becomes_no():
    assert count_states([])==count_states(['pass','invalid'])=='unknown'


class Checker:
    identity={'model':'synthetic'}
    def __init__(self,states):self.states=states;self.seen=[]
    def check(self,p,n,evidence,*,slot,final):
        self.seen.append((n.id,slot,final))
        return {'status':self.states[n.id],'evidence':'Synthetic visual observation','confidence':.99,'completion_tokens':3}


@pytest.mark.parametrize('states,label',[({'d1':'pass','d2':'pass'},'yes'),({'d1':'pass','d2':'fail'},'partial'),({'d1':'fail','d2':'fail'},'no'),({'d1':'unknown','d2':'pass'},None)])
def test_only_independent_models_run_and_count_is_authoritative(case,states,label):
    checker=Checker(states);executor=CountingExecutor(checker);trace=executor.execute(program(),case.evidence)
    assert trace['label']==label and len(checker.seen)==2
    assert trace['counting']['model_readout'] is False and trace['counting']['semantic_audit']=='disabled'
    assert all(o['queried'] for o in trace['observations'])
    assert [o['check_id'] for o in trace['observations']]==['d1','d2']


def test_negative_and_unknown_calls_do_not_block_other_checks(case):
    checker=Checker({'d1':'unknown','d2':'fail'});t=CountingExecutor(checker).execute(program(),case.evidence)
    assert len(checker.seen)==2 and t['counting']=={'passed':0,'failed':1,'unknown':1,'total':2,'semantic_audit':'disabled','model_readout':False}


@pytest.mark.parametrize('failure',[CallFailure('Synthetic transport failure'),ValueError('Synthetic invalid response')])
def test_failed_calls_remain_unknown_and_other_decisions_still_run(case,tmp_path,failure):
    from types import SimpleNamespace
    class Failed(Checker):
        calls=SimpleNamespace(directory=tmp_path)
        def check(self,p,n,evidence,*,slot,final):
            if n.id=='d1':raise failure
            return super().check(p,n,evidence,slot=slot,final=final)
    checker=Failed({'d2':'pass'});trace=CountingExecutor(checker).execute(program(),case.evidence)
    assert trace['label'] is None and trace['counting']['unknown']==1 and trace['counting']['passed']==1
    assert trace['observations'][0]['failure'] and trace['observations'][1]['queried']


def test_flat_format_never_reinterprets_legacy_helpers():
    row=example_program().to_dict()
    with pytest.raises((ValueError,TypeError,KeyError)):CountingProgram.from_dict(row)
    p=program();bad=replace(p,nodes=(replace(p.nodes[0],role='support'),p.nodes[1]))
    with pytest.raises(ValueError):bad.ref


def test_immutable_edits_and_required_coverage():
    p=program();node={'id':'d3','requirement_id':'r','question':'Are the corners red?','criteria':'Pass all corners red','binding':'square corners'}
    def tx(*actions):return {'version':'typed-counting-v1','reason':'Inspect required extent','actions':list(actions)}
    added=apply_transaction(p,tx({'operation':'add','target_id':'','decisions':[node]})).program
    assert len(added.nodes)==3 and len(p.nodes)==2 and added.requirements==p.requirements
    removed=apply_transaction(added,tx({'operation':'remove','target_id':'d3','decisions':[]})).program
    assert removed==p
    split=apply_transaction(p,tx({'operation':'split','target_id':'d2','decisions':[node,{**node,'id':'d4','question':'Is the bottom edge red?'}]})).program
    assert [n.id for n in split.nodes]==['d1','d3','d4']
    with pytest.raises(ValueError):apply_transaction(p,tx({'operation':'add','target_id':'','decisions':[{**node,'id':'d1'}]}))
    with pytest.raises(ValueError):apply_transaction(p,tx({'operation':'remove','target_id':'d1','decisions':[]},{'operation':'remove','target_id':'d2','decisions':[]}))
    with pytest.raises(ValueError):apply_transaction(p,tx({'operation':'add','target_id':'','decisions':[{**node,'requirement_id':'invented'}]}))


def test_artifact_parity_fresh_slots_and_cache(case,tmp_path):
    p=program();assert restore_program(export_program(p))==p
    checker=Checker({'d1':'pass','d2':'fail'});e=CountingExecutor(checker,checkpoint=CheckpointStore(tmp_path/'obs.jsonl'))
    e.execute(p,case.evidence,repeat='screen');e.execute(p,case.evidence,repeat='screen');assert len(checker.seen)==2
    e.execute(p,case.evidence,repeat='confirmation');e.execute(p,case.evidence,repeat='final',final=True);assert len(checker.seen)==6
    revised=replace(p,nodes=(replace(p.nodes[0],criteria='Revised red threshold'),p.nodes[1]));e.execute(revised,case.evidence,repeat='screen');assert len(checker.seen)==8


def test_no_semantic_approval_is_fabricated_and_empirical_gates_remain(case):
    policy=NoAuditRobustPolicy();r=RobustEvaluator(CountingExecutor(Checker({'d1':'pass','d2':'fail'})),policy).evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    a=policy.assess(r,{'status':'disabled','performed':False})
    assert a['qualified'] and a['semantic_audit']=='disabled' and 'semantic_audit' not in a['reasons']
    bad={**r,'confidence_pass':False};assert not policy.assess(bad)['qualified']


class Engine:
    def __init__(self,seen):self.seen=seen
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.seen.append((payload,kw));fields=kw['schema']['properties']
        assert 'accepted' not in fields and 'outcome' not in payload
        if 'decisions' in fields:
            value={'decisions':[{k:v for k,v in n.__dict__.items() if k not in ('id','role')} for n in program().nodes]}
        elif 'status' in fields:
            assert payload['decision']['role']=='decision'
            value={'status':'pass' if payload['decision']['id']=='d1' else 'fail','evidence':'Synthetic direct condition','confidence':.99}
        elif 'findings' in fields:value={'findings':[]}
        elif 'text' in fields:value={'text':'Only repair original required conditions'}
        else:value={'transactions':[]}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'synthetic','finishReason':'stop'}


def test_optimizer_never_calls_auditor_or_model_readout_and_saved_leaf_executes(case,tmp_path):
    seen=[];calls=DurableCalls(tmp_path,lambda cap:Engine(seen),identity=PRIMARY)
    opt=create_counting_leaf_optimizer(CaseCalls(calls,case.id),example_program())
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'partial'},optimizer_factory=lambda _:opt)
    assert bundle['version']=='calitree-casewise-leaves-v5'
    saved=bundle['nodes']['leaf:'+case.id]['result'];assert saved['status']=='confirmed_local'
    assert saved['candidates'][saved['selected']['program_ref']]['audit']=={'status':'disabled','performed':False,'reason':'Semantic auditing disabled by configuration'}
    restored=json.loads(json.dumps(bundle));trace=judge_program_leaf(restored,'leaf:'+case.id,case.evidence,opt.evaluator.executor,repeat='inference/fresh')
    assert trace['label']=='partial' and trace['program_ref']==saved['selected']['program_ref']
    jobs=[json.loads(f.read_text()) for f in (tmp_path/'jobs').glob('*.json')]
    assert not any('audit' in j['stage'] for j in jobs)
    assert all(j['payload']['decision']['role']=='decision' for j in jobs if j['stage']=='check_counting')
    assert all('reference_label' not in j['payload'] for j in jobs if j['stage'] in ('compile_counting','check_counting'))


def test_paired_runner_no_preparation_audit_final_model_or_api_replay(case,tmp_path):
    original=example_program();m={'cases':[{'id':case.id,'instruction':case.instruction,'rubric':original.rubric,'evidence':case.evidence,
        'target':'partial','group':case.group,'original':{'program_ref':original.ref,'program':original.to_dict()}}],
        'arms':['luna_only','luna_then_sol'],'scope':'Synthetic counting run','scoring':'counting','primary_identity':PRIMARY,
        'routes':{'sol-proposer':SOL},'max_calls':300,'max_completion_tokens':384000,'reserve_calls':80,'reserve_tokens':81920,
        'scope_limits':{'search':109,'final':40},'policy':{'repeats':5,'agreement':.8,'consistency':.8,'confidence':.8,'minimum_eligible':3},'max_rounds':15}
    seen=[];out=tmp_path/'paired';save_json(out/'manifest.json',m)
    first=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert first['status']=='completed' and all(row['support_status']=='locally_robust' for row in first['cases'][case.id].values())
    jobs=[json.loads(f.read_text()) for f in (out/'jobs').glob('*.json')]
    assert not any('audit' in j['stage'] for j in jobs)
    assert all(j['stage']=='check_counting' for j in jobs if j['phase']=='final')
    assert sum(j['case_id'].startswith('prepare/') for j in jobs)==1
    num=len(seen);second=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert num==len(seen) and first['cases']==second['cases'] and first['budget']==second['budget']


def test_counting_preflight_explicit_frozen_mode(tmp_path):
    m=preflight(tmp_path/'counting',scoring='counting')
    assert m['version']=='counting-leaf-twelve-v5' and m['semantic_audit'] is False and m['model_readout'] is False
    assert m['shared_preparation_calls_per_case']==1 and len(m['cases'])==12
    assert preflight(tmp_path/'counting',scoring='counting')==m
    with pytest.raises(ValueError):preflight(tmp_path/'counting',scoring='semantic')
