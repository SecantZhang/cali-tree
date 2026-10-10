"""Independent required-condition checks with a deterministic all/some/none score."""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import CallFailure
from critical.core.decision.compiler import TEXT, array, enum, object_schema, media_inputs
from critical.core.decision.models import Requirement, Outcome
from critical.core.optimization.program.models import AppliedProgramEdit

VERSION='decision-leaf-v5'
PROTOCOL='typed-counting-v1'
AGGREGATION='required-condition-all-some-none-count-v1'
TEMPLATES=Path(__file__).parents[1]/'prompts/templates/typed_counting_v1'


def template(name):return (TEMPLATES/(name+'.txt')).read_text()


@dataclass(frozen=True)
class Decision:
    id: str
    requirement_id: str
    question: str
    criteria: str
    binding: str
    role: str = 'decision'


@dataclass(frozen=True)
class CountingProgram:
    instruction: str
    rubric: str
    requirements: tuple[Requirement,...]
    outcomes: tuple[Outcome,...]
    nodes: tuple[Decision,...]
    checker_template: str
    version: str = VERSION
    mode: str = 'flat'
    aggregation: str = AGGREGATION

    def to_dict(self):return json.loads(json.dumps(asdict(self)))
    @property
    def ref(self):validate(self);return digest(self.to_dict())
    @classmethod
    def from_dict(cls,row):
        if row.get('version')!=VERSION:raise ValueError('Explicit counting version mismatch')
        return validate(cls(**{**row,'requirements':tuple(Requirement(**r) for r in row['requirements']),
            'outcomes':tuple(Outcome(**{**o,'requirement_ids':tuple(o['requirement_ids'])}) for o in row['outcomes']),
            'nodes':tuple(Decision(**n) for n in row['nodes'])}))


def validate(p,original=None,*,expected_version=VERSION):
    if (p.version,p.mode,p.aggregation)!=(expected_version,'flat',AGGREGATION):raise ValueError('Unsupported counting contract; legacy evidence programs cannot be reinterpreted')
    if not all(isinstance(v,str) and v.strip() for v in (p.instruction,p.rubric,p.checker_template)):
        raise ValueError('Missing original instruction, rubric or frozen template')
    if not p.requirements or not p.outcomes or not 1<=len(p.nodes)<=4:raise ValueError('Need covered requirements and one to four independent decisions')
    for group in (p.requirements,p.outcomes,p.nodes):
        if len({v.id for v in group})!=len(group) or any(not isinstance(v.id,str) or not v.id.strip() for v in group):raise ValueError('Duplicate/empty identity')
    reqs={r.id for r in p.requirements}
    for r in p.requirements:
        if not r.text.strip() or not r.source_phrase.strip() or r.source_phrase not in p.instruction:raise ValueError('Invalid requirement provenance')
    for n in p.nodes:
        if n.role!='decision' or n.requirement_id not in reqs or not all(isinstance(v,str) and v.strip() for v in (n.question,n.criteria,n.binding)):
            raise ValueError('Only independent required-condition decisions can earn counted votes')
    if {n.requirement_id for n in p.nodes}!=reqs:raise ValueError('Removal leaves an original requirement uncovered')
    covered=set()
    for o in p.outcomes:
        if not o.requirement_ids or not set(o.requirement_ids)<=reqs or o.applicability not in ('applicable','not_applicable','unknown'):
            raise ValueError('Invalid original outcome mapping/applicability')
        covered.update(o.requirement_ids)
    if covered!=reqs:raise ValueError('Original outcome ledger is incomplete')
    if len({' '.join(n.question.lower().split()) for n in p.nodes})!=len(p.nodes):raise ValueError('Duplicate decision question')
    if original is not None and (p.instruction,p.rubric,p.requirements,p.outcomes)!=(original.instruction,original.rubric,original.requirements,original.outcomes):
        raise ValueError('Original instruction, rubric, requirements and requested bindings stay frozen')
    return p


def export_program(p):return {'program_ref':p.ref,'program':p.to_dict()}
def restore_program(row):
    p=CountingProgram.from_dict(row['program'])
    if p.ref!=row['program_ref']:raise ValueError('Program hash mismatch')
    return p


def count_states(states):
    """Unknowns, failures and an empty set remain unresolved; no model adjudication."""
    if not states or any(v not in ('pass','fail') for v in states):return 'unknown'
    passed=states.count('pass')
    return 'complete' if passed==len(states) else 'absent' if passed==0 else 'partial'


DECISION_SCHEMA=object_schema({k:TEXT for k in ('id','requirement_id','question','criteria','binding')})
SPEC_SCHEMA=object_schema({k:v for k,v in DECISION_SCHEMA['properties'].items() if k!='id'})
COMPILE_SCHEMA=object_schema({'decisions':{**array(SPEC_SCHEMA),'minItems':1,'maxItems':4}})
ACTION_SCHEMA=object_schema({'operation':enum(('add','remove','revise','split')),'target_id':TEXT,
    'decisions':{**array(DECISION_SCHEMA),'maxItems':4}})
TX_SCHEMA=object_schema({'version':enum((PROTOCOL,)),'reason':TEXT,'actions':{**array(ACTION_SCHEMA),'minItems':1,'maxItems':4}})
PROPOSAL_SCHEMA=object_schema({'transactions':{**array(TX_SCHEMA),'maxItems':2}})
OBS_SCHEMA=object_schema({'status':enum(('pass','fail','unknown')),'evidence':TEXT,'confidence':{'type':['number','null']}})


class CountingCompiler:
    def __init__(self,calls,original):self.calls,self.original=calls,original
    def compile(self,instruction,rubric,*,slot):
        if (instruction,rubric)!=(self.original.instruction,self.original.rubric):raise ValueError('Original instruction/rubric changed')
        value,ref=self.calls.call('compile_counting',{'instruction':instruction,'rubric':rubric,
            'requirements':[asdict(r) for r in self.original.requirements],'outcomes':[asdict(o) for o in self.original.outcomes],
            'max_decisions':4,'protocol':PROTOCOL,'aggregation':AGGREGATION},COMPILE_SCHEMA,
            template=template('compile'),slot=slot,max_tokens=2048)
        specs=value.get('decisions')
        if not isinstance(specs,list) or not 1<=len(specs)<=4:raise ValueError('Need one to four independent specifications')
        nodes=[]
        for i,s in enumerate(specs,1):
            if set(s)!=set(SPEC_SCHEMA['properties']):raise ValueError('Compiler may not supply roles, dependencies or activation')
            nodes.append(Decision(f'd{i}',**s))
        p=validate(CountingProgram(instruction,rubric,self.original.requirements,self.original.outcomes,tuple(nodes),template('check')),self.original)
        save_json(self.calls.directory/'constructions'/f'{ref}.json',{'protocol':PROTOCOL,'specification':value,'program':export_program(p),
            'semantic_audit':{'status':'disabled','performed':False}})
        return p


def apply_transaction(parent,tx):
    validate(parent)
    if set(tx)!=set(TX_SCHEMA['properties']) or tx['version']!=PROTOCOL or not isinstance(tx['reason'],str) or not tx['reason'].strip():raise ValueError('Invalid counting transaction')
    if not isinstance(tx['actions'],list) or not 1<=len(tx['actions'])<=4:raise ValueError('Need one to four atomic actions')
    nodes=list(parent.nodes)
    for a in tx['actions']:
        if set(a)!=set(ACTION_SCHEMA['properties']) or a['operation'] not in ('add','remove','revise','split') or not isinstance(a['target_id'],str) or not isinstance(a['decisions'],list):
            raise ValueError('Malformed counting action')
        replacements=[]
        for n in a['decisions']:
            if set(n)!=set(DECISION_SCHEMA['properties']):raise ValueError('Cannot supply roles, dependencies or activation')
            replacements.append(Decision(**n))
        op=a['operation'];ids=[n.id for n in nodes]
        if op=='add':
            if a['target_id'] or len(replacements)!=1 or replacements[0].id in ids:raise ValueError('Addition needs one unique decision and no target')
            nodes.extend(replacements)
        else:
            if a['target_id'] not in ids:raise ValueError('Target decision not found')
            pos=ids.index(a['target_id'])
            if op=='remove':
                if replacements:raise ValueError('Removal cannot introduce other semantics')
                nodes.pop(pos)
            elif op=='revise':
                if len(replacements)!=1 or replacements[0].id!=a['target_id']:raise ValueError('Revision preserves the target ID')
                nodes[pos]=replacements[0]
            else:
                if not 2<=len(replacements)<=4:raise ValueError('Split needs two to four mapped replacement decisions')
                nodes[pos:pos+1]=replacements
    child=validate(replace(parent,nodes=tuple(nodes)),parent)
    return AppliedProgramEdit(child,{'protocol':PROTOCOL,'parent_ref':parent.ref,'child_ref':child.ref,'typed_actions':tx['actions'],
        'expanded_decisions':[asdict(n) for n in nodes], 'semantic_audit':'disabled',
        'provenance':[{'decision_id':n.id,'requirement_id':n.requirement_id,
                      'source_phrase':next(r.source_phrase for r in parent.requirements if r.id==n.requirement_id)} for n in nodes]})


class CountingChecker:
    def __init__(self,calls):
        self.calls=calls;self.identity={'provider':calls.identity,'checker':'independent-counting-v1','scope':getattr(calls,'case_id',None)}
    def check(self,p,n,evidence,*,slot,final=False):
        value,ref=self.calls.call('check_counting',{'instruction':p.instruction,'decision':asdict(n),
            'requirement':asdict(next(r for r in p.requirements if r.id==n.requirement_id))},OBS_SCHEMA,
            template=p.checker_template,media=media_inputs(evidence),slot=slot,final=final,max_tokens=1024)
        job=json.loads((self.calls.directory/'jobs'/f'{ref}.json').read_text())
        return {**value,'execution_ref':ref,'completion_tokens':int(job['response'].get('completionTokens',1024))}


class CountingExecutor:
    def __init__(self,checker,*,checkpoint=None,max_checks=4,validator=validate):
        if max_checks!=4:raise ValueError('Counting execution cap is four')
        self.checker,self.checkpoint,self.max_checks=checker,checkpoint,max_checks;self.cache={};self.validate=validator
    def execute(self,p,evidence,*,repeat='0',final=False):
        self.validate(p);evidence={k:evidence[k] for k in ('source_image','edited_image')}
        images={k:sha256(Path(v).read_bytes()).hexdigest() for k,v in evidence.items()}
        observations=[];transitions=[]
        applicable_req={rid for o in p.outcomes if o.applicability=='applicable' for rid in o.requirement_ids}
        unknown_req={rid for o in p.outcomes if o.applicability=='unknown' for rid in o.requirement_ids}
        for n in p.nodes:
            applicable=n.requirement_id in applicable_req and n.requirement_id not in unknown_req
            obs={'check_id':n.id,'status':'unknown','valid':False,'eligible':applicable,'queried':False,'confidence':None,
                'evidence':'Declared applicability does not establish an applicable decision' if not applicable else '',
                'event':'applicability_skip' if not applicable else '', 'completion_tokens':0,'execution_ref':'','failure':None,'dependencies':[]}
            if applicable:
                key=digest([p.ref,self.checker.identity,images,n.id,str(repeat),final])
                if key in self.cache:obs=self.cache[key]
                elif self.checkpoint is not None and self.checkpoint.has('count-observe:'+key):obs=self.checkpoint.get('count-observe:'+key)
                else:
                    obs.update(queried=True,execution_ref=key)
                    try:
                        row=self.checker.check(p,n,evidence,slot=f'{repeat}/{n.id}',final=final)
                        obs.update(execution_ref=row.get('execution_ref',key),completion_tokens=int(row.get('completion_tokens',0)))
                        if row.get('status') not in ('pass','fail','unknown') or not isinstance(row.get('evidence'),str) or not row['evidence'].strip():raise ValueError('Invalid independent observation')
                        confidence=row.get('confidence')
                        if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:confidence=None
                        obs.update(status=row['status'],valid=True,evidence=row['evidence'],confidence=confidence,
                            event='valid_uncertainty' if row['status']=='unknown' else 'observed')
                    except (CallFailure,ValueError,TypeError,KeyError) as exc:
                        obs.update(event='invalid_response',evidence=str(exc),failure=type(exc).__name__)
                        if isinstance(exc,CallFailure):
                            obs.update(event='transport_failure',completion_tokens=1024)
                            keys=re.findall(r'\b[a-f0-9]{64}\b',str(exc));path=self.checker.calls.directory/'jobs'/f'{keys[0]}.json' if keys else None
                            job=json.loads(path.read_text()) if path and path.exists() else {}
                            if job.get('outcome')=='invalid':obs['event']='invalid_response'
                            if job.get('response'):obs['completion_tokens']=int(job['response'].get('completionTokens',1024))
                            if job.get('execution_ref'):obs['execution_ref']=job['execution_ref']
                    self.cache[key]=obs
                    if self.checkpoint is not None:self.checkpoint.put('count-observe:'+key,obs)
            observations.append(obs);transitions.append({'node':n.id,'parent':'','activation':None,'eligible':applicable,'state':obs['status'],'event':obs['event']})
        return aggregate_trace(p,observations,transitions)


def aggregate_trace(p,observations,transitions):
        """Recompute the fixed score from exact observations, without model adjudication."""
        applicable_req={rid for o in p.outcomes if o.applicability=='applicable' for rid in o.requirement_ids}
        unknown_req={rid for o in p.outcomes if o.applicability=='unknown' for rid in o.requirement_ids}
        states=[o['status'] for o in observations if o['eligible']]
        state='unknown' if unknown_req else count_states(states)
        requirements={}
        for r in p.requirements:
            rows=[o for n,o in zip(p.nodes,observations) if n.requirement_id==r.id]
            requirements[r.id]='unknown' if r.id in unknown_req else count_states([o['status'] for o in rows if o['eligible']]) if r.id in applicable_req else 'not_applicable'
        outcomes={o.id:{'status':'unknown' if o.applicability!='applicable' else (
            'unknown' if any(requirements[rid]=='unknown' for rid in o.requirement_ids) else
            'complete' if all(requirements[rid]=='complete' for rid in o.requirement_ids) else
            'absent' if all(requirements[rid]=='absent' for rid in o.requirement_ids) else 'partial'),
            'applicability':o.applicability,'source':'deterministic_count','reason':'Required-condition all/some/none count'} for o in p.outcomes}
        return {'program_ref':p.ref,'label':{'complete':'yes','partial':'partial','absent':'no'}.get(state),'resolved':state!='unknown',
            'outcomes':outcomes,'requirements':requirements,'observations':observations,'transitions':transitions,
            'counting':{'passed':states.count('pass'),'failed':states.count('fail'),'unknown':states.count('unknown'),
                        'total':len(states),'semantic_audit':'disabled','model_readout':False}}
