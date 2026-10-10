"""Degree of fulfillment is neither confidence nor a vote count; no API calls."""
from copy import deepcopy
from dataclasses import asdict,replace
from fractions import Fraction
import json

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls,CaseCalls
from critical.core.decision.fulfillment import (FulfillmentDecision,FulfillmentProgram,WeightRoot,
    FulfillmentCompiler,FulfillmentChecker,FulfillmentExecutor,validate,variant,apply_transaction,
    export_program,restore_program,template,FIELDS)
from critical.core.decision.counting_v6 import restore_program as restore_v6
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.demo import example_program
from critical.core.optimization.program.robust.fulfillment import create_fulfillment_leaf_optimizer,FulfillmentEvaluator
from critical.core.optimization.program.robust.metrics import NoAuditRobustPolicy
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf
from run.calitree_adaptive_leaf import preflight,execute,PRIMARY


def program():
    orig=example_program();quote=orig.requirements[0].source_phrase
    nodes=tuple(FulfillmentDecision(id=f'd{i}',requirement_id='r',question=f'Is the {part} region red?',
        criteria='Assess requested red coverage',binding=part,source_quote=quote,aspect=part,endpoint=f'The {part} region is red',
        necessity='The whole requested square includes this region',zero_when='No requested red in the region',
        half_when='Half the region is red',full_when='The region is red throughout',root_id=f'root.d{i}',
        weight_numerator=1,weight_denominator=2) for i,part in [(1,'upper'),(2,'lower')])
    roots=tuple(WeightRoot(n.root_id,'r',quote,n.endpoint,1,2) for n in nodes)
    return FulfillmentProgram(orig.instruction,orig.rubric,orig.requirements,orig.outcomes,nodes,template('check'),
        decomposition_reason='Independent upper and lower parts of a requested whole square',weight_roots=roots)


@pytest.fixture
def case(tmp_path):
    e={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        p=tmp_path/(key+'.png');Image.new('RGB',(8,8),color).save(p);e[key]=str(p)
    return Case('synthetic',example_program().instruction,e,'group')


class Checker:
    identity={'checker':'synthetic-fulfillment'}
    def __init__(self,values,confidence=.99):self.values,self.confidence=values,confidence;self.seen=[]
    def check(self,p,n,evidence,*,slot,final):
        f=self.values[n.id];self.seen.append((n.id,slot,final))
        status='unknown' if f is None else 'pass' if f>=.9 else 'fail' if f<=.1 else 'partial'
        return {'fulfillment_score':f,'binary_status':'unknown' if f is None else 'pass' if f==1 else 'fail',
                'status':status,'evidence':'Synthetic directly measured coverage','confidence':self.confidence,'completion_tokens':4}


@pytest.mark.parametrize('scores,label',[(0,'no'),(.1,'no'),(.100001,'partial'),(.5,'partial'),(.899999,'partial'),(.9,'yes'),(1,'yes')])
def test_exact_thresholds_and_degree_is_not_confidence(case,scores,label):
    e=FulfillmentExecutor(Checker({'d1':scores,'d2':scores},confidence=.99));t=e.execute(program(),case.evidence)
    assert t['label']==label and t['fulfillment']['score']==scores
    # Lowering epistemic confidence leaves completion unchanged, but fails the separate confidence gate.
    low=FulfillmentEvaluator(FulfillmentExecutor(Checker({'d1':scores,'d2':scores},confidence=.2)),NoAuditRobustPolicy()).evaluate(
        program(),case,label,repeats=5,namespace='low')
    assert low['agreement']==1 and low['confidence_pass'] is False


def test_user_chalk_example_and_same_observation_binary_counterfactual(case):
    p=program();t=FulfillmentExecutor(Checker({'d1':.9,'d2':.4})).execute(p,case.evidence)
    assert t['fulfillment']['score']==.65 and t['label']=='partial' and t['fulfillment']['binary_label']=='no'
    t2=FulfillmentExecutor(Checker({'d1':.9,'d2':.4})).execute(variant(p,'binary'),case.evidence)
    assert t2['label']=='no' and t2['fulfillment']['fulfillment_label']=='partial'


@pytest.mark.parametrize('known,expected,bounds',[(.5,'partial',(.25,.75)),(0,None,(0,.5)),(1,None,(.5,1))])
def test_unknown_ranges_never_become_zero(case,known,expected,bounds):
    t=FulfillmentExecutor(Checker({'d1':known,'d2':None})).execute(program(),case.evidence)
    assert t['label']==expected and (t['fulfillment']['lower'],t['fulfillment']['upper'])==bounds
    assert t['observations'][1]['status']=='unknown' and t['fulfillment']['score'] is None


def test_all_unknown_and_unknown_applicability_are_unresolved(case):
    p=program();t=FulfillmentExecutor(Checker({'d1':None,'d2':None})).execute(p,case.evidence)
    assert t['label'] is None and t['fulfillment']['lower']==0 and t['fulfillment']['upper']==1
    p=replace(p,outcomes=(replace(p.outcomes[0],applicability='unknown'),))
    t=FulfillmentExecutor(Checker({'d1':1,'d2':1})).execute(p,case.evidence)
    assert t['label'] is None and not any(o['queried'] for o in t['observations'])


def spec(n):return {k:asdict(n)[k] for k in ('id',)+FIELDS}
def tx(op,target,decisions,expected):
    return {'version':'typed-fulfillment-v1','reason':'Preserve the same requested extent with observable parts',
        'actions':[{'operation':op,'target_id':target,'decisions':decisions}],
        'predicted_scores':[{'decision_id':key,'fulfillment_score':value,'evidence_reason':'Synthetic measured region'} for key,value in expected.items()]}


def test_splitting_conserves_parent_mass_and_helper_cannot_inflate_score(case):
    p=program();a=replace(p.nodes[0],id='d1a',aspect='upper-left',question='Is the upper-left red?',endpoint='Upper-left is red')
    b=replace(p.nodes[0],id='d1b',aspect='upper-right',question='Is the upper-right red?',endpoint='Upper-right is red')
    child=apply_transaction(p,tx('split','d1',[spec(a),spec(b)],{'d1a':.5,'d1b':.5})).program
    assert [n.weight for n in child.nodes]==[Fraction(1,4),Fraction(1,4),Fraction(1,2)] and child.weight_roots==p.weight_roots
    assert FulfillmentExecutor(Checker({'d1a':.5,'d1b':.5,'d2':.5})).execute(child,case.evidence)['fulfillment']['score']==.5
    h=replace(p.nodes[0],id='h',aspect='context',question='Is the region visible?',endpoint='The region is visible')
    helper=apply_transaction(p,tx('add','',[spec(h)],{'h':1})).program
    assert helper.nodes[-1].weight==0 and helper.nodes[-1].role=='evidence'
    t=FulfillmentExecutor(Checker({'d1':.5,'d2':.5,'h':1})).execute(helper,case.evidence)
    assert t['fulfillment']['score']==.5
    removed=apply_transaction(helper,tx('remove','h',[],{'d1':.5})).program
    assert removed==p and len(p.nodes)==2


def test_no_weight_threshold_or_required_mass_manipulation():
    p=program()
    with pytest.raises(ValueError):apply_transaction(p,tx('remove','d1',[],{'d2':1}))
    with pytest.raises(ValueError):apply_transaction(p,tx('revise','d1',[{**spec(p.nodes[0]),'weight_numerator':99}],{'d1':1}))
    with pytest.raises(ValueError):replace(p,satisfied_threshold=.8).ref
    with pytest.raises(ValueError):replace(p,nodes=(replace(p.nodes[0],weight_numerator=3,weight_denominator=4),p.nodes[1])).ref
    with pytest.raises(ValueError):apply_transaction(p,tx('revise','d1',[{**spec(p.nodes[0]),'endpoint':'A weaker requested state'}],{'d1':1}))


def test_reload_exact_program_cache_and_legacy_dispatch(case,tmp_path):
    p=program();assert restore_program(export_program(p))==p
    with pytest.raises((ValueError,TypeError)):restore_v6(export_program(p))
    checker=Checker({'d1':.9,'d2':.4});e=FulfillmentExecutor(checker,checkpoint=CheckpointStore(tmp_path/'obs.jsonl'))
    a=e.execute(p,case.evidence,repeat='same');b=e.execute(restore_program(export_program(p)),case.evidence,repeat='same')
    assert a==b and len(checker.seen)==2
    e.execute(variant(p,'binary'),case.evidence,repeat='same');assert len(checker.seen)==4
    e.execute(p,case.evidence,repeat='final',final=True);assert len(checker.seen)==6


class Engine:
    def __init__(self,seen,fail=False,invalid=None):self.seen,self.fail,self.invalid=seen,fail,invalid
    def generate(self,prompt,**kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);self.seen.append(payload);fields=kw['schema']['properties']
        if 'decisions' in fields:
            p=program();value={'decisions':[{k:asdict(n)[k] for k in FIELDS} for n in p.nodes],'decomposition_reason':p.decomposition_reason}
        elif 'fulfillment_score' in fields:
            assert not any(k in payload for k in ('reference_label','feedback','weights','scoring_mode','thresholds'))
            assert not any(k.startswith('weight') or k=='root_id' for k in payload['condition'])
            if self.fail:self.fail=False;raise RuntimeError('Synthetic TLS error')
            value={'fulfillment_score':self.invalid if self.invalid is not None else .5,'confidence':.99,'evidence':'Half the requested extent is complete'}
        elif 'findings' in fields:value={'findings':[]}
        elif 'text' in fields:value={'text':'Refine grounded evidence without changing mass'}
        else:value={'transactions':[]}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'synthetic','finishReason':'stop'}


def test_durable_recovery_preserves_raw_missingness_and_no_false_negative(case,tmp_path):
    seen=[];engine=Engine(seen,fail=True);calls=DurableCalls(tmp_path,lambda cap:engine,identity=PRIMARY,
        max_calls=80,max_completion_tokens=81920,scope_limits={'search':60,'final':20})
    evaluator=FulfillmentEvaluator(FulfillmentExecutor(FulfillmentChecker(CaseCalls(calls,'scope')),
        checkpoint=CheckpointStore(tmp_path/'observations.jsonl')),NoAuditRobustPolicy(agreement=1))
    report=evaluator.evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    # Even raw aggregate is bounded partial; missing atomic confidence still fails its robustness gate.
    assert report['raw_measurements']['agreement']==1 and not report['raw_measurements']['confidence_pass']
    assert report['agreement']==1 and report['confidence_pass'] and calls.budget['calls']==11
    assert report['counterfactual_agreement']['binary']==0
    before=deepcopy(calls.budget);again=evaluator.evaluate(program(),case,'partial',repeats=5,namespace='confirm')
    assert again==report and calls.budget==before


@pytest.mark.parametrize('value',[-.1,1.1,True])
def test_invalid_numeric_fulfillment_is_unmeasured_not_clamped(case,tmp_path,value):
    calls=DurableCalls(tmp_path,lambda cap:Engine([],invalid=value),identity=PRIMARY)
    t=FulfillmentExecutor(FulfillmentChecker(CaseCalls(calls,'scope'))).execute(program(),case.evidence)
    assert t['label'] is None and all(o['event']=='invalid_response' for o in t['observations'])


def test_saved_leaf_and_label_isolation(case,tmp_path):
    seen=[];calls=DurableCalls(tmp_path,lambda cap:Engine(seen),identity=PRIMARY)
    opt=create_fulfillment_leaf_optimizer(CaseCalls(calls,case.id),example_program())
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'partial'},optimizer_factory=lambda _:opt)
    assert bundle['version']=='calitree-casewise-leaves-v7'
    t=judge_program_leaf(json.loads(json.dumps(bundle)),'leaf:'+case.id,case.evidence,opt.evaluator.executor,repeat='inference')
    assert t['label']=='partial' and t['fulfillment']['score']==.5
    jobs=[json.loads(f.read_text()) for f in (tmp_path/'jobs').glob('*.json')]
    assert not any('audit' in j['stage'] for j in jobs)
    assert all('reference_label' not in j['payload'] and 'feedback' not in j['payload'] for j in jobs if j['stage'] in ('compile_fulfillment','check_fulfillment'))


def test_paired_runner_seeds_share_roots_and_fresh_final_slots(case,tmp_path):
    original=example_program();m={'cases':[{'id':case.id,'instruction':case.instruction,'rubric':original.rubric,'evidence':case.evidence,
        'target':'partial','group':case.group,'original':{'program_ref':original.ref,'program':original.to_dict()}}],
        'arms':['binary','fulfillment'],'scope':'Synthetic paired aggregation comparison','scoring':'fulfillment','primary_identity':PRIMARY,
        'routes':{},'max_sol_proposal_calls':0,'max_calls':300,'max_completion_tokens':384000,'reserve_calls':84,'reserve_tokens':86016,
        'scope_limits':{'search':107,'final':42},'policy':{'repeats':5,'agreement':1,'consistency':.8,'confidence':.8,'minimum_eligible':3},'max_rounds':2}
    seen=[];out=tmp_path/'paired';save_json(out/'manifest.json',m)
    r=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert r['status']=='completed';assert r['cases'][case.id]['fulfillment']['final']['selected']['agreement']==1
    assert r['cases'][case.id]['binary']['final']['selected']['agreement']==0
    artifacts=[next(iter(json.loads((out/'frozen'/a/'0.json').read_text())['nodes'].values()))['result']['seed']['program'] for a in m['arms']]
    assert artifacts[0]['weight_roots']==artifacts[1]['weight_roots'] and artifacts[0]['nodes']==artifacts[1]['nodes']
    before=len(seen);again=execute(out,m,lambda cap:Engine(seen),lambda cap:Engine(seen),progress=False)
    assert before==len(seen) and r['cases']==again['cases'] and r['budget']==again['budget']


def test_frozen_preflight_modes_and_budgets(tmp_path):
    m=preflight(tmp_path/'run',scoring='fulfillment')
    assert m['arms']==['binary','fulfillment'] and m['routes']=={} and len(m['cases'])==12
    assert m['thresholds']=={'yes':.9,'no':.1} and m['reserve_calls']==1008
    assert preflight(tmp_path/'run',scoring='fulfillment')==m
    with pytest.raises(ValueError):preflight(tmp_path/'run',scoring='endpoints')
