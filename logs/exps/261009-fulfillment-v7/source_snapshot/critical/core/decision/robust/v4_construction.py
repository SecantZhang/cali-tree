"""Label-blind compilation and atomic, deterministic v2 evidence edits."""
from dataclasses import asdict, replace
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.decision.compiler import TEXT, array, enum, object_schema
from critical.core.decision.robust.compiler import checked_audit
from critical.core.optimization.program.models import AppliedProgramEdit
from .models import GATES
from .v4_models import Activation, EvidenceNode, EvidenceProgram, PROTOCOL, export_program, validate

TEMPLATES = Path(__file__).parents[2]/'prompts/templates/typed_evidence_v2'


def template(name):
    return (TEMPLATES/(name+'.txt')).read_text()


INDEX = {'type':'integer'}
SUPPORT_SCHEMA = object_schema({**{k:TEXT for k in ('requirement_id','question','criteria','binding')},
    'evidence_from':array(INDEX),'required_evidence_from':array(INDEX),
    'activation_source':INDEX,'activation_states':array(enum(GATES))})
COMPILE_SCHEMA = object_schema({'supports':{**array(SUPPORT_SCHEMA),'minItems':2,'maxItems':2},
    'fulfillment_criteria':TEXT,'fulfillment_required':array(INDEX)})
OPERATIONS = ('insert_support','replace_support','revise_support','revise_readout','remove_support',
              'reorder_supports','configure_activation')
ACTION_SCHEMA = object_schema({'operation':enum(OPERATIONS),
    **{k:TEXT for k in ('after','before','new_check_id','target_id','requirement_id','question','criteria','binding','readout_criteria','activation_check')},
    'evidence_from':array(TEXT),'required_evidence_from':array(TEXT),'activation_states':array(enum(GATES)),
    'support_order':array(TEXT),'readout_required':array(TEXT)})
TRANSACTION_SCHEMA = object_schema({'version':enum((PROTOCOL,)),'reason':TEXT,
    'actions':{**array(ACTION_SCHEMA),'minItems':1,'maxItems':4}})
PROPOSAL_SCHEMA = object_schema({'transactions':{**array(TRANSACTION_SCHEMA),'maxItems':2}})
AUDIT_SCHEMA = object_schema({'accepted':{'type':'boolean'},'reason':TEXT,'source_clause':TEXT,'counterexample':TEXT})


def rebuild(original, supports, readout):
    nodes=[]
    for n in supports:
        earlier=[v.id for v in nodes]
        if not set(n.dependencies)<=set(earlier):raise ValueError(f'{n.id} has missing or non-earlier context: {n.dependencies}')
        nodes.append(replace(n,parent=earlier[-1] if earlier else '',active_on=GATES if earlier else (),
            dependencies=tuple(i for i in earlier if i in n.dependencies)))
    nodes.append(replace(readout,parent=nodes[-1].id if nodes else '',active_on=GATES if nodes else (),
                         dependencies=tuple(n.id for n in nodes)))
    p=EvidenceProgram(original.instruction,original.rubric,original.requirements,original.outcomes,tuple(nodes),template('check'))
    return validate(p,original)


def construct(original, spec):
    if set(spec)!=set(COMPILE_SCHEMA['properties']) or not isinstance(spec['supports'],list) or len(spec['supports'])!=2:
        raise ValueError('Compilation requires exactly two ordered support specifications')
    nodes=[]
    for i,s in enumerate(spec['supports'],1):
        if set(s)!=set(SUPPORT_SCHEMA['properties']):raise ValueError('Compiler cannot supply raw graph fields')
        for key in ('evidence_from','required_evidence_from'):
            refs=s[key]
            if not isinstance(refs,list) or len(set(refs))!=len(refs) or any(type(v) is not int or not 1<=v<i for v in refs):
                raise ValueError('Compiler context and prerequisites may reference only earlier indices')
        a=s['activation_source']
        if type(a) is not int or not 0<=a<i or (not a and s['activation_states']):raise ValueError('Invalid compilation activation source')
        nodes.append(EvidenceNode(f's{i}','support','','',(),tuple(f's{v}' for v in sorted(s['evidence_from'])),
            s['question'],s['criteria'],s['binding'],s['requirement_id'],tuple(f's{v}' for v in s['required_evidence_from']),
            Activation(f's{a}',tuple(s['activation_states'])) if a else None))
    req=spec['fulfillment_required']
    if not isinstance(req,list) or any(type(i) is not int or not 1<=i<=len(nodes) for i in req):raise ValueError('Invalid fulfillment prerequisite')
    o=original.outcomes[0]
    readout=EvidenceNode('fulfillment','requested',o.id,'',(),(),o.description,spec['fulfillment_criteria'],
        'Target: '+o.target+'. Reference: '+o.reference+'.',required_dependencies=tuple(f's{i}' for i in req))
    return rebuild(original,nodes,readout)


class EvidenceCompiler:
    def __init__(self,calls,original):
        self.calls,self.original=calls,original

    def compile(self,instruction,rubric,*,slot):
        if (instruction,rubric)!=(self.original.instruction,self.original.rubric):raise ValueError('Original instruction/rubric changed')
        spec,ref=self.calls.call('compile_v4',{'instruction':instruction,'rubric':rubric,
            'requirements':[asdict(r) for r in self.original.requirements], 'outcomes':[asdict(o) for o in self.original.outcomes],
            'protocol':PROTOCOL,'max_checks':4},COMPILE_SCHEMA,template=template('compile'),slot=slot,max_tokens=2048)
        p=construct(self.original,spec)
        save_json(self.calls.directory/'constructions'/f'{ref}.json',{'specification':spec,'program':export_program(p)})
        return p

    def audit(self,program,*,slot):
        validate(program,self.original)
        value,ref=self.calls.call('audit_v4',{'instruction':program.instruction,'rubric':program.rubric,
            'original_requirements':[asdict(r) for r in program.requirements], 'program':program.to_dict()},
            AUDIT_SCHEMA,template=template('audit'),slot=slot,max_tokens=2048)
        audit=checked_audit(value,ref)
        if not audit['accepted'] and (not isinstance(value.get('source_clause'),str) or not value['source_clause'].strip() or
                value['source_clause'] not in program.instruction+'\n'+program.rubric or
                not isinstance(value.get('counterexample'),str) or not value['counterexample'].strip()):
            raise ValueError('Audit rejection needs an exact original clause and concrete counterexample')
        return audit


def apply_transaction(parent,tx):
    validate(parent)
    if set(tx)!=set(TRANSACTION_SCHEMA['properties']) or tx['version']!=PROTOCOL or not isinstance(tx['reason'],str) or not tx['reason'].strip():
        raise ValueError('Invalid typed-evidence-v2 transaction')
    actions=tx['actions']
    if not isinstance(actions,list) or not 1<=len(actions)<=4:raise ValueError('Need one to four atomic actions')
    supports=list(parent.nodes[:-1]);readout=parent.nodes[-1]
    for a in actions:
        if set(a)!=set(ACTION_SCHEMA['properties']):raise ValueError('Actions cannot supply raw executable graph fields')
        for k,v in a.items():
            if k.endswith('_from') or k in ('activation_states','support_order','readout_required'):
                if not isinstance(v,list) or any(not isinstance(i,str) for i in v):raise ValueError('Invalid action references')
            elif not isinstance(v,str):raise ValueError('Invalid action text')
        op=a['operation'];ids=[n.id for n in supports]+[readout.id]
        if op not in OPERATIONS:raise ValueError('Unsupported action')
        allowed={'operation'}
        if op in ('insert_support','replace_support','revise_support'):
            allowed|={'requirement_id','question','criteria','binding','evidence_from','required_evidence_from','activation_check','activation_states','readout_criteria','readout_required'}
            if not all(a[k].strip() for k in ('requirement_id','question','criteria','binding')):raise ValueError('Missing evidence semantics')
            if op=='insert_support':
                allowed|={'after','before','new_check_id'}
                after=a['after'];before=a['before'];nid=a['new_check_id']
                if after not in ids[:-1] or ids[ids.index(after)+1]!=before:raise ValueError('Specified insertion edge does not exist')
                if not nid.strip() or nid in ids:raise ValueError('New check ID must be unique')
                if not a['readout_criteria'].strip():raise ValueError('Insertion needs explicit readout criteria')
                position=ids.index(after)+1
            else:
                allowed.add('target_id');nid=a['target_id']
                if nid not in ids[:-1]:raise ValueError('Support target not found')
                position=ids.index(nid)
            if not a['activation_check'] and a['activation_states']:raise ValueError('Activation states need a source')
            n=EvidenceNode(nid,'support','','',(),tuple(a['evidence_from']),a['question'],a['criteria'],a['binding'],
                a['requirement_id'],tuple(a['required_evidence_from']),Activation(a['activation_check'],tuple(a['activation_states'])) if a['activation_check'] else None)
            if op=='insert_support':supports.insert(position,n)
            else:supports[position]=n
        elif op=='revise_readout':
            allowed|={'target_id','criteria','readout_required'}
            if a['target_id']!=readout.id or not a['criteria'].strip():raise ValueError('Readout revision needs current ID and criteria')
            readout=replace(readout,criteria=a['criteria'],required_dependencies=tuple(a['readout_required']))
        elif op=='remove_support':
            allowed|={'target_id','readout_criteria','readout_required'}
            if a['target_id'] not in ids[:-1] or not a['readout_criteria'].strip():raise ValueError('Removal needs a support and revised readout')
            supports.pop(ids.index(a['target_id']))
        elif op=='reorder_supports':
            allowed.add('support_order')
            if len(a['support_order'])!=len(supports) or set(a['support_order'])!=set(ids[:-1]):raise ValueError('Reordering must list every surviving support exactly once')
            byid={n.id:n for n in supports};supports=[byid[i] for i in a['support_order']]
        elif op=='configure_activation':
            allowed|={'target_id','activation_check','activation_states','readout_criteria','readout_required'}
            if a['target_id'] not in ids[:-1] or not a['readout_criteria'].strip():raise ValueError('Routing needs a support and explicit readout interpretation')
            if not a['activation_check'] and a['activation_states']:raise ValueError('Activation states need a source')
            i=ids.index(a['target_id']);supports[i]=replace(supports[i],activation=Activation(a['activation_check'],tuple(a['activation_states'])) if a['activation_check'] else None)
        if any(v for k,v in a.items() if k not in allowed):raise ValueError(f'{op} changes fields outside its typed contract')
        if a['readout_criteria']:
            readout=replace(readout,criteria=a['readout_criteria'],required_dependencies=tuple(a['readout_required']))
    child=rebuild(parent,supports,readout)
    return AppliedProgramEdit(child,{'protocol':PROTOCOL,'typed_actions':actions,'parent_ref':parent.ref,'child_ref':child.ref,
        'expanded_nodes':[asdict(n) for n in child.nodes],
        'provenance':[{'node_id':n.id,'requirement_id':n.requirement_id,
            'source_phrase':next(r.source_phrase for r in parent.requirements if r.id==n.requirement_id)} for n in child.nodes if n.role=='support']})
