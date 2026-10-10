"""Immutable v3 leaf programs. No training labels belong in this module."""
from dataclasses import asdict, dataclass, replace
import json
from critical.core.decision.models import Requirement, Outcome
from critical.core.decision.artifacts import digest
from .errors import GraphValidationError

VERSION = 'decision-leaf-v3'
STATES = ('complete', 'partial', 'absent', 'unknown')
GATES = ('pass', 'fail', 'unknown')

@dataclass(frozen=True)
class Inference:
    when: str
    outcome_id: str
    status: str
    applicability: str
    justification: str

@dataclass(frozen=True)
class Node:
    id: str
    role: str
    outcome_id: str
    parent: str
    active_on: tuple[str, ...]
    dependencies: tuple[str, ...]
    question: str
    criteria: str
    binding: str
    inferences: tuple[Inference, ...] = ()

    @classmethod
    def from_dict(cls, row):
        return cls(**{**row, 'active_on': tuple(row['active_on']),
                      'dependencies': tuple(row['dependencies']),
                      'inferences': tuple(Inference(**v) for v in row['inferences'])})

@dataclass(frozen=True)
class RobustProgram:
    instruction: str
    rubric: str
    requirements: tuple[Requirement, ...]
    outcomes: tuple[Outcome, ...]
    nodes: tuple[Node, ...]
    checker_template: str
    mode: str = 'tree'
    version: str = VERSION
    aggregation: str = 'requested-all-some-none-v3'

    def to_dict(self):
        return json.loads(json.dumps(asdict(self)))

    @classmethod
    def from_dict(cls, row):
        obj = cls(**{**row, 'requirements': tuple(Requirement(**v) for v in row['requirements']),
                     'outcomes': tuple(Outcome(**{**v, 'requirement_ids': tuple(v['requirement_ids'])}) for v in row['outcomes']),
                     'nodes': tuple(Node.from_dict(v) for v in row['nodes'])})
        validate(obj)
        return obj

    @property
    def ref(self):
        validate(self)
        return digest(self.to_dict())

    def view(self, mode):
        obj = replace(self, mode=mode)
        validate(obj)
        return obj


def validate(p):
    if p.version != VERSION or p.mode not in ('flat', 'tree') or p.aggregation != 'requested-all-some-none-v3':
        raise ValueError('Unsupported executable contract')
    if not p.instruction.strip() or not p.rubric.strip() or not p.checker_template.strip():
        raise ValueError('Missing original instruction, rubric or frozen template')
    if not p.requirements or not p.outcomes or not p.nodes:
        raise ValueError('Need requirements, outcomes and one to four checks; never truncate requirements')
    for group in (p.requirements, p.outcomes, p.nodes):
        if len({v.id for v in group}) != len(group) or any(not v.id.strip() for v in group):
            raise ValueError('Duplicate or empty identity')
    reqs = {v.id for v in p.requirements}
    for r in p.requirements:
        if not r.text.strip() or not r.source_phrase.strip() or r.source_phrase not in p.instruction:
            raise ValueError('Requirement provenance must quote the original instruction')
    covered = set()
    for o in p.outcomes:
        if not o.requirement_ids or not set(o.requirement_ids) <= reqs:
            raise ValueError('Broken requirement mapping')
        if o.applicability not in ('applicable', 'not_applicable', 'unknown') or not o.description.strip() or not o.target.strip():
            raise ValueError('Invalid outcome binding or applicability')
        covered.update(o.requirement_ids)
    if covered != reqs:
        raise ValueError('Uncovered required instruction')
    nodes = {n.id: n for n in p.nodes}
    outs = {o.id for o in p.outcomes}
    for n in p.nodes:
        if n.role not in ('requested', 'support') or not n.question.strip() or not n.criteria.strip() or not n.binding.strip():
            raise ValueError('Missing executable node contract')
        if (n.role == 'requested' and n.outcome_id not in outs) or (n.outcome_id and n.outcome_id not in outs):
            raise ValueError('Broken outcome reference')
        ancestors, parent = [], n.parent
        while parent:
            if parent not in nodes:
                raise GraphValidationError('missing_parent', f'{n.id} has missing parent {parent}', node_id=n.id, dependency_id=parent)
            if parent in ancestors or parent == n.id:
                raise GraphValidationError('cycle', f'Cyclic routing at {n.id} through {parent}', node_id=n.id, dependency_id=parent)
            ancestors.append(parent)
            parent = nodes[parent].parent
        if len(ancestors) + 1 > 4:
            raise GraphValidationError('depth_limit', f'{n.id} exceeds depth four', node_id=n.id)
        for dependency in n.dependencies:
            if dependency not in nodes:
                raise GraphValidationError('missing_dependency', f'{n.id} consumes missing check {dependency}', node_id=n.id, dependency_id=dependency)
            if dependency not in ancestors:
                relation = ('separate_root' if not n.parent and not nodes[dependency].parent else
                            'sibling' if nodes[dependency].parent == n.parent else 'non_ancestor')
                raise GraphValidationError('dependency_not_ancestor',
                    f'{n.id} consumes {dependency}, but it is a {relation}, not an ancestor',
                    node_id=n.id, dependency_id=dependency, relationship=relation)
        if n.parent:
            allowed = STATES if nodes[n.parent].role == 'requested' else GATES
            if not n.active_on or not set(n.active_on) <= set(allowed):
                raise ValueError('Explicit valid activation states required')
        elif n.active_on:
            raise ValueError('Virtual-root children have no activation condition')
        own_states = STATES if n.role == 'requested' else GATES
        inference_keys = set()
        for i in n.inferences:
            key = (i.when, i.outcome_id)
            if key in inference_keys or i.when not in own_states or i.when == 'unknown' or i.outcome_id not in outs:
                raise ValueError('Invalid or conflicting inference')
            inference_keys.add(key)
            if i.status not in STATES or i.applicability not in ('applicable', 'not_applicable', 'unknown') or not i.justification.strip():
                raise ValueError('Inference must explicitly account for outcome and applicability')
    if len(p.nodes)>4:
        raise GraphValidationError('check_limit','Need one to four checks; never truncate requirements')
    for o in p.outcomes:
        if sum(n.role == 'requested' and n.outcome_id == o.id for n in p.nodes) != 1:
            raise ValueError('Each outcome needs exactly one fulfillment check')
    # Every terminal path starts with every outcome explicitly unresolved; execution
    # can only replace it with evidence, audited inference, or declared applicability.
    return p


def export_program(p):
    return {'program_ref': p.ref, 'program': p.to_dict()}


def restore_program(row):
    p = RobustProgram.from_dict(row['program'])
    if p.ref != row['program_ref']:
        raise ValueError('Program hash mismatch')
    return p
