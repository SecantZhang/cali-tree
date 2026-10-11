"""Flat program fields and validation; persisted contracts stay version-specific."""
from dataclasses import dataclass, asdict
import json
from critical.core.decision.models import Requirement, Outcome

@dataclass(frozen=True)
class Decision:
    id: str
    requirement_id: str
    question: str
    criteria: str
    binding: str
    role: str = 'decision'

@dataclass(frozen=True)
class FlatProgram:
    instruction: str
    rubric: str
    requirements: tuple[Requirement,...]
    outcomes: tuple[Outcome,...]
    nodes: tuple[Decision,...]
    checker_template: str
    version: str = 'decision-leaf-v5'
    mode: str = 'flat'
    aggregation: str = 'required-condition-all-some-none-count-v1'

    def to_dict(self):return json.loads(json.dumps(asdict(self)))

@dataclass(frozen=True)
class GroundedDecision(Decision):
    source_quote: str = ''
    aspect: str = ''
    endpoint: str = ''
    necessity: str = ''

def validate_flat(p,original=None,*,expected_version,expected_aggregation,allowed_roles=('decision',)):
    if (p.version,p.mode,p.aggregation)!=(expected_version,'flat',expected_aggregation):raise ValueError('Unsupported counting contract; legacy evidence programs cannot be reinterpreted')
    if not all(isinstance(v,str) and v.strip() for v in (p.instruction,p.rubric,p.checker_template)):
        raise ValueError('Missing original instruction, rubric or frozen template')
    if not p.requirements or not p.outcomes or not 1<=len(p.nodes)<=4:raise ValueError('Need covered requirements and one to four independent decisions')
    for group in (p.requirements,p.outcomes,p.nodes):
        if len({v.id for v in group})!=len(group) or any(not isinstance(v.id,str) or not v.id.strip() for v in group):raise ValueError('Duplicate/empty identity')
    reqs={r.id for r in p.requirements}
    for r in p.requirements:
        if not r.text.strip() or not r.source_phrase.strip() or r.source_phrase not in p.instruction:raise ValueError('Invalid requirement provenance')
    for n in p.nodes:
        if n.role not in allowed_roles or n.requirement_id not in reqs or not all(isinstance(v,str) and v.strip() for v in (n.question,n.criteria,n.binding)):
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

def count_states(states):
    """Unknowns, failures and an empty set remain unresolved; no model adjudication."""
    if not states or any(v not in ('pass','fail') for v in states):return 'unknown'
    passed=states.count('pass')
    return 'complete' if passed==len(states) else 'absent' if passed==0 else 'partial'
