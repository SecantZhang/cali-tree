"""Atomic semantic actions with code-owned execution topology."""
from dataclasses import asdict, replace

from critical.core.decision.compiler import TEXT, array, enum, object_schema, media_inputs
from critical.core.decision.robust.models import Node, GATES
from critical.core.decision.robust.refinement import validate_refinement
from critical.core.decision.robust.construction import PROTOCOL, TypedEvidenceCompiler, template
from critical.core.decision.robust.errors import GraphValidationError
from critical.core.optimization.program.models import AppliedProgramEdit
from .proposer import StructuralProposer

OPERATIONS = ('insert_support','replace_support','revise_support','revise_readout','remove_support')
ACTION_SCHEMA = object_schema({'operation':enum(OPERATIONS),
    **{k:TEXT for k in ('after','before','new_check_id','target_id','requirement_id','question','criteria','binding','readout_criteria')},
    'evidence_from':array(TEXT)})
TRANSACTION_SCHEMA = object_schema({'version':enum((PROTOCOL,)),'reason':TEXT,'actions':array(ACTION_SCHEMA)})
PROPOSAL_SCHEMA = object_schema({'transactions':array(TRANSACTION_SCHEMA)})


def apply_typed_transaction(parent, transaction):
    validate_refinement(parent)
    if any(n.parent != (parent.nodes[i-1].id if i else '') or
           n.active_on != (GATES if i else ()) for i,n in enumerate(parent.nodes)):
        raise ValueError('Typed edits initially require an all-state evidence chain')
    if set(transaction) != {'version','reason','actions'} or transaction['version'] != PROTOCOL:
        raise ValueError('Unsupported typed transaction protocol')
    actions = transaction['actions']
    if not isinstance(transaction['reason'],str) or not transaction['reason'].strip() or not isinstance(actions,list) or not 1 <= len(actions) <= 4:
        raise ValueError('Need a diagnostic reason and one to four typed actions')
    supports = list(parent.nodes[:-1]);readout=parent.nodes[-1]
    reqs={r.id:r for r in parent.requirements};provenance=[]

    def semantic_node(action, nid, old=None):
        req=reqs.get(action['requirement_id'])
        if req is None or not all(action[k].strip() for k in ('question','criteria','binding')):
            raise ValueError('Support semantics need an original requirement and nonempty question/criteria/binding')
        refs=action['evidence_from']
        if len(set(refs)) != len(refs):raise ValueError('Duplicate evidence reference')
        provenance.append({'node_id':nid,'requirement_id':req.id,'source_phrase':req.source_phrase})
        return Node(nid,'support','',old.parent if old else '',old.active_on if old else (),
                    tuple(refs),action['question'],action['criteria'],action['binding'])

    for action in actions:
        if set(action) != set(ACTION_SCHEMA['properties']) or any(not isinstance(action[k],str) for k in action if k!='evidence_from') or not isinstance(action['evidence_from'],list) or any(not isinstance(i,str) for i in action['evidence_from']):
            raise ValueError('Typed actions cannot contain raw graph fields or malformed values')
        op=action['operation'];by_id={n.id:n for n in (*supports,readout)}
        if op not in OPERATIONS:raise ValueError('Unsupported typed operation')
        if op=='insert_support':
            after,before=action['after'],action['before'];nid=action['new_check_id']
            chain=[n.id for n in (*supports,readout)]
            if after not in chain[:-1] or before not in by_id or chain[chain.index(after)+1]!=before:
                raise GraphValidationError('edge_not_found',f'No existing edge {after} -> {before}',node_id=before,dependency_id=after)
            if action['target_id'] or not nid.strip() or nid in by_id:
                raise ValueError('Insertion needs a unique new support ID and no target_id')
            if not action['readout_criteria'].strip():raise ValueError('Insertion needs explicit readout criteria')
            supports.insert(chain.index(after)+1,semantic_node(action,nid))
            readout=replace(readout,criteria=action['readout_criteria'])
        elif op in ('replace_support','revise_support'):
            target=action['target_id'];old=by_id.get(target)
            if old is None or old.role!='support':raise ValueError('Revision target must be an existing support')
            if any(action[k] for k in ('after','before','new_check_id')):raise ValueError('Replacement preserves ID and position')
            supports[supports.index(old)]=semantic_node(action,target,old)
            if action['readout_criteria']:readout=replace(readout,criteria=action['readout_criteria'])
        elif op=='revise_readout':
            if action['target_id']!=readout.id or not action['criteria'].strip() or any(action[k] for k in ('after','before','new_check_id','requirement_id','question','binding','readout_criteria')) or action['evidence_from']:
                raise ValueError('Readout revision changes only the existing fulfillment criteria')
            readout=replace(readout,criteria=action['criteria'])
        elif op=='remove_support':
            target=by_id.get(action['target_id'])
            if target is None or target.role!='support' or not action['readout_criteria'].strip():
                raise ValueError('Removal needs an existing support and explicit readout criteria')
            if any(action[k] for k in ('after','before','new_check_id','requirement_id','question','criteria','binding')) or action['evidence_from']:
                raise ValueError('Removal cannot change other semantics implicitly')
            supports.remove(target);readout=replace(readout,criteria=action['readout_criteria'])
    # Rebuild every routing edge from the final ordered support list. Context
    # references remain explicit semantics: dangling/forward references fail.
    nodes=[]
    for i,n in enumerate(supports):
        earlier=[v.id for v in supports[:i]]
        if not set(n.dependencies)<=set(earlier):
            bad=next(d for d in n.dependencies if d not in earlier)
            exists=bad in {v.id for v in (*supports,readout)}
            raise GraphValidationError('dependency_not_ancestor' if exists else 'missing_dependency',
                f'{n.id} consumes {bad}, which is not an earlier ancestor' if exists else f'{n.id} consumes missing check {bad}',
                node_id=n.id,dependency_id=bad,relationship='non_ancestor' if exists else 'missing')
        nodes.append(replace(n,parent=earlier[-1] if earlier else '',active_on=GATES if earlier else (),
                             dependencies=tuple(d for d in earlier if d in n.dependencies)))
    nodes.append(replace(readout,parent=nodes[-1].id if nodes else '',active_on=GATES if nodes else (),
                         dependencies=tuple(n.id for n in nodes)))
    child=validate_refinement(replace(parent,nodes=tuple(nodes)),parent)
    old={n.id:n for n in parent.nodes};new={n.id:n for n in child.nodes}
    expanded={'reason':transaction['reason'],'edits':[{'operator':'subtree_replace',
        'remove_nodes':[nid for nid in old if nid not in new],
        'nodes':[asdict(n) for n in child.nodes if old.get(n.id)!=n],
        'remove_outcomes':[],'outcomes':[],'node_order':[n.id for n in child.nodes]}],'outcome_mapping':[]}
    return AppliedProgramEdit(child,{'protocol':PROTOCOL,'parent_ref':parent.ref,'child_ref':child.ref,
        'expanded_transaction':expanded,'provenance':provenance})


class TypedEvidenceProposer(StructuralProposer):
    def __init__(self,calls,*,profile='general'):
        super().__init__(calls)
        if profile not in ('general','criterion-only','nested-required'):raise ValueError('Unknown typed repair profile')
        self.profile=profile

    def propose(self,program,case,reference_label,feedback,*,slot,limit=2):
        value,_=self.calls.call('propose_typed',{'instruction':program.instruction,'rubric':program.rubric,
            'program':program.to_dict(),'reference_label':reference_label,'feedback':feedback,
            'profile':self.profile,'protocol':PROTOCOL,'limit':limit},PROPOSAL_SCHEMA,
            template=template('propose'),media=media_inputs(case.evidence),slot=slot,max_tokens=2048)
        rows=value.get('transactions')
        if not isinstance(rows,list) or len(rows)>limit:raise ValueError('Proposal count exceeded or malformed')
        return rows


def nested_nodes(program, seed):
    original={n.id for n in seed.nodes}
    return [n.id for n in program.nodes if n.role=='support' and n.id not in original and n.dependencies]


def create_typed_evidence_optimizer(calls,original,*,profile='general',reviewers=None,checkpoint=None,
                                    policy=None,random_seed=20261008,seed_audit=None):
    from .refinement import create_evidence_refinement_optimizer
    opt=create_evidence_refinement_optimizer(calls,original,reviewers=reviewers,checkpoint=checkpoint,
        policy=policy,random_seed=random_seed,seed_audit=seed_audit)
    opt.compiler=TypedEvidenceCompiler(calls,original)
    opt.proposer=TypedEvidenceProposer(calls,profile=profile)
    def apply(parent,tx):
        if profile=='criterion-only' and any(a['operation'] not in ('revise_support','revise_readout') for a in tx.get('actions',[])):
            raise ValueError('Criterion-only arm forbids structural changes')
        return apply_typed_transaction(parent,tx)
    opt.apply_edit=apply
    if profile=='nested-required':opt.candidate_eligibility=lambda p,seed:bool(nested_nodes(p,seed))
    return opt
