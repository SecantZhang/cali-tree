"""Missing/nested evidence repairs, blind reviewers and durable model routing."""
from copy import deepcopy
from dataclasses import asdict, replace
import json

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.decision.calls import DurableCalls, CaseCalls, RoutedCalls, CallFailure, BudgetExhausted, ProviderStopped
from critical.core.decision.models import Requirement, Outcome
from critical.core.decision.robust.models import RobustProgram, Node, GATES, export_program, restore_program
from critical.core.decision.robust.executor import RobustExecutor
from critical.core.decision.robust.compiler import template as original_template
from critical.core.decision.robust.refinement import (EvidenceRefinementCompiler, EvidenceRefinementChecker,
    promote_decomposition, validate_refinement, template)
from critical.core.decision.robust.decomposition import validate_decomposition, template as old_template
from critical.core.optimization.program.models import Case
from critical.core.optimization.program.robust.discovery import VisualEvidenceDiagnosis, VisualReviewer
from critical.core.optimization.program.robust.refinement import apply_evidence_transaction, create_evidence_refinement_optimizer
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf

INSTRUCTION = 'Turn the image into a drawing made from chalk'
RUBRIC = 'yes: all requested transformation complete; partial: known progress but incomplete; no: no progress. Required unknowns stay unresolved.'


def original():
    return RobustProgram(INSTRUCTION, RUBRIC, (Requirement('r', INSTRUCTION, INSTRUCTION),),
        (Outcome('o', ('r',), 'Transform the image into a chalk drawing', 'the image', 'a drawing made from chalk'),),
        (Node('readout', 'requested', 'o', '', (), (), 'Has the image become a chalk drawing?',
              'complete: whole image transformed; partial: some progress; absent: no progress; unknown: insufficient evidence', 'the image'),),
        original_template('check'))


def seed():
    p = original()
    a = Node('medium', 'support', '', '', (), (), 'Is there chalk-like treatment?',
             'pass: chalk-like treatment; fail: no chalk treatment; unknown: unclear', 'the image')
    b = Node('drawing', 'support', '', 'medium', GATES, (), 'Are there drawn forms?',
             'pass: drawing-like forms; fail: none; unknown: unclear', 'the image')
    c = replace(p.nodes[0], parent='drawing', active_on=GATES, dependencies=('medium', 'drawing'),
                criteria='Both pass implies complete; one passes and one fails partial; both fail absent; unknown stays unknown')
    return validate_refinement(replace(p, nodes=(a,b,c), checker_template=template('check')), p)


def nested_transaction(p):
    # A broad drawing-form observation can pass while its finer extent check fails.
    child = Node('extent', 'support', '', 'drawing', GATES, ('drawing',),
        'Does the conversion cover the image as a whole rather than leave substantial photographic appearance?',
        'pass: whole-image conversion; fail: substantial photographic appearance remains; unknown: unclear', 'the image')
    readout = replace(p.nodes[-1], parent='extent', dependencies=('medium','drawing','extent'),
        criteria='complete: chalk, drawing and whole-image conversion established; partial: known drawing/chalk progress and incomplete extent; absent: no requested progress; unknown: required evidence unavailable')
    return {'reason':'Investigate whole-image extent missed by a broad drawing-form check, preserving the original requirement.',
        'edits':[{'operator':'add','remove_nodes':[],'nodes':[asdict(child),asdict(readout)],
                  'remove_outcomes':[],'outcomes':[],'node_order':['medium','drawing','extent','readout']}],
        'outcome_mapping':[], 'evidence_mapping':[{'node_id':'extent','requirement_id':'r','source_phrase':INSTRUCTION}]}


def finding():
    return {'kind':'nested_evidence','requirement_id':'r','source_phrase':INSTRUCTION,'parent_id':'drawing',
        'question':'Does the conversion cover the image as a whole?',
        'criteria':'pass: whole-image conversion; fail: incomplete; unknown: unclear',
        'evidence':'Hypothesis: remaining photographic regions warrant inspection.',
        'rationale':'Drawing-like forms alone may not establish the extent of the requested transformation.'}


@pytest.fixture
def case(tmp_path):
    evidence={}
    for key,color in [('source_image','blue'),('edited_image','red')]:
        path=tmp_path/(key+'.png');Image.new('RGB',(10,10),color).save(path);evidence[key]=str(path)
    return Case('chalk-synthetic',INSTRUCTION,evidence)


class Engine:
    def __init__(self, fn): self.fn=fn
    def generate(self,prompt,**kw): return self.fn(prompt,kw)


def provider(seen, *, unknown=False, audit_all=False, no_repair=False):
    def fn(prompt,kw):
        payload=json.loads(prompt.split('INPUT_JSON: ',1)[1]);seen.append((deepcopy(payload),kw))
        props=kw['schema']['properties']
        if 'findings' in props: value={'findings':[finding()]}
        elif 'transactions' in props: value={'transactions':[] if no_repair else [nested_transaction(seed())]}
        elif 'text' in props: value={'text':'Investigate missed whole-image extent without forcing a label.'}
        elif 'nodes' in props: value={'nodes':seed().to_dict()['nodes']}
        elif 'accepted' in props:
            value={'accepted':audit_all or len(payload['program']['nodes'])==4,
                   'reason':'Extent is covered' if len(payload['program']['nodes'])==4 else 'Broad supports miss extent'}
        elif 'broad' in props:
            value={'broad':{'accepted':True,'reason':'Faithful direct check'},
                   'decomposed':{'accepted':False,'reason':'Broad supports miss extent'}}
        else:
            n=payload['node'];state=('unknown' if unknown else 'fail') if n['id']=='extent' else 'pass'
            if n['role']=='requested':state='partial' if len(n['dependencies']) in (0,3) else 'complete'
            value={'status':state,'evidence':'Synthetic image-grounded observation','confidence':.99,
                   'used_dependency_ids':n['dependencies']}
        return {'parsed':value,'completionTokens':10,'promptTokens':20,'model':'mock-returned','finishReason':'stop'}
    return fn


def calls_at(path,fn,**limits):
    return CaseCalls(DurableCalls(path,lambda _:Engine(fn),identity={'model':'primary','family':'family-a'},
        scope_limits={'search':109,'final':40},**limits),'chalk-synthetic')


def test_audit_rejected_seed_gets_visual_nested_repair_and_exact_reload(case,tmp_path):
    seen=[];calls=calls_at(tmp_path/'calls',provider(seen));cp=CheckpointStore(tmp_path/'observations.jsonl')
    optimizer=create_evidence_refinement_optimizer(calls,original(),checkpoint=cp)
    bundle=CaliTreeBuilder.build_program_leaves([case],reference_labels={case.id:'partial'},
        optimizer_factory=lambda _:optimizer,seeds={case.id:seed()})
    r=bundle['nodes']['leaf:'+case.id]['result'];old=seed().ref;selected=r['selected']['program_ref']
    assert r['status']=='confirmed_local' and selected!=old
    assert 'diagnostic' in r['candidates'][old] and 'screen' not in r['candidates'][old]
    assert 'confirmation' not in r['candidates'][old] and not r['candidates'][old]['audit']['accepted']
    assert r['candidates'][selected]['confirmation']['agreement']==1
    history=r['lineage'][-1]
    assert all(old not in v['retained'] for v in history['screen_frontier'])
    events=[e for e in history['events'] if 'visual_discovery' in e]
    assert events[0]['report_kind']=='diagnostic_only' and events[0]['gradients']
    assert events[0]['visual_discovery']['findings'][0]['status']=='hypothesis'
    discovery=[p for p,_ in seen if 'observations' in p and 'max_findings' in p]
    assert [o['status'] for o in discovery[0]['observations'][0]]==['pass','pass','complete']
    for payload,kw in seen:
        if 'transactions' not in kw['schema']['properties'] and 'text' not in kw['schema']['properties']:
            assert 'reference_label' not in payload and 'feedback' not in payload
            assert 'agreement' not in payload and 'label_distribution' not in payload
        if 'status' in kw['schema']['properties'] and payload['node']['role']=='requested': assert kw['media_inputs']==[]
    n=len(seen)
    reloaded=json.loads(json.dumps(bundle));executor=RobustExecutor(EvidenceRefinementChecker(calls),checkpoint=cp)
    trace=judge_program_leaf(reloaded,'leaf:'+case.id,case.evidence,executor,repeat='saved-inference')
    assert trace['label']=='partial'
    assert [o['status'] for o in trace['observations']]==['pass','pass','fail','partial']
    assert trace['observations'][2]['dependencies'][0]['check_id']=='drawing'
    assert len(seen)==n+4
    replay=create_evidence_refinement_optimizer(calls,original(),checkpoint=CheckpointStore(cp.path))
    again=replay.optimize(case,'partial',seed=seed())
    assert json.loads(json.dumps({k:v for k,v in again.to_dict().items() if k!='usage'}))==json.loads(json.dumps({k:v for k,v in r.items() if k!='usage'}))
    assert len(seen)==n+4


@pytest.mark.parametrize('fault',['missing-map','unsupported-phrase','cycle','over-cap','binding'])
def test_atomic_nested_edits_preserve_requirements(fault):
    p=seed();before=p.to_dict();tx=nested_transaction(p)
    child=apply_evidence_transaction(p,tx)
    assert child.requirements==p.requirements and child.outcomes==p.outcomes and p.to_dict()==before
    if fault=='missing-map':tx['evidence_mapping']=[]
    if fault=='unsupported-phrase':tx['evidence_mapping'][0]['source_phrase']='Remove the giraffes'
    if fault=='cycle':tx['edits'][0]['nodes'][0]['parent']='readout'
    if fault=='over-cap':
        tx['edits'][0]['nodes'].append({**tx['edits'][0]['nodes'][0],'id':'extra'})
        tx['edits'][0]['node_order'].insert(3,'extra')
    if fault=='binding':
        tx['edits'][0]['outcomes']=[{**asdict(p.outcomes[0]),'target':'another image'}]
        tx['outcome_mapping']=[{'old_outcome':'o','replacements':['o']}]
    with pytest.raises(ValueError):apply_evidence_transaction(p,tx)
    assert p.to_dict()==before


def test_unknown_nested_evidence_and_independent_legacy_contract(case,tmp_path):
    p=seed();seen=[];calls=calls_at(tmp_path/'calls',provider(seen,unknown=True))
    old=replace(p,checker_template=old_template('check'));validate_decomposition(old,original())
    promoted=promote_decomposition(old)
    assert promoted.ref!=old.ref and promote_decomposition(restore_program(export_program(old)))==promoted
    nested=apply_evidence_transaction(promoted,nested_transaction(promoted))
    with pytest.raises(ValueError):validate_decomposition(nested)
    trace=RobustExecutor(EvidenceRefinementChecker(calls)).execute(nested,case.evidence)
    assert trace['label'] is None and not trace['observations'][-1]['queried'] and len(seen)==3


def test_multiple_families_share_accounting_and_failed_slots(case,tmp_path):
    seen=[];routes={}
    for name in ['other-a','other-b']:
        routes[name]={'identity':{'model':name,'family':name},'engine_factory':lambda _:Engine(provider(seen))}
    parent=DurableCalls(tmp_path/'calls',lambda _:Engine(provider(seen)),identity={'model':'primary'},routes=routes,
        max_calls=4,reserve_calls=1,max_completion_tokens=9000,reserve_tokens=1024)
    scoped=CaseCalls(parent,case.id)
    reviewers=[VisualReviewer(n,n,RoutedCalls(scoped,n)) for n in routes]
    diagnosis=VisualEvidenceDiagnosis(reviewers)
    discovered=diagnosis.discover(seed(),case,None,slot='inspect')
    assert len(discovered['reviews'])==2 and len(discovered['findings'])==2
    assert parent.budget['calls']==2 and parent.budget['cases'][case.id]['search']==2
    assert len(seen)==2 and diagnosis.discover(seed(),case,None,slot='inspect')==discovered and len(seen)==2
    jobs=[json.loads(p.read_text()) for p in (parent.directory/'jobs').glob('*.json')]
    assert {j['route'] for j in jobs}==set(routes) and all(j['response']['model']=='mock-returned' for j in jobs)
    with pytest.raises(BudgetExhausted):diagnosis.discover(seed(),case,None,slot='fresh')
    assert parent.budget['calls']==3  # one final call remains reserved across model families
    changed=deepcopy({n:v['identity'] for n,v in routes.items()});changed['other-a']['model']='replacement'
    with pytest.raises(ValueError,match='Changed call protocol'):
        DurableCalls(parent.directory,lambda _:Engine(provider(seen)),identity={'model':'primary'},
            routes={n:{'identity':changed[n],'engine_factory':routes[n]['engine_factory']} for n in routes},
            max_calls=4,reserve_calls=1,max_completion_tokens=9000,reserve_tokens=1024)


def test_route_identities_cannot_change_mid_run(case,tmp_path):
    seen=[];routes={'reviewer':{'identity':{'model':'other','family':'other-family'},
                              'engine_factory':lambda _:Engine(provider(seen))}}
    parent=DurableCalls(tmp_path/'calls',lambda _:Engine(provider(seen)),identity={'model':'primary'},routes=routes)
    scope=CaseCalls(parent,case.id);review=RoutedCalls(scope,'reviewer')
    routes['reviewer']['identity']['model']='external-mutation'
    assert review.identity['model']=='other'
    review.identity['model']='internal-mutation'
    with pytest.raises(ValueError,match='Changed frozen'):
        review.call('visual_discovery',{}, {},template='label-blind review',slot='changed')
    assert parent.budget['calls']==0 and not seen


def test_discovery_invalid_provenance_and_transport_are_not_visual_absence(case,tmp_path):
    seen=[]
    def bad(prompt,kw):
        row=provider(seen)(prompt,kw);row['parsed']['findings'][0]['source_phrase']='Remove the subjects';return row
    c=calls_at(tmp_path/'invalid',bad)
    d=VisualEvidenceDiagnosis([VisualReviewer('one','family-a',c)])
    result=d.discover(seed(),case,None,slot='bad')
    assert not result['findings'] and 'provenance' in result['failures'][0]['error']
    failures=[]
    def failed(*args):failures.append(1);raise OSError('transport interrupted')
    c=calls_at(tmp_path/'failed',failed);d=VisualEvidenceDiagnosis([VisualReviewer('one','family-a',c)])
    assert d.discover(seed(),case,None,slot='one')['failures'][0]['failure']=='CallFailure'
    d.discover(seed(),case,None,slot='one');assert len(failures)==1
    d.discover(seed(),case,None,slot='two')
    with pytest.raises(ProviderStopped):d.discover(seed(),case,None,slot='three')
    assert len(failures)==3 and c.budget['stopped']=='Three consecutive transport failures'


def test_rejected_diagnostics_never_qualify_or_replace_seed(case,tmp_path):
    seen=[];c=calls_at(tmp_path/'calls',provider(seen,no_repair=True))
    opt=create_evidence_refinement_optimizer(c,original())
    result=opt.optimize(case,'yes',seed=seed())
    assert result.status=='unresolved' and result.selected==result.seed
    candidate=result.candidates[seed().ref]
    assert candidate['diagnostic']['agreement']==1 and 'screen' not in candidate and 'confirmation' not in candidate
    assert not result.lineage[-1]['screen_frontier'] and not result.lineage[-1]['confirmation_frontier']


def test_insufficient_discovery_budget_retains_seed_and_final_reservation(case,tmp_path):
    seen=[];c=calls_at(tmp_path/'calls',provider(seen),max_calls=3,reserve_calls=1,
        max_completion_tokens=10000,reserve_tokens=1024)
    result=create_evidence_refinement_optimizer(c,original()).optimize(case,'partial',seed=seed())
    assert result.status=='budget_exhausted' and result.seed==result.selected and c.budget['calls']==2


def test_discovery_still_reaches_proposer_after_backward_failure(case,tmp_path):
    seen=[];c=calls_at(tmp_path/'calls',provider(seen))
    opt=create_evidence_refinement_optimizer(c,original())
    class FailedGradient:
        def feedback(self,*args,**kwargs):raise CallFailure('retained schema failure')
    opt.gradient=FailedGradient()
    r=opt.optimize(case,'partial',seed=seed())
    assert r.status=='confirmed_local'
    events=r.lineage[-1]['events']
    assert any(e.get('gradient_failure',{}).get('failure')=='CallFailure' and e.get('visual_discovery') for e in events)
    assert any('retained schema failure' in str(p.get('feedback',{})) for p,_ in seen if 'feedback' in p)


def test_nested_edit_invalidates_affected_observations(case,tmp_path):
    seen=[];c=calls_at(tmp_path/'calls',provider(seen));cp=CheckpointStore(tmp_path/'obs')
    p=apply_evidence_transaction(seed(),nested_transaction(seed()))
    RobustExecutor(EvidenceRefinementChecker(c),checkpoint=cp).execute(p,case.evidence,repeat='same')
    assert len(seen)==4
    changed=replace(p,nodes=(*p.nodes[:2],replace(p.nodes[2],criteria='Refined whole-image extent boundary'),p.nodes[3]))
    trace=RobustExecutor(EvidenceRefinementChecker(c),checkpoint=CheckpointStore(cp.path)).execute(changed,case.evidence,repeat='same')
    assert trace['program_ref']!=p.ref and len(seen)==6
    assert [x[0]['node']['id'] for x in seen[-2:]]==['extent','readout']


def test_preflight_new_protocol_does_not_reinterpret_old_artifacts(tmp_path):
    from run.calitree_forced_decomposition import preflight
    m=preflight(tmp_path/'new',chalk_only=True,evidence_refinement=True)
    assert m['contract']=='nested-evidence-readout-v1' and m['max_checks']==4
    assert m['reserve_calls']==80 and m['scope_limits']['search']==109
    assert preflight(tmp_path/'new',chalk_only=True,evidence_refinement=True)==m
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'new',chalk_only=True)
    with pytest.raises(ValueError,match='fresh run'):preflight(tmp_path/'x',evidence_refinement=True,prior_attempt=tmp_path/'new')


def test_small_pilot_budget_reserves_complete_final_comparison(tmp_path):
    from run.calitree_forced_decomposition import preflight
    with pytest.raises(ValueError,match='chalk-only'):preflight(tmp_path/'bad',small_pilot=True)
    m=preflight(tmp_path/'small',chalk_only=True,evidence_refinement=True,small_pilot=True)
    assert len(m['cases'])==1 and m['max_calls']==150 and m['max_completion_tokens']==192000
    assert m['reserve_calls']==10+40 and m['reserve_tokens']==50*1024
    assert m['uncapped_schedule_maximum_calls']==300 and m['budget_may_limit_search']
    assert preflight(tmp_path/'small',chalk_only=True,evidence_refinement=True,small_pilot=True)==m
    with pytest.raises(ValueError,match='Frozen'):preflight(tmp_path/'small',chalk_only=True,evidence_refinement=True)


def test_bounded_saved_seed_followup_preserves_failed_preparation(tmp_path):
    from run.calitree_forced_decomposition import preflight, ROOT
    from critical.core.decision.artifacts import save_json
    previous=tmp_path/'previous'
    preflight(previous,chalk_only=True,evidence_refinement=True,small_pilot=True)
    save_json(previous/'budget.json',{'calls':38,'completion_tokens_or_reserved':3210,'stopped':None})
    save_json(previous/'results.json',{'status':'completed'})
    save_json(previous/'prepared/0.json',{'decomposition_error':'Invalid ancestor evidence references'})
    source=ROOT/'logs/exps/261008-forced-decomposition-resumed-v1/frozen/decomposed-greedy/1.json'
    original_prepared=(previous/'prepared/0.json').read_bytes()
    m=preflight(tmp_path/'seeded',chalk_only=True,evidence_refinement=True,small_pilot=True,
        decomposition_seed=source,previous_small_attempt=previous)
    assert m['max_calls']==112 and m['max_completion_tokens']==188790
    assert m['shared_calls_per_case']==1 and m['decomposition_seed']['program']['checker_template']==template('check')
    assert 'result' not in m['decomposition_seed']['program']
    assert (previous/'prepared/0.json').read_bytes()==original_prepared
    assert preflight(tmp_path/'seeded',chalk_only=True,evidence_refinement=True,small_pilot=True)==m
    save_json(previous/'budget.json',{'calls':39,'completion_tokens_or_reserved':3210,'stopped':None})
    with pytest.raises(ValueError,match='Frozen'):
        preflight(tmp_path/'seeded',chalk_only=True,evidence_refinement=True,small_pilot=True)
    save_json(previous/'budget.json',{'calls':38,'completion_tokens_or_reserved':3210,'stopped':'Provider rejected the request'})
    with pytest.raises(ValueError,match='provider stop'):
        preflight(tmp_path/'blocked',chalk_only=True,evidence_refinement=True,small_pilot=True,
            decomposition_seed=source,previous_small_attempt=previous)


def test_invalid_sibling_compilation_is_retained_without_schema_repair(case,tmp_path):
    seen=[]
    def invalid(prompt,kw):
        row=provider(seen)(prompt,kw)
        for n in row['parsed']['nodes']:
            n['parent']='';n['active_on']=[]
        return row
    calls=calls_at(tmp_path/'calls',invalid)
    compiler=EvidenceRefinementCompiler(calls,original())
    for _ in range(2):
        with pytest.raises(ValueError,match='ancestor'):
            compiler.compile(case.instruction,RUBRIC,slot='compile')
    assert len(seen)==1 and calls.budget['calls']==1


def test_refinement_runner_freezes_before_final_and_resumes_without_calls(case,tmp_path):
    from run.calitree_forced_decomposition import execute, ARMS
    from critical.core.optimization.program.robust.metrics import RobustPolicy
    from critical.core.decision.artifacts import save_json
    raw={'id':case.id,'instruction':case.instruction,'rubric':RUBRIC,'target':'partial','evidence':case.evidence,
         'group':'synthetic','broad_seed':export_program(original())}
    manifest={'cases':[raw],'arms':list(ARMS),'scope':'Synthetic mocked-provider experiment',
        'evidence_refinement':True,'policy':asdict(RobustPolicy()),'random_seed':42,
        'model':'primary','provider':'mock','temperature':0,'reasoning_effort':'none',
        'max_calls':300,'max_completion_tokens':384000,'reserve_calls':80,'reserve_tokens':81920,
        'scope_limits':{'search':109,'final':40}}
    seen=[];fn=provider(seen);output=tmp_path/'run';save_json(output/'manifest.json',manifest)
    result=execute(output,manifest,lambda _:Engine(fn))
    assert result['status']=='completed' and result['cases'][case.id]['decomposed-greedy']['support_status']=='locally_robust'
    assert result['cases'][case.id]['decomposed-greedy']['final']['selected']['agreement']==1
    n=len(seen)
    resumed=execute(output,manifest,lambda _:Engine(fn))
    assert len(seen)==n and resumed['cases']==result['cases']
    budget=json.loads((output/'budget.json').read_text())
    jobs={p.stem:json.loads(p.read_text()) for p in (output/'jobs').glob('*.json')}
    ordered=[jobs[k] for k in budget['attempted_slots']]
    first=next(i for i,j in enumerate(ordered) if j['phase']=='final')
    assert all(j['stage']=='check' and j['phase']=='final' for j in ordered[first:])
    changed=deepcopy(manifest);changed['cases'][0]['target']='no'
    evaluated=execute(output,changed,lambda _:Engine(fn))
    assert len(seen)==n and evaluated['cases'][case.id]['decomposed-greedy']['final']['selected']['agreement']==0
