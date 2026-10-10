"""V7: protected requirement mass and graded fulfillment, independent of confidence."""
from collections import Counter
from dataclasses import asdict,dataclass,replace
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from .artifacts import digest,save_json
from .compiler import TEXT,array,enum,object_schema,media_inputs
from .models import Requirement,Outcome
from .counting import CountingProgram,CountingExecutor,validate as validate_base,count_states
from .counting_v6 import EndpointDecision,EndpointExecutor
from critical.core.optimization.program.models import AppliedProgramEdit

VERSION='decision-leaf-v7'
PROTOCOL='typed-fulfillment-v1'
AGGREGATION='protected-weighted-fulfillment-bounds-v1'
TEMPLATES=Path(__file__).parents[1]/'prompts/templates/typed_fulfillment_v1'


def template(name):return (TEMPLATES/(name+'.txt')).read_text()
def rational(value):return Fraction(str(value))
def numeric(value):return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1
def bucket(score):return 'yes' if score>=Fraction(9,10) else 'no' if score<=Fraction(1,10) else 'partial'
def state(label):return {'yes':'complete','no':'absent','partial':'partial',None:'unknown'}[label]


@dataclass(frozen=True)
class WeightRoot:
    id:str
    requirement_id:str
    source_quote:str
    endpoint:str
    numerator:int
    denominator:int


@dataclass(frozen=True)
class FulfillmentDecision(EndpointDecision):
    zero_when:str=''
    half_when:str=''
    full_when:str=''
    root_id:str=''
    weight_numerator:int=0
    weight_denominator:int=1

    @property
    def weight(self):return Fraction(self.weight_numerator,self.weight_denominator)


@dataclass(frozen=True)
class FulfillmentProgram(CountingProgram):
    version:str=VERSION
    aggregation:str=AGGREGATION
    decomposition_reason:str=''
    weight_roots:tuple[WeightRoot,...]=()
    scoring_mode:str='fulfillment'
    satisfied_threshold:float=.9
    nonsatisfied_threshold:float=.1

    @property
    def ref(self):validate(self);return digest(self.to_dict())

    @classmethod
    def from_dict(cls,row):
        if row.get('version')!=VERSION:raise ValueError('Explicit fulfillment version mismatch')
        return validate(cls(**{**row,'requirements':tuple(Requirement(**r) for r in row['requirements']),
            'outcomes':tuple(Outcome(**{**o,'requirement_ids':tuple(o['requirement_ids'])}) for o in row['outcomes']),
            'weight_roots':tuple(WeightRoot(**r) for r in row['weight_roots']),
            'nodes':tuple(FulfillmentDecision(**n) for n in row['nodes'])}))


def validate(p,original=None):
    validate_base(p,original,expected_version=VERSION,expected_aggregation=AGGREGATION,allowed_roles=('decision','evidence'))
    if p.scoring_mode not in ('binary','fulfillment') or not p.decomposition_reason.strip():raise ValueError('Frozen scoring mode and decomposition reason required')
    if (p.satisfied_threshold,p.nonsatisfied_threshold)!=(.9,.1):raise ValueError('Fulfillment thresholds are frozen at .9/.1')
    roots={r.id:r for r in p.weight_roots};reqs={r.id:r for r in p.requirements}
    if not roots or len(roots)!=len(p.weight_roots):raise ValueError('Need unique immutable weight roots')
    totals=Counter()
    for r in roots.values():
        if r.requirement_id not in reqs or not r.endpoint.strip() or not r.source_quote.strip() or (
                r.source_quote not in reqs[r.requirement_id].source_phrase and r.source_quote not in p.rubric):raise ValueError('Invalid weight provenance')
        if type(r.numerator) is not int or type(r.denominator) is not int or r.numerator<=0 or r.denominator<=0:raise ValueError('Positive exact root mass required')
        totals[r.requirement_id]+=Fraction(r.numerator,r.denominator)
    if set(totals)!=set(reqs) or any(v!=Fraction(1,len(reqs)) for v in totals.values()):raise ValueError('Requirements have fixed equal mass totaling one')
    allocated=Counter();aspects=set()
    for n in p.nodes:
        if not isinstance(n,FulfillmentDecision) or not all(isinstance(v,str) and v.strip() for v in
                (n.source_quote,n.aspect,n.endpoint,n.necessity,n.zero_when,n.half_when,n.full_when)):raise ValueError('Grounded endpoints and 0/.5/1 anchors required')
        if n.source_quote not in reqs[n.requirement_id].source_phrase and n.source_quote not in p.rubric:raise ValueError('No exact source quote')
        if re.search(r'\b(progress|attempt)\b',n.question+' '+n.endpoint,re.I):raise ValueError('An endpoint must not become a generic progress helper')
        if type(n.weight_numerator) is not int or type(n.weight_denominator) is not int or n.weight_denominator<=0:raise ValueError('Invalid exact decision mass')
        if n.role=='evidence':
            if n.weight!=0 or n.root_id:raise ValueError('Auxiliary evidence has zero mass and no root')
        else:
            if n.weight<=0 or n.root_id not in roots or roots[n.root_id].requirement_id!=n.requirement_id:raise ValueError('Required node needs its original mass root')
            allocated[n.root_id]+=n.weight
        aspect=(n.requirement_id,n.aspect.casefold().strip())
        if aspect in aspects:raise ValueError('Duplicate declared aspect')
        aspects.add(aspect)
    if set(allocated)!=set(roots) or any(allocated[k]!=Fraction(r.numerator,r.denominator) for k,r in roots.items()):raise ValueError('Required mass cannot be deleted or redistributed between roots')
    if isinstance(original,FulfillmentProgram) and (p.weight_roots,p.scoring_mode)!=(original.weight_roots,original.scoring_mode):raise ValueError('Weight ledger and scoring mode are immutable during optimization')
    return p


def export_program(p):return {'program_ref':p.ref,'program':p.to_dict()}
def restore_program(row):
    p=FulfillmentProgram.from_dict(row['program'])
    if p.ref!=row['program_ref']:raise ValueError('Fulfillment hash mismatch')
    return p
def variant(p,mode):return validate(replace(p,scoring_mode=mode))


FIELDS=('requirement_id','question','criteria','binding','source_quote','aspect','endpoint','necessity','zero_when','half_when','full_when')
SPEC_SCHEMA=object_schema({k:TEXT for k in FIELDS})
DECISION_SCHEMA=object_schema({'id':TEXT,**SPEC_SCHEMA['properties']})
COMPILE_SCHEMA=object_schema({'decisions':{**array(SPEC_SCHEMA),'minItems':1,'maxItems':4},'decomposition_reason':TEXT})
ACTION_SCHEMA=object_schema({'operation':enum(('add','remove','revise','split')),'target_id':TEXT,'decisions':{**array(DECISION_SCHEMA),'maxItems':4}})
SCORE={'type':'number','minimum':0,'maximum':1}
EXPECTATION_SCHEMA=object_schema({'decision_id':TEXT,'fulfillment_score':SCORE,'evidence_reason':TEXT})
TX_SCHEMA=object_schema({'version':enum((PROTOCOL,)),'reason':TEXT,'actions':{**array(ACTION_SCHEMA),'minItems':1,'maxItems':4},
    'predicted_scores':{**array(EXPECTATION_SCHEMA),'minItems':1,'maxItems':4}})
PROPOSAL_SCHEMA=object_schema({'transactions':{**array(TX_SCHEMA),'maxItems':2}})
OBS_SCHEMA=object_schema({'fulfillment_score':{**SCORE,'type':['number','null']},'evidence':TEXT,'confidence':{**SCORE,'type':['number','null']}})


class FulfillmentCompiler:
    def __init__(self,calls,original):self.calls,self.original=calls,original
    def compile(self,instruction,rubric,*,slot):
        if (instruction,rubric)!=(self.original.instruction,self.original.rubric):raise ValueError('Original instruction changed')
        value,ref=self.calls.call('compile_fulfillment',{'instruction':instruction,'rubric':rubric,
            'requirements':[asdict(r) for r in self.original.requirements],'outcomes':[asdict(o) for o in self.original.outcomes],
            'preferred_decisions':2,'max_decisions':4,'protocol':PROTOCOL},COMPILE_SCHEMA,template=template('compile'),slot=slot,max_tokens=2048)
        if set(value)!=set(COMPILE_SCHEMA['properties']) or not isinstance(value['decisions'],list):raise ValueError('Invalid grading specifications')
        counts=Counter(s['requirement_id'] for s in value['decisions']);nodes=[];roots=[]
        for i,s in enumerate(value['decisions'],1):
            if set(s)!=set(FIELDS):raise ValueError('Models cannot supply weights or roles')
            mass=Fraction(1,len(self.original.requirements)*counts[s['requirement_id']]);rid=f'root.d{i}'
            roots.append(WeightRoot(rid,s['requirement_id'],s['source_quote'],s['endpoint'],mass.numerator,mass.denominator))
            nodes.append(FulfillmentDecision(id=f'd{i}',**s,root_id=rid,weight_numerator=mass.numerator,weight_denominator=mass.denominator))
        p=validate(FulfillmentProgram(instruction,rubric,self.original.requirements,self.original.outcomes,tuple(nodes),template('check'),
            decomposition_reason=value['decomposition_reason'],weight_roots=tuple(roots)),self.original)
        save_json(self.calls.directory/'constructions'/f'{ref}.json',{'specification':value,'program':export_program(p),
            'semantic_audit':{'status':'disabled','performed':False},'weight_assignment':'equal requirements; equal seed facets; exact conserved splits'})
        return p


def apply_transaction(parent,tx):
    validate(parent)
    if set(tx)!=set(TX_SCHEMA['properties']) or tx['version']!=PROTOCOL or not isinstance(tx['reason'],str) or not tx['reason'].strip():raise ValueError('Invalid fulfillment transaction')
    if not isinstance(tx['actions'],list) or not 1<=len(tx['actions'])<=4:raise ValueError('Bounded atomic actions required')
    nodes=list(parent.nodes);changed=set()
    for a in tx['actions']:
        if set(a)!=set(ACTION_SCHEMA['properties']) or a['operation'] not in ('add','remove','revise','split') or not isinstance(a['target_id'],str) or not isinstance(a['decisions'],list):raise ValueError('Invalid grading action')
        specs=a['decisions']
        if any(set(s)!=set(DECISION_SCHEMA['properties']) for s in specs):raise ValueError('Weights, roots and roles are assigned only by code')
        op=a['operation'];ids=[n.id for n in nodes]
        if op=='add':
            if a['target_id'] or len(specs)!=1 or specs[0]['id'] in ids:raise ValueError('Addition requires one unique auxiliary check')
            nodes.append(FulfillmentDecision(**specs[0],role='evidence'));changed.add(specs[0]['id']);continue
        if a['target_id'] not in ids:raise ValueError('Missing target')
        pos=ids.index(a['target_id']);old=nodes[pos]
        if op=='remove':
            if specs or old.role!='evidence':raise ValueError('Only zero-weight auxiliary evidence can be removed; do not delete fulfillment mass')
            nodes.pop(pos);continue
        if op=='revise':
            if len(specs)!=1 or specs[0]['id']!=old.id or specs[0]['requirement_id']!=old.requirement_id:raise ValueError('Revision preserves identity and requirement')
            # Refining criteria/binding/anchors is permitted; requested endpoint remains fixed.
            if specs[0]['endpoint']!=old.endpoint:raise ValueError('Revision cannot replace the requested endpoint')
            replacements=[FulfillmentDecision(**specs[0],role=old.role,root_id=old.root_id,
                weight_numerator=old.weight_numerator,weight_denominator=old.weight_denominator)]
        else:
            if old.role!='decision' or not 2<=len(specs)<=4 or any(s['requirement_id']!=old.requirement_id for s in specs):raise ValueError('Split preserves the parent requirement')
            mass=old.weight/len(specs)
            replacements=[FulfillmentDecision(**s,root_id=old.root_id,weight_numerator=mass.numerator,weight_denominator=mass.denominator) for s in specs]
        nodes[pos:pos+1]=replacements;changed.update(n.id for n in replacements)
    child=validate(replace(parent,nodes=tuple(nodes)),parent);pred=tx['predicted_scores']
    if not isinstance(pred,list) or not 1<=len(pred)<=4:raise ValueError('Predicted evidence impact required')
    expected=[]
    for e in pred:
        if set(e)!=set(EXPECTATION_SCHEMA['properties']) or e['decision_id'] not in {n.id for n in nodes} or not numeric(e['fulfillment_score']) or not isinstance(e['evidence_reason'],str) or not e['evidence_reason'].strip():raise ValueError('Invalid score prediction')
        expected.append(e['decision_id'])
    if len(set(expected))!=len(expected) or not (changed & {n.id for n in nodes})<=set(expected):raise ValueError('Predict all changed checks')
    return AppliedProgramEdit(child,{'protocol':PROTOCOL,'parent_ref':parent.ref,'child_ref':child.ref,'typed_actions':tx['actions'],
        'predicted_scores':pred,'expanded_decisions':[asdict(n) for n in nodes],'mass_preserved':True,'semantic_audit':'disabled'})


def score_bounds(nodes,observations):
    rows=[(n,o) for n,o in zip(nodes,observations) if n.role=='decision' and o['eligible']]
    mass=sum((n.weight for n,o in rows),Fraction())
    if not mass:return None,None
    lower=Fraction();upper=Fraction()
    for n,o in rows:
        value=o.get('fulfillment_score') if o['valid'] else None
        if numeric(value):lower+=n.weight*rational(value);upper+=n.weight*rational(value)
        else:upper+=n.weight
    return lower/mass,upper/mass


def readouts(nodes,observations,*,unknown_applicability=False):
    low,high=score_bounds(nodes,observations)
    if unknown_applicability:low,high=Fraction(0),Fraction(1)
    graded=None if low is None or unknown_applicability or bucket(low)!=bucket(high) else bucket(low)
    values=[o.get('binary_status','unknown') for n,o in zip(nodes,observations) if n.role=='decision' and o['eligible']]
    binary=None if unknown_applicability else {'complete':'yes','partial':'partial','absent':'no'}.get(count_states(values))
    return binary,graded,low,high


def aggregate_trace(p,observations,transitions):
    unknown={r for o in p.outcomes if o.applicability=='unknown' for r in o.requirement_ids}
    binary,graded,low,high=readouts(p.nodes,observations,unknown_applicability=bool(unknown))
    label=binary if p.scoring_mode=='binary' else graded;requirements={}
    applicable={r for o in p.outcomes if o.applicability=='applicable' for r in o.requirement_ids}
    for r in p.requirements:
        subset=[(n,o) for n,o in zip(p.nodes,observations) if n.requirement_id==r.id]
        b,g,_,_=readouts([n for n,o in subset],[o for n,o in subset],unknown_applicability=r.id in unknown)
        requirements[r.id]=state(b if p.scoring_mode=='binary' else g) if r.id in applicable or r.id in unknown else 'not_applicable'
    outcomes={o.id:{'status':'unknown' if o.applicability!='applicable' or any(requirements[r]=='unknown' for r in o.requirement_ids) else
        'complete' if all(requirements[r]=='complete' for r in o.requirement_ids) else 'absent' if all(requirements[r]=='absent' for r in o.requirement_ids) else 'partial',
        'applicability':o.applicability,'source':'protected_fulfillment','reason':'Frozen weighted fulfillment or binary comparison'} for o in p.outcomes}
    return {'program_ref':p.ref,'label':label,'resolved':label is not None,'requirements':requirements,'outcomes':outcomes,
        'observations':observations,'transitions':transitions,'fulfillment':{'lower':float(low) if low is not None else None,
            'upper':float(high) if high is not None else None,'score':float(low) if low is not None and low==high else None,
            'binary_label':binary,'fulfillment_label':graded,'mode':p.scoring_mode,'thresholds':{'yes':.9,'no':.1},
            'unknowns_are_intervals':True,'semantic_audit':'disabled','model_readout':False}}


class FulfillmentChecker:
    def __init__(self,calls):
        self.calls=calls;self.identity={'provider':calls.identity,'checker':'anchored-fulfillment-v1','scope':getattr(calls,'case_id',None)}
    def check(self,p,n,evidence,*,slot,final=False):
        # No weights, aggregation mode, thresholds, labels, or optimization feedback reach the observer.
        value,ref=self.calls.call('check_fulfillment',{'instruction':p.instruction,
            'condition':{k:asdict(n)[k] for k in FIELDS},'role':n.role,
            'requirement':asdict(next(r for r in p.requirements if r.id==n.requirement_id))},OBS_SCHEMA,
            template=p.checker_template,media=media_inputs(evidence),slot=slot,final=final,max_tokens=1024)
        job=json.loads((self.calls.directory/'jobs'/f'{ref}.json').read_text());f=value.get('fulfillment_score')
        valid='fulfillment_score' in value and (f is None or numeric(f))
        status='invalid' if not valid else 'unknown' if f is None else {'yes':'pass','no':'fail','partial':'partial'}[bucket(rational(f))]
        return {**value,'fulfillment_score':f if valid else None,'status':status,
            'binary_status':'unknown' if not valid or f is None else 'pass' if f==1 else 'fail',
            'execution_ref':ref,'completion_tokens':int(job['response'].get('completionTokens',1024))}


class FulfillmentExecutor(EndpointExecutor):
    aggregate=staticmethod(aggregate_trace)
    def __init__(self,checker,**kw):
        CountingExecutor.__init__(self,checker,validator=validate,observation_states=('pass','fail','partial','unknown'),
            observation_fields=('fulfillment_score','binary_status'),**kw)
    def execute(self,p,evidence,**kw):
        base=CountingExecutor.execute(self,p,evidence,**kw)
        for o,t in zip(base['observations'],base['transitions']):
            if o['event']=='transport_failure':
                path=self.checker.calls.directory/'jobs'/f"{o['execution_ref']}.json"
                job=json.loads(path.read_text()) if path.exists() else {}
                if job.get('outcome')!='transport_error':o['event']=t['event']='interrupted_attempt'
        return aggregate_trace(p,base['observations'],base['transitions'])
