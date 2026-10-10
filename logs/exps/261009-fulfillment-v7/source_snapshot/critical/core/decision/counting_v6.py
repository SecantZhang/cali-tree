"""Grounded endpoint specifications and bounded, outcome-blind transport recovery."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import re

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import CallFailure
from critical.core.decision.compiler import TEXT, array, enum, object_schema
from critical.core.decision.models import Requirement, Outcome
from critical.core.optimization.program.models import AppliedProgramEdit
from .counting import (Decision, CountingProgram, CountingChecker, CountingExecutor,
                      validate as validate_legacy, aggregate_trace, AGGREGATION)

VERSION='decision-leaf-v6'
PROTOCOL='typed-counting-v2'
TEMPLATES=Path(__file__).parents[1]/'prompts/templates/typed_counting_v2'


def template(name):return (TEMPLATES/(name+'.txt')).read_text()


@dataclass(frozen=True)
class EndpointDecision(Decision):
    source_quote: str = ''
    aspect: str = ''
    endpoint: str = ''
    necessity: str = ''


@dataclass(frozen=True)
class EndpointProgram(CountingProgram):
    version: str = VERSION
    decomposition_reason: str = ''

    @property
    def ref(self):validate(self);return digest(self.to_dict())

    @classmethod
    def from_dict(cls,row):
        return validate(cls(**{**row,'requirements':tuple(Requirement(**r) for r in row['requirements']),
            'outcomes':tuple(Outcome(**{**o,'requirement_ids':tuple(o['requirement_ids'])}) for o in row['outcomes']),
            'nodes':tuple(EndpointDecision(**n) for n in row['nodes'])}))


def validate(p,original=None):
    validate_legacy(p,original,expected_version=VERSION)
    if not isinstance(p.decomposition_reason,str) or not p.decomposition_reason.strip():
        raise ValueError('Explain the decomposition; a single endpoint must explicitly explain irreducibility')
    aspects=set()
    for n in p.nodes:
        if not isinstance(n,EndpointDecision) or not all(isinstance(v,str) and v.strip() for v in
                (n.source_quote,n.aspect,n.endpoint,n.necessity)):
            raise ValueError('Endpoint needs an exact source quote, distinct aspect, endpoint and necessity explanation')
        req=next(r for r in p.requirements if r.id==n.requirement_id)
        if n.source_quote not in req.source_phrase and n.source_quote not in p.rubric:
            raise ValueError('Endpoint source_quote must occur in its original requirement or rubric')
        # Narrow explicit protocol violations, not a claim of semantic verification.
        if re.search(r'\b(progress|attempt|partially|partial)\b',n.question+' '+n.endpoint,re.I):
            raise ValueError('Count endpoint satisfaction; progress/attempt questions cannot earn required-condition votes')
        aspect=(n.requirement_id,' '.join(n.aspect.casefold().split()))
        if aspect in aspects:raise ValueError('Duplicate aspect; splitting must expose distinct required dimensions')
        aspects.add(aspect)
    return p


def export_program(p):return {'program_ref':p.ref,'program':p.to_dict()}


def restore_program(row):
    p=EndpointProgram.from_dict(row['program'])
    if p.ref!=row['program_ref']:raise ValueError('Endpoint program hash mismatch')
    return p


FIELDS=('requirement_id','question','criteria','binding','source_quote','aspect','endpoint','necessity')
SPEC_SCHEMA=object_schema({k:TEXT for k in FIELDS})
DECISION_SCHEMA=object_schema({'id':TEXT,**SPEC_SCHEMA['properties']})
COMPILE_SCHEMA=object_schema({'decisions':{**array(SPEC_SCHEMA),'minItems':1,'maxItems':4},'decomposition_reason':TEXT})
ACTION_SCHEMA=object_schema({'operation':enum(('add','remove','revise','split')),'target_id':TEXT,
    'decisions':{**array(DECISION_SCHEMA),'maxItems':4}})
EXPECTATION_SCHEMA=object_schema({'decision_id':TEXT,'status':enum(('pass','fail','unknown')),'evidence_reason':TEXT})
TX_SCHEMA=object_schema({'version':enum((PROTOCOL,)),'reason':TEXT,
    'actions':{**array(ACTION_SCHEMA),'minItems':1,'maxItems':4},
    'predicted_states':{**array(EXPECTATION_SCHEMA),'minItems':1,'maxItems':4}})
PROPOSAL_SCHEMA=object_schema({'transactions':{**array(TX_SCHEMA),'maxItems':2}})


class EndpointCompiler:
    def __init__(self,calls,original):self.calls,self.original=calls,original
    def compile(self,instruction,rubric,*,slot):
        if (instruction,rubric)!=(self.original.instruction,self.original.rubric):raise ValueError('Original instruction/rubric changed')
        value,ref=self.calls.call('compile_counting',{'instruction':instruction,'rubric':rubric,
            'requirements':[asdict(r) for r in self.original.requirements],'outcomes':[asdict(o) for o in self.original.outcomes],
            'preferred_decisions':2,'max_decisions':4,'protocol':PROTOCOL,'aggregation':AGGREGATION},COMPILE_SCHEMA,
            template=template('compile'),slot=slot,max_tokens=2048)
        if set(value)!=set(COMPILE_SCHEMA['properties']) or not isinstance(value['decisions'],list):raise ValueError('Invalid endpoint compilation')
        nodes=[]
        for i,spec in enumerate(value['decisions'],1):
            if set(spec)!=set(FIELDS):raise ValueError('Invalid endpoint specification')
            nodes.append(EndpointDecision(id=f'd{i}',**spec))
        p=validate(EndpointProgram(instruction,rubric,self.original.requirements,self.original.outcomes,
            tuple(nodes),template('check'),decomposition_reason=value['decomposition_reason']),self.original)
        save_json(self.calls.directory/'constructions'/f'{ref}.json',{'protocol':PROTOCOL,'specification':value,
            'program':export_program(p),'partial_representable':len(nodes)>1,'semantic_audit':{'status':'disabled','performed':False}})
        return p


def apply_transaction(parent,tx):
    validate(parent)
    if set(tx)!=set(TX_SCHEMA['properties']) or tx['version']!=PROTOCOL or not isinstance(tx['reason'],str) or not tx['reason'].strip():raise ValueError('Invalid endpoint transaction')
    if not isinstance(tx['actions'],list) or not 1<=len(tx['actions'])<=4:raise ValueError('Need one to four atomic actions')
    nodes=list(parent.nodes);changed=set()
    for a in tx['actions']:
        if set(a)!=set(ACTION_SCHEMA['properties']) or a['operation'] not in ('add','remove','revise','split') or not isinstance(a['decisions'],list):raise ValueError('Malformed endpoint action')
        replacements=[]
        for spec in a['decisions']:
            if set(spec)!=set(DECISION_SCHEMA['properties']):raise ValueError('Endpoint fields must be explicit; no graph or labels')
            replacements.append(EndpointDecision(**spec))
        op=a['operation'];ids=[n.id for n in nodes];changed.update(n.id for n in replacements)
        if op=='add':
            if a['target_id'] or len(replacements)!=1 or replacements[0].id in ids:raise ValueError('Addition needs a unique decision and no target')
            nodes.extend(replacements)
        else:
            if a['target_id'] not in ids:raise ValueError('Target decision not found')
            pos=ids.index(a['target_id'])
            if op=='remove':
                if replacements:raise ValueError('Removal cannot introduce other semantics')
                nodes.pop(pos)
            elif op=='revise':
                if len(replacements)!=1 or replacements[0].id!=a['target_id']:raise ValueError('Revision preserves its target ID')
                nodes[pos]=replacements[0]
            else:
                if not 2<=len(replacements)<=4:raise ValueError('Split needs two to four endpoint replacements')
                nodes[pos:pos+1]=replacements
    child=validate(replace(parent,nodes=tuple(nodes)),parent)
    predicted=tx['predicted_states']
    if not isinstance(predicted,list) or not 1<=len(predicted)<=4:raise ValueError('Predict evidence impact of each repair')
    expected_ids=[]
    for e in predicted:
        if set(e)!=set(EXPECTATION_SCHEMA['properties']) or e['decision_id'] not in {n.id for n in nodes} or e['status'] not in ('pass','fail','unknown') or not isinstance(e['evidence_reason'],str) or not e['evidence_reason'].strip():raise ValueError('Invalid evidence prediction')
        expected_ids.append(e['decision_id'])
    if len(set(expected_ids))!=len(expected_ids) or not (changed & {n.id for n in nodes})<=set(expected_ids):raise ValueError('Predict every changed endpoint exactly once')
    return AppliedProgramEdit(child,{'protocol':PROTOCOL,'parent_ref':parent.ref,'child_ref':child.ref,
        'typed_actions':tx['actions'],'predicted_states':predicted,'expanded_decisions':[asdict(n) for n in nodes],
        'semantic_audit':'disabled','provenance':[{'decision_id':n.id,'requirement_id':n.requirement_id,'source_quote':n.source_quote} for n in nodes]})


class EndpointChecker(CountingChecker):
    def __init__(self,calls):
        super().__init__(calls);self.identity['checker']='independent-endpoints-v2'


class EndpointExecutor(CountingExecutor):
    aggregate=staticmethod(aggregate_trace)
    def __init__(self,checker,**kw):super().__init__(checker,validator=validate,**kw)

    def execute(self,p,evidence,**kw):
        trace=super().execute(p,evidence,**kw)
        for o,t in zip(trace['observations'],trace['transitions']):
            if o['event']=='transport_failure':
                path=self.checker.calls.directory/'jobs'/f"{o['execution_ref']}.json"
                job=json.loads(path.read_text()) if path.exists() else {}
                if job.get('outcome')!='transport_error':
                    o['event']=t['event']='interrupted_attempt'
        trace['counting']['partial_representable']=trace['counting']['total']>1
        return trace

    def recover_transport(self,p,evidence,trace,index,*,repeat,final):
        """A new single-attempt slot for ONE failed check; all other observations stay exact."""
        self.validate(p)
        if trace['program_ref']!=p.ref:raise ValueError('Recovery program mismatch')
        original=trace['observations'][index]
        if original['event']!='transport_failure':raise ValueError('Only transport failures qualify; never replace valid wrong/uncertain answers')
        n=p.nodes[index]
        if original['check_id']!=n.id:raise ValueError('Recovery check mismatch')
        recovered=deepcopy(original);recovered.update(execution_ref='',failure=None,completion_tokens=0)
        try:
            row=self.checker.check(p,n,evidence,slot=repeat+'/'+n.id,final=final)
            recovered.update(execution_ref=row['execution_ref'],completion_tokens=row['completion_tokens'])
            if row.get('status') not in self.observation_states or not isinstance(row.get('evidence'),str) or not row['evidence'].strip():raise ValueError('Invalid recovery observation')
            c=row.get('confidence');c=c if type(c) in (int,float) and math.isfinite(c) and 0<=c<=1 else None
            recovered.update(status=row['status'],valid=True,evidence=row['evidence'],confidence=c,
                event='valid_uncertainty' if row['status']=='unknown' else 'observed')
            recovered.update({k:row.get(k) for k in self.observation_fields})
        except CallFailure as exc:
            keys=re.findall(r'\b[a-f0-9]{64}\b',str(exc));path=self.checker.calls.directory/'jobs'/f'{keys[0]}.json' if keys else None
            job=json.loads(path.read_text()) if path and path.exists() else {}
            recovered.update(status='unknown',valid=False,confidence=None,evidence=str(exc),failure='CallFailure',
                event='invalid_response' if job.get('outcome')=='invalid' else 'transport_failure',
                execution_ref=job.get('execution_ref',''),completion_tokens=int((job.get('response') or {}).get('completionTokens',1024)))
        except (ValueError,TypeError,KeyError) as exc:
            recovered.update(status='unknown',valid=False,confidence=None,evidence=str(exc),failure=type(exc).__name__,event='invalid_response')
        recovered['attempts']=[deepcopy(original),deepcopy(recovered)]
        recovered['completion_tokens']+=original['completion_tokens']
        observations=deepcopy(trace['observations']);observations[index]=recovered
        transitions=deepcopy(trace['transitions']);transitions[index].update(state=recovered['status'],event=recovered['event'])
        result=self.aggregate(p,observations,transitions)
        if 'counting' in result:result['counting']['partial_representable']=result['counting']['total']>1
        return result
