"""Mandatory visual evidence checks, isolated readout and frozen paired protocol."""
from copy import deepcopy
from dataclasses import asdict, replace
import json

import pytest
from PIL import Image

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import save_json
from critical.core.decision.calls import DurableCalls, CaseCalls, CallFailure
from critical.core.decision.robust.models import Node, GATES, export_program, restore_program
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.decision.robust.decomposition import (
    DecompositionCompiler, DecompositionChecker, BroadCompiler, validate_decomposition, validate_broad, template)
from critical.core.optimization.program.robust.decomposition import DecompositionProposer
from critical.core.optimization.program.robust import RobustLeafOptimizer, RobustEvaluator, RobustPolicy
from critical.core.optimization.program.robust.demo import example_program, DemoGradient, RUBRIC
from critical.core.optimization.program.models import Case
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf
from run.calitree_forced_decomposition import ARMS, SOURCE, preflight, execute


def decomposed(original=None):
    p = original or example_program()
    a = Node('location', 'support', '', '', (), (), 'Is the square identifiable?',
             'pass: identifiable; fail: visibly absent; unknown: ambiguous', 'square in both images')
    b = Node('red', 'support', '', 'location', GATES, (), 'Does the square have a dominant red hue?',
             'pass: red hue; fail: no red hue; unknown: ambiguous', 'edited square')
    c = replace(p.nodes[0], id='readout', parent='red', active_on=GATES, dependencies=('location', 'red'),
                criteria='Complete if square identifiable and red; absent if no red progress; partial if some red; unknown if necessary evidence unknown')
    return validate_decomposition(replace(p, nodes=(a, b, c), checker_template=template('check')), p)


@pytest.fixture
def case(tmp_path):
    evidence = {}
    for key, color in [('source_image', 'blue'), ('edited_image', 'red')]:
        path = tmp_path / (key+'.png'); Image.new('RGB', (8, 8), color).save(path)
        evidence[key] = str(path)
    return Case('square', example_program().instruction, evidence, 'distinct-source')


class Engine:
    def __init__(self, fn): self.fn = fn
    def generate(self, prompt, **kw): return self.fn(prompt, kw)


def fake_provider(p, seen, *, state='complete', bad_ack=False, compile_failure=False):
    def fn(prompt, kw):
        payload = json.loads(prompt.split('INPUT_JSON: ', 1)[1]); seen.append((deepcopy(payload), kw))
        props = kw['schema']['properties']
        if 'nodes' in props:
            if compile_failure: raise OSError('interrupted compile')
            value = {'nodes': p.to_dict()['nodes']}
        elif 'broad' in props:
            value = {key: {'accepted': True, 'reason': 'Faithful original requirement'} for key in props}
        elif 'accepted' in props: value = {'accepted': True, 'reason': 'Faithful original requirement'}
        elif 'transactions' in props: value = {'transactions': []}
        elif 'text' in props: value = {'text': 'Clarify observable evidence without weakening the requirement.'}
        else:
            node = payload['node']
            status = 'pass' if node['role']=='support' else state
            value = {'status': status, 'evidence': 'Observed red square', 'confidence': .99}
            if 'used_dependency_ids' in props:
                value['used_dependency_ids'] = [] if bad_ack else node['dependencies']
        return {'parsed': value, 'completionTokens': 10, 'promptTokens': 20, 'model': 'mock-returned'}
    return fn


def scoped(tmp_path, fn):
    return CaseCalls(DurableCalls(tmp_path, lambda _: Engine(fn), identity={'model':'mock'},
                                 scope_limits={'search':109, 'final':40}), 'test-case')


@pytest.mark.parametrize('fault', ['collapse','duplicate','whole-check','drop-dependency','dependent-support',
                                  'negative-route','rebind-outcome','criterion-template','ledger','overcap'])
def test_enforced_structure_and_frozen_original(fault):
    original = example_program(); p = decomposed(original); a,b,c = p.nodes
    if fault=='collapse': p = replace(p,nodes=(replace(c,parent='',active_on=(),dependencies=()),))
    if fault=='duplicate': p = replace(p,nodes=(a,replace(b,question=a.question),c))
    if fault=='whole-check': p = replace(p,nodes=(replace(a,question=c.question),b,c))
    if fault=='drop-dependency': p = replace(p,nodes=(a,b,replace(c,dependencies=('red',))))
    if fault=='dependent-support': p = replace(p,nodes=(a,replace(b,dependencies=('location',)),c))
    if fault=='negative-route': p = replace(p,nodes=(a,replace(b,active_on=('pass',)),c))
    if fault=='rebind-outcome': p = replace(p,outcomes=(replace(p.outcomes[0],target='another shape'),))
    if fault=='criterion-template': p = replace(p,checker_template='Rejudge the images')
    if fault=='ledger': p = replace(p,requirements=(replace(p.requirements[0],text='Do less'),))
    if fault=='overcap': p = replace(p,nodes=(*p.nodes,replace(a,id='four'),replace(a,id='five')))
    with pytest.raises(ValueError): validate_decomposition(p, original)


def test_broad_guard_and_compile_audit_label_isolation(case,tmp_path):
    original = example_program(); p = decomposed(original); seen=[]
    calls=scoped(tmp_path/'jobs', fake_provider(p,seen))
    compiler=DecompositionCompiler(calls,original)
    compiled=compiler.compile_from(slot='compile')
    assert compiled==p and compiled.requirements==original.requirements and compiled.outcomes==original.outcomes
    assert compiler.audit_pair(compiled,slot='pair')['decomposed']['accepted']
    assert compiler.audit(compiled,slot='single')['accepted']
    assert all('reference_label' not in payload and 'feedback' not in payload for payload,_ in seen)
    assert all(not kw['media_inputs'] for _,kw in seen)
    n=len(seen)
    with pytest.raises(ValueError): compiler.audit(original,slot='collapse')
    with pytest.raises(ValueError): BroadCompiler(calls,original).audit(p,slot='expanded')
    assert len(seen)==n and validate_broad(original,original)==original
    DecompositionProposer(calls).propose(p,case,'yes',{'textual_gradients':{}},slot='proposal')
    assert seen[-1][0]['reference_label']=='yes' and sum(m['type']=='image' for m in seen[-1][1]['media_inputs'])==2


def test_negative_evidence_independence_unknown_and_readout_images(case,tmp_path):
    p=decomposed(); seen=[]; mode={'first':'fail'}
    base=fake_provider(p,seen)
    def fn(prompt,kw):
        value=base(prompt,kw); node=seen[-1][0].get('node',{})
        if node.get('id')=='location': value['parsed']['status']=mode['first']
        return value
    checker=DecompositionChecker(scoped(tmp_path/'calls',fn)); executor=RobustExecutor(checker)
    trace=executor.execute(p,case.evidence,repeat='negative')
    assert trace['label']=='yes'  # synthetic readout may use negative evidence; not automatically unresolved
    assert [x['check_id'] for x in trace['observations']]==['location','red','readout']
    assert seen[-1][0]['dependencies'][0]['status']=='fail'
    assert [sum(m['type']=='image' for m in kw['media_inputs']) for _,kw in seen]==[2,2,0]
    assert all('reference_label' not in payload and 'feedback' not in payload for payload,_ in seen)
    mode['first']='unknown'; seen.clear()
    trace=executor.execute(p,case.evidence,repeat='unknown')
    assert trace['label'] is None and len(seen)==2
    assert all(o['queried'] for o in trace['observations'][:2]) and not trace['observations'][-1]['queried']


def test_acknowledgment_failure_keeps_actual_cost_and_replay(case,tmp_path):
    p=decomposed();seen=[];calls=scoped(tmp_path/'calls',fake_provider(p,seen,bad_ack=True))
    cp=CheckpointStore(tmp_path/'observations.jsonl')
    trace=RobustExecutor(DecompositionChecker(calls),checkpoint=cp).execute(p,case.evidence,repeat='one')
    last=trace['observations'][-1]
    assert trace['label'] is None and last['failure']=='ValueError' and last['completion_tokens']==10
    jobs=[json.loads(f.read_text()) for f in (calls.directory/'jobs').glob('*.json')]
    assert sum('observation_validation_error' in j for j in jobs)==1
    assert RobustExecutor(DecompositionChecker(calls),checkpoint=CheckpointStore(cp.path)).execute(
        restore_program(export_program(p)),case.evidence,repeat='one')==trace
    assert len(seen)==3
    RobustExecutor(DecompositionChecker(calls),checkpoint=cp).execute(p,case.evidence,repeat='fresh',final=True)
    assert len(seen)==6


def test_valid_saved_execution_and_changed_component_invalidates_cache(case,tmp_path):
    p=decomposed();seen=[];calls=scoped(tmp_path/'calls',fake_provider(p,seen))
    store=CheckpointStore(tmp_path/'obs');executor=RobustExecutor(DecompositionChecker(calls),checkpoint=store)
    trace=executor.execute(p,case.evidence,repeat='same')
    saved=json.loads(json.dumps(export_program(p)))
    assert RobustExecutor(DecompositionChecker(calls),checkpoint=CheckpointStore(store.path)).execute(
        restore_program(saved),case.evidence,repeat='same')==trace
    assert len(seen)==3
    changed=replace(p,nodes=(p.nodes[0],replace(p.nodes[1],criteria='Assess dominant red independently'),p.nodes[2]))
    executor.execute(changed,case.evidence,repeat='same')
    # Identical independent first check may reuse its durable response; the
    # changed evidence check and its dependent readout must both be recomputed.
    assert len(seen)==5 and changed.ref!=p.ref
    assert [v[0]['node']['id'] for v in seen[-2:]]==['red','readout']


def test_collapse_rejected_next_round_component_repair_succeeds(case,tmp_path):
    original=example_program();seed=decomposed();seen=[]
    calls=scoped(tmp_path/'calls',fake_provider(seed,seen))
    class Proposer:
        def propose(self,p,case,target,feedback,*,slot,limit):
            if 'round/0/' in slot:
                nodes=[asdict(original.nodes[0])]; remove=[n.id for n in p.nodes]; operator='subtree_replace'
            else:
                assert feedback['rejected_diagnostics']
                nodes=[asdict(replace(p.nodes[-1],criteria='Faithful repaired combination'))];remove=[];operator='checker_revision'
            return [{'reason':'Synthetic component repair','edits':[{'operator':operator,'remove_nodes':remove,
                'nodes':nodes,'remove_outcomes':[],'outcomes':[],'node_order':[]}],'outcome_mapping':[]}]
    class Checker:
        identity={'checker':'synthetic'}
        def check(self,p,node,*args,**kw):
            return {'status':'pass' if node.role=='support' else 'complete' if 'repaired' in node.criteria else 'absent',
                    'evidence':'Synthetic evidence','confidence':.99,'completion_tokens':10}
    result=RobustLeafOptimizer(DecompositionCompiler(calls,original),Proposer(),RobustEvaluator(RobustExecutor(Checker())),
        DemoGradient(),rubric=RUBRIC,selection='greedy').optimize(case,'yes',seed=seed)
    assert result.status=='confirmed_local' and result.seed!=result.selected
    assert any('Forced decomposition' in row.get('error','') for row in result.lineage)
    selected=restore_program(result.selected);validate_decomposition(selected,original)
    assert len(selected.nodes)==3 and seed.ref in result.candidates


def test_preflight_exact_cases_budget_and_resume_config_lock(tmp_path):
    m=preflight(tmp_path/'preflight'); prior=json.loads((SOURCE/'manifest.json').read_text())
    assert [c['id'] for c in m['cases']]==[c['id'] for c in prior['cases']]
    assert len({c['group'] for c in m['cases']})==3
    assert m['max_calls']==m['planned_maximum_calls']==900
    assert m['max_completion_tokens']==1152000 and m['reserve_calls']==240 and m['reserve_tokens']==240*1024
    assert m['strict_routing'] and m['version']=='forced-decomposition-pilot-v2'
    assert preflight(tmp_path/'preflight')==m
    m['minimum_supports']=1;save_json(tmp_path/'preflight/manifest.json',m)
    with pytest.raises(ValueError,match='Frozen'): preflight(tmp_path/'preflight')


def manifest(case):
    return {'model':'gpt-6-luna','provider':'openai','temperature':0,'reasoning_effort':'none','scope':'Synthetic',
        'arms':list(ARMS),'policy':asdict(RobustPolicy()),'random_seed':20261008,'max_calls':300,
        'max_completion_tokens':384000,'reserve_calls':80,'reserve_tokens':81920,'scope_limits':{'search':109,'final':40},
        'cases':[{'id':case.id,'instruction':case.instruction,'rubric':RUBRIC,'evidence':case.evidence,'target':'yes',
                  'group':case.group,'broad_seed':export_program(example_program())}]}


def test_two_arm_full_workflow_frozen_finals_leaf_execution_and_no_call_resume(case,tmp_path):
    p=decomposed();seen=[];m=manifest(case);directory=tmp_path/'run'
    fn=fake_provider(p,seen);result=execute(directory,m,lambda _:Engine(fn));n=len(seen)
    assert result['status']=='completed'
    assert all(r['support_status']=='locally_robust' for r in result['cases'][case.id].values())
    jobs={p.stem:json.loads(p.read_text()) for p in (directory/'jobs').glob('*.json')}
    slots=json.loads((directory/'budget.json').read_text())['attempted_slots']
    phases=[jobs[s]['phase'] for s in slots];first=phases.index('final')
    assert all(p=='final' for p in phases[first:])
    assert sum(j['stage']=='check' and j['phase']=='final' for j in jobs.values())==40
    for j in jobs.values():
        if j['stage'] in ('check','audit','audit_pair','compile_decomposition'):
            assert 'reference_label' not in j['payload'] and 'feedback' not in j['payload']
        if j['stage']=='check' and j['payload']['node']['id']=='readout': assert j['media_identity']==[]
    def forbidden(_): raise AssertionError('Attempted replay HTTP call')
    replay=execute(directory,m,forbidden)
    assert replay['cases']==result['cases'] and len(seen)==n
    bundle=json.loads((directory/'leaves.json').read_text());sc=CaseCalls(DurableCalls(directory,forbidden,
        identity={k:m[k] for k in ('model','provider','temperature','reasoning_effort')},
        **{k:m[k] for k in ('max_calls','max_completion_tokens','reserve_calls','reserve_tokens','scope_limits')}),
        'decomposed-greedy/'+case.id)
    executed=judge_program_leaf(bundle,'leaf:decomposed-greedy/'+case.id,case.evidence,
        RobustExecutor(DecompositionChecker(sc),checkpoint=CheckpointStore(directory/'observations.jsonl')),
        repeat='final/selected/decomposed-greedy/'+case.id+'/0')
    assert executed['label']=='yes' and executed['program_ref']==p.ref
    assert json.loads((directory/'scoring_fidelity.json').read_text())['seed']['agreement']==1


def test_failed_compilation_preserved_without_fake_semantic_feedback(case,tmp_path):
    p=decomposed();seen=[];directory=tmp_path/'failure';m=manifest(case)
    result=execute(directory,m,lambda _:Engine(fake_provider(p,seen,compile_failure=True)))
    assert result['status']=='completed' and result['cases'][case.id]['decomposed-greedy']['error']
    assert result['cases'][case.id]['broad-greedy']['support_status']=='locally_robust'
    assert not any(payload.get('program',{}).get('checker_template')==template('check') and
                   'feedback' in payload for payload,_ in seen)
    replay=execute(directory,m,lambda _:(_ for _ in ()).throw(AssertionError('HTTP replay')))
    assert replay['cases']==result['cases']


def test_strict_routing_guidance_changes_only_prompt_not_transactions(case,tmp_path):
    p=decomposed();seen=[];prompts=[]
    base=fake_provider(p,seen)
    def fn(prompt,kw):prompts.append(prompt);return base(prompt,kw)
    calls=scoped(tmp_path/'calls',fn)
    DecompositionProposer(calls,strict_routing=False).propose(p,case,'yes',{},slot='legacy')
    DecompositionProposer(calls,strict_routing=True).propose(p,case,'yes',{},slot='strict')
    assert seen[0][0]==seen[1][0]  # no reference/semantic criteria changed
    assert 'FIRST support: parent "", active_on []' not in prompts[0]
    assert 'FIRST support: parent "", active_on []' in prompts[1]
    assert 'copy all their unchanged fields exactly' in prompts[1]
    assert 'Use node_order [] when retaining the existing order' in prompts[1]


def test_format_followup_deducts_prior_accounting_and_pins_preparation(tmp_path):
    prior=tmp_path/'prior';old=preflight(prior)
    for i,c in enumerate(old['cases']):
        original=restore_program(c['broad_seed'])
        save_json(prior/'prepared'/f'{i}.json',{'broad':c['broad_seed'],'decomposed':export_program(decomposed(original)),
            'audits':{key:{'accepted':True,'reason':'offline'} for key in ('broad','decomposed')}})
    save_json(prior/'budget.json',{'calls':242,'completion_tokens_or_reserved':26479})
    save_json(prior/'results.json',{'status':'completed'})
    follow=preflight(tmp_path/'follow',prior_attempt=prior)
    assert follow['strict_routing'] and follow['cases']==old['cases']
    assert follow['max_calls']==658 and follow['max_completion_tokens']==1125521
    assert follow['reserve_calls']==240 and follow['shared_calls_per_case']==0
    assert preflight(tmp_path/'follow')==follow
    save_json(prior/'budget.json',{'calls':243,'completion_tokens_or_reserved':26479})
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'follow')


def test_format_followup_reuses_preparation_and_excludes_old_final_feedback(case,tmp_path):
    p=decomposed();m=manifest(case);prior=tmp_path/'old'
    save_json(prior/'prepared/0.json',{'broad':export_program(example_program()),'decomposed':export_program(p),
        'audits':{key:{'accepted':True,'reason':'offline'} for key in ('broad','decomposed')}})
    save_json(prior/'results.json',{'final_feedback':'must not reach proposer'})
    m.update(strict_routing=True,prior_attempt={'path':str(prior)})
    seen=[];result=execute(tmp_path/'follow',m,lambda _:Engine(fake_provider(p,seen)))
    assert result['status']=='completed'
    assert not any('original' in payload or 'programs' in payload for payload,_ in seen)
    assert 'must not reach proposer' not in json.dumps([payload for payload,_ in seen])
