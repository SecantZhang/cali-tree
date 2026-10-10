"""Grounded counting repairs and transport-only verification recovery, no API calls."""
from copy import deepcopy
from dataclasses import asdict,replace
import json

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls,CaseCalls
from critical.core.decision.counting import restore_program as restore_v5
from critical.core.decision.counting_v6 import (EndpointDecision,EndpointProgram,EndpointExecutor,EndpointChecker,
    EndpointCompiler,apply_transaction,validate,export_program,restore_program,template)
from critical.core.optimization.program.robust.counting_v6 import (EndpointEvaluator,diagnose,
    screen_diagnostics,create_endpoint_leaf_optimizer)
from critical.core.optimization.program.robust.metrics import NoAuditRobustPolicy
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.program.models import Case
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf
from run.calitree_adaptive_leaf import preflight,execute,PRIMARY,SOL


def program():
    original=example_program();quote=original.requirements[0].source_phrase
    nodes=tuple(EndpointDecision(f'd{i}','r',f'Is the {part} half red?',
        f'Pass if the {part} half is red; fail otherwise','Compare source and edited square',
        source_quote=quote,aspect=part,endpoint=f'The {part} half is red',
        necessity=f'The requested red square includes its {part} half') for i,part in [(1,'upper'),(2,'lower')])
    return EndpointProgram(original.instruction,original.rubric,original.requirements,original.outcomes,
        nodes,template('check'),decomposition_reason='Independent spatial extents of the requested red square')


@pytest.fixture
def case(tmp_path):
    evidence={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        path=tmp_path/(key+'.png');Image.new('RGB',(8,8),color).save(path);evidence[key]=str(path)
    return Case('synthetic',example_program().instruction,evidence,'group')


def tx(node):
    return {'version':'typed-counting-v2','reason':'Tighten the lower spatial extent with direct visual evidence',
        'actions':[{'operation':'revise','target_id':node.id,'decisions':[{k:v for k,v in asdict(node).items() if k!='role'}]}],
        'predicted_states':[{'decision_id':node.id,'status':'fail','evidence_reason':'The lower half remains blue'}]}


@pytest.mark.parametrize('field,value',[
    ('source_quote','invented instruction'),('aspect','upper'),('endpoint','Some meaningful progress happened'),
    ('question','Has any progress toward red occurred?'),('necessity','')])
def test_reject_explicit_protocol_violations(field,value):
    p=program();bad=replace(p,nodes=(p.nodes[0],replace(p.nodes[1],**{field:value})))
    with pytest.raises(ValueError):bad.ref


def test_immutable_grounded_edits_expected_impact_and_ledger():
    p=program();node=replace(p.nodes[1],criteria='Inspect only the lower half')
    applied=apply_transaction(p,tx(node));assert p.nodes[1].criteria!=node.criteria
    assert applied.program.requirements==p.requirements and applied.program.outcomes==p.outcomes
    assert applied.details['predicted_states'][0]['decision_id']=='d2'
    bad=tx(node);bad['predicted_states'][0]['decision_id']='invented'
    with pytest.raises(ValueError):apply_transaction(p,bad)
    bad=tx(node);bad['predicted_states']=[]
    with pytest.raises(ValueError):apply_transaction(p,bad)
    assert restore_program(export_program(p))==p
    with pytest.raises(ValueError):restore_v5(export_program(p))


class Engine:
    def __init__(self,seen,fail_slots=(),unknown=False,repair=False):
        self.seen,self.fail_slots,self.unknown,self.repair=seen,fail_slots,unknown,repair
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.seen.append((payload,kw))
        fields=kw['schema']['properties']
        if 'decisions' in fields:
            p=program();nodes=list(p.nodes)
            if self.repair:nodes[1]=replace(nodes[1],criteria='broad red evidence anywhere')
            value={'decisions':[{k:v for k,v in asdict(n).items() if k not in ('id','role')} for n in nodes],
                   'decomposition_reason':p.decomposition_reason}
        elif 'status' in fields:
            n=payload['decision'];index=sum('decision' in a for a,b in self.seen)
            if index in self.fail_slots:raise RuntimeError('Synthetic TLS connection failure')
            status='unknown' if self.unknown else 'pass' if n['id']=='d1' or n['criteria']=='broad red evidence anywhere' else 'fail'
            value={'status':status,'evidence':'Synthetic visible region','confidence':.99}
        elif 'findings' in fields:value={'findings':[]}
        elif 'text' in fields:value={'text':'Separate lower spatial extent from the upper one'}
        else:
            assert 'targeted_diagnosis' in payload['feedback']
            round_number=sum('targeted_diagnosis' in a.get('feedback',{}) for a,b in self.seen)
            node=program().nodes[1]
            if round_number==1:node=replace(node,question='Has meaningful progress occurred?',endpoint='Some progress')
            value={'transactions':[tx(node)] if self.repair and round_number<=2 else []}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'synthetic','finishReason':'stop'}


def make_evaluator(tmp_path,engine):
    calls=DurableCalls(tmp_path,lambda cap:engine,identity=PRIMARY,
        max_calls=100,max_completion_tokens=102400,scope_limits={'search':80,'final':20})
    checker=EndpointChecker(CaseCalls(calls,'scope'))
    return calls,EndpointEvaluator(EndpointExecutor(checker,checkpoint=CheckpointStore(tmp_path/'obs.jsonl')),NoAuditRobustPolicy())


def test_recover_only_failed_transport_check_preserve_others_cost_and_zero_call_resume(case,tmp_path):
    seen=[];calls,e=make_evaluator(tmp_path,Engine(seen,fail_slots=(2,)))
    report=e.evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    assert calls.budget['calls']==11 and report['agreement']==report['coverage']==1
    assert report['raw_measurements']['coverage']==.8 and report['raw_measurements']['agreement']==.8
    assert report['draws']==5 and report['mean_attempted_calls']==2.2
    raw=report['raw_measurements']['traces'][0]['observations']
    effective=report['traces'][0]['observations']
    assert effective[0]==raw[0] and len(effective[1]['attempts'])==2
    assert effective[1]['completion_tokens']==1034 and report['mean_completion_tokens']==224.8
    before=deepcopy(calls.budget);again=e.evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    assert again==report and calls.budget==before
    jobs=[json.loads(f.read_text()) for f in (tmp_path/'jobs').glob('*.json')]
    recovery=[j for j in jobs if 'transport_recovery' in j['slot']]
    assert len(recovery)==1 and recovery[0]['slot'].endswith('/d2')


def test_recovery_has_one_attempt_limit_and_never_selects_by_label(case,tmp_path):
    seen=[];calls,e=make_evaluator(tmp_path,Engine(seen,fail_slots=(2,4)))
    a=e.evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    b=e.evaluate(program(),case,'yes',repeats=5,namespace='confirm')
    assert calls.budget['calls']==11 and a['coverage']==.8
    assert a['transport_recovery']==b['transport_recovery'] and a['traces']==b['traces']
    assert not e.policy.assess(a)['qualified']


def test_valid_uncertainty_and_valid_wrong_answers_never_get_replaced(case,tmp_path):
    seen=[];calls,e=make_evaluator(tmp_path,Engine(seen,unknown=True))
    a=e.evaluate(program(),case,'partial',repeats=5,namespace='unknown')
    assert a['transport_recovery'] is None and calls.budget['calls']==10 and a['coverage']==0
    seen=[];calls,e=make_evaluator(tmp_path/'wrong',Engine(seen))
    b=e.evaluate(program(),case,'yes',repeats=5,namespace='wrong')
    assert b['agreement']==0 and b['transport_recovery'] is None and calls.budget['calls']==10


def test_schema_failure_is_not_transport_recoverable(case,tmp_path):
    class Invalid(Engine):
        def generate(self,prompt,**kw):
            row=super().generate(prompt,**kw)
            if 'decision' in json.loads(prompt.split('INPUT_JSON: ',1)[1]):row['parsed']['status']='malformed'
            return row
    calls,e=make_evaluator(tmp_path,Invalid([]))
    report=e.evaluate(program(),case,'partial',repeats=5,namespace='schema')
    assert calls.budget['calls']==10 and report['coverage']==0 and report['transport_recovery'] is None
    assert all(o['event']=='invalid_response' for t in report['traces'] for o in t['observations'])


def test_native_gradients_ignore_transport_failures(case,tmp_path,monkeypatch):
    from critical.core.optimization.program.robust.counting_v6 import EndpointTextGrad
    from critical.core.optimization.program.robust.proposer import NodeTextGrad
    calls,e=make_evaluator(tmp_path,Engine([],fail_slots=(2,4)))
    report=e.evaluate(program(),case,'partial',repeats=5,namespace='gradient')
    def check_filtered(self,p,c,target,r,*,slot):
        assert all(o['valid'] and o['event']!='transport_failure' for t in r['traces'] for o in t['observations'])
        assert all('attempts' not in o for t in r['traces'] for o in t['observations'])
        return {'filtered':True}
    monkeypatch.setattr(NodeTextGrad,'feedback',check_filtered)
    assert EndpointTextGrad(calls).feedback(program(),case,'partial',report,slot='native')=={'filtered':True}


def test_interrupted_attempt_is_preserved_without_recovery(case,tmp_path):
    calls,e=make_evaluator(tmp_path,Engine([]));p=program()
    first=e.evaluate(p,case,'partial',repeats=1,namespace='first')
    ref=first['traces'][0]['observations'][0]['execution_ref'];path=tmp_path/'jobs'/f'{ref}.json'
    job=json.loads(path.read_text());job['outcome']='interrupted';save_json(path,job)
    fresh=EndpointEvaluator(EndpointExecutor(EndpointChecker(CaseCalls(calls,'scope'))),NoAuditRobustPolicy())
    report=fresh.evaluate(p,case,'partial',repeats=1,namespace='first')
    assert calls.budget['calls']==2 and report['coverage']==0 and report['transport_recovery'] is None
    assert report['traces'][0]['observations'][0]['event']=='interrupted_attempt'


def test_partial_representation_limit_and_repair_impact_diagnostics(case,tmp_path):
    calls,e=make_evaluator(tmp_path,Engine([]));p=program();report=e.evaluate(p,case,'yes',repeats=1,namespace='screen')
    single=replace(p,nodes=(p.nodes[0],),decomposition_reason='Synthetic irreducible condition')
    r=e.evaluate(single,case,'partial',repeats=1,namespace='single');d=diagnose(single,r,'partial')
    assert 'partial_unrepresentable_with_one_binary_condition' in d['issues']
    assert 'all_pass_investigate_missing_required_aspect_or_permissive_criterion' in d['issues']
    impact=screen_diagnostics(tx(p.nodes[1]),report,'yes')['previous_candidate_outcomes']
    assert impact['predictions_matched']=={'d2':True} and impact['semantic_success'] is False


def test_rejected_progress_edit_recovers_seed_retained_and_exact_leaf_reload(case,tmp_path):
    seen=[];calls=DurableCalls(tmp_path,lambda cap:Engine(seen,repair=True),identity=PRIMARY,
        max_calls=150,max_completion_tokens=153600,scope_limits={'search':100,'final':50})
    opt=create_endpoint_leaf_optimizer(CaseCalls(calls,case.id),example_program())
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'partial'},optimizer_factory=lambda _:opt)
    saved=bundle['nodes']['leaf:'+case.id]['result'];history=saved['lineage'][-1]
    assert bundle['version']=='calitree-casewise-leaves-v6' and saved['status']=='confirmed_local'
    assert saved['seed']['program_ref']!=saved['selected']['program_ref'] and len(history['events'])==2
    assert 'progress' in history['diagnostics'][0]['error'] and history['seed_retained']==saved['seed']['program_ref']
    assert saved['seed']['program_ref'] not in [k for k,v in saved['candidates'].items() if v.get('confirmation')]
    assert saved['lineage'][1]['screen_diagnosis']['previous_candidate_outcomes']['predictions_matched']=={'d2':True}
    trace=judge_program_leaf(json.loads(json.dumps(bundle)),'leaf:'+case.id,case.evidence,opt.evaluator.executor)
    assert trace['label']=='partial' and trace['program_ref']==saved['selected']['program_ref']
    jobs=[json.loads(f.read_text()) for f in (tmp_path/'jobs').glob('*.json')]
    assert not any('audit' in j['stage'] for j in jobs)
    assert all('reference_label' not in j['payload'] and 'feedback' not in j['payload'] for j in jobs if j['stage'] in ('compile_counting','check_counting'))


def test_v6_preflight_reservation_and_frozen_configuration(tmp_path):
    m=preflight(tmp_path/'run',scoring='endpoints')
    assert m['version']=='counting-endpoints-twelve-v6' and m['reserve_calls']==24*42
    assert m['scope_limits']=={'search':107,'final':42} and m['transport_recovery_per_report']==1
    assert m['policy']['agreement']==1
    assert m['shared_preparation_calls_per_case']==1 and len(m['cases'])==12
    assert preflight(tmp_path/'run',scoring='endpoints')==m
    with pytest.raises(ValueError):preflight(tmp_path/'run',scoring='counting')


def test_paired_fresh_final_and_zero_call_runner_replay(case,tmp_path):
    original=example_program();m={'cases':[{'id':case.id,'instruction':case.instruction,'rubric':original.rubric,'evidence':case.evidence,
        'target':'partial','group':case.group,'original':{'program_ref':original.ref,'program':original.to_dict()}}],
        'arms':['luna_only','luna_then_sol'],'scope':'Synthetic endpoint run','scoring':'endpoints','primary_identity':PRIMARY,
        'routes':{'sol-proposer':SOL},'max_calls':300,'max_completion_tokens':384000,'reserve_calls':84,'reserve_tokens':86016,
        'scope_limits':{'search':107,'final':42},'policy':{'repeats':5,'agreement':.8,'consistency':.8,'confidence':.8,'minimum_eligible':3},'max_rounds':15}
    seen=[];out=tmp_path/'paired';save_json(out/'manifest.json',m)
    first=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert first['status']=='completed' and all(row['support_status']=='locally_robust' for row in first['cases'][case.id].values())
    before=len(seen);second=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert before==len(seen) and first['cases']==second['cases'] and first['budget']==second['budget']
    freeze=json.loads((out/'selection_freeze.json').read_text());assert len(freeze['hashes'])==2
