"""V4 ordered conditional evidence. V3 serialization and execution stay untouched."""
from dataclasses import asdict, dataclass, replace
import json

from critical.core.decision.artifacts import digest
from critical.core.decision.models import Requirement, Outcome
from .models import Node as LegacyNode, RobustProgram as LegacyProgram, GATES, validate as validate_legacy
from .errors import GraphValidationError

VERSION = 'decision-leaf-v4'
PROTOCOL = 'typed-evidence-v2'


@dataclass(frozen=True)
class Activation:
    check_id: str
    states: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceNode:
    id: str
    role: str
    outcome_id: str
    parent: str
    active_on: tuple[str, ...]
    dependencies: tuple[str, ...]  # Declared context, not necessarily prerequisites.
    question: str
    criteria: str
    binding: str
    requirement_id: str = ''
    required_dependencies: tuple[str, ...] = ()
    activation: Activation | None = None
    inferences: tuple = ()

    @classmethod
    def from_dict(cls, row):
        activation = row['activation']
        return cls(**{**row, 'active_on': tuple(row['active_on']), 'dependencies': tuple(row['dependencies']),
            'required_dependencies': tuple(row['required_dependencies']), 'inferences': tuple(row['inferences']),
            'activation': Activation(activation['check_id'], tuple(activation['states'])) if activation else None})


@dataclass(frozen=True)
class EvidenceProgram:
    instruction: str
    rubric: str
    requirements: tuple[Requirement, ...]
    outcomes: tuple[Outcome, ...]
    nodes: tuple[EvidenceNode, ...]
    checker_template: str
    mode: str = 'tree'
    version: str = VERSION
    aggregation: str = 'requested-all-some-none-v4'

    def to_dict(self):
        return json.loads(json.dumps(asdict(self)))

    @classmethod
    def from_dict(cls, row):
        obj = cls(**{**row, 'requirements': tuple(Requirement(**r) for r in row['requirements']),
            'outcomes': tuple(Outcome(**{**o, 'requirement_ids': tuple(o['requirement_ids'])}) for o in row['outcomes']),
            'nodes': tuple(EvidenceNode.from_dict(n) for n in row['nodes'])})
        return validate(obj)

    @property
    def ref(self):
        validate(self)
        return digest(self.to_dict())

    def view(self, mode):
        return validate(replace(self, mode=mode))


def validate(p, original=None):
    if p.version != VERSION or p.mode != 'tree' or p.aggregation != 'requested-all-some-none-v4':
        raise ValueError('Unsupported v4 executable contract')
    if len(p.outcomes) != 1 or not 2 <= len(p.nodes) <= 4:
        raise ValueError('V4 needs one outcome, one to three supports and one fulfillment')
    # Reuse provenance, coverage and ancestry validation without changing legacy types.
    old_nodes = tuple(LegacyNode(**{k: getattr(n, k) for k in LegacyNode.__dataclass_fields__}) for n in p.nodes)
    validate_legacy(LegacyProgram(p.instruction, p.rubric, p.requirements, p.outcomes, old_nodes, p.checker_template))
    requirements = {r.id for r in p.requirements}
    earlier = []
    for index, n in enumerate(p.nodes):
        if n.inferences or n.parent != (earlier[-1] if earlier else '') or n.active_on != (GATES if earlier else ()):
            raise ValueError('V4 topology is a code-owned all-state ancestor chain; activation is separate')
        if len(set(n.dependencies)) != len(n.dependencies) or tuple(i for i in earlier if i in n.dependencies) != n.dependencies:
            raise ValueError('Context references must be unique and saved in ancestor order')
        if len(set(n.required_dependencies)) != len(n.required_dependencies) or not set(n.required_dependencies) <= set(n.dependencies):
            raise ValueError('Known prerequisites must be a unique subset of declared context')
        if n.role == 'support':
            if index == len(p.nodes)-1 or n.outcome_id or n.requirement_id not in requirements:
                raise ValueError('Support must map to an immutable requirement, without completion credit')
            if n.activation:
                if n.activation.check_id not in earlier:
                    raise GraphValidationError('activation_not_ancestor', f'{n.id} activation references non-earlier support {n.activation.check_id}',
                                               node_id=n.id, dependency_id=n.activation.check_id)
                if not n.activation.states or len(set(n.activation.states)) != len(n.activation.states) or not set(n.activation.states) <= set(GATES):
                    raise ValueError('Activation needs explicit pass/fail/unknown states')
        else:
            o=p.outcomes[0]
            if index != len(p.nodes)-1 or n.activation or n.requirement_id or n.dependencies != tuple(earlier):
                raise ValueError('Fulfillment must always consume all supports; it cannot be conditionally hidden')
            if n.question != o.description or n.binding != 'Target: '+o.target+'. Reference: '+o.reference+'.':
                raise ValueError('Requested question and target/reference binding stay frozen')
        earlier.append(n.id)
    if len({ ' '.join(n.question.lower().split()) for n in p.nodes }) != len(p.nodes):
        raise ValueError('Evidence questions must be distinct from each other and fulfillment')
    if original is not None and (p.instruction,p.rubric,p.requirements,p.outcomes) != (
            original.instruction,original.rubric,original.requirements,original.outcomes):
        raise ValueError('Original instruction, rubric, requirement ledger and outcome stay frozen')
    return p


def export_program(p):
    return {'program_ref': p.ref, 'program': p.to_dict()}


def restore_program(row):
    p = EvidenceProgram.from_dict(row['program'])
    if p.ref != row['program_ref']:
        raise ValueError('Program hash mismatch')
    return p
