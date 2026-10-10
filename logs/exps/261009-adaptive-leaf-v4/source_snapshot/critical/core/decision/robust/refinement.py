"""Versioned evidence-refinement contract; historical independent checks stay intact."""
from dataclasses import replace
from pathlib import Path

from critical.core.decision.compiler import object_schema, array, AUDIT_SCHEMA
from .compiler import NODE_SCHEMA, RobustCompiler, checked_audit
from .decomposition import DecompositionChecker
from .models import RobustProgram, validate

CONTRACT = 'nested-evidence-readout-v1'
TEMPLATES = Path(__file__).parents[2] / 'prompts/templates/evidence_refinement_v1'


def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()


def validate_refinement(program, original=None):
    validate(program)
    if program.mode != 'tree' or program.checker_template != template('check'):
        raise ValueError('Nested evidence execution contract changed')
    if len(program.outcomes) != 1 or not 3 <= len(program.nodes) <= 4:
        raise ValueError('Need two or three supports and one final fulfillment check')
    supports, readout = program.nodes[:-1], program.nodes[-1]
    if any(n.role != 'support' or n.outcome_id or n.inferences for n in supports):
        raise ValueError('Supports cannot earn completion credit or infer outcomes')
    if readout.role != 'requested' or readout.outcome_id != program.outcomes[0].id or readout.inferences:
        raise ValueError('One final evidence-only requested readout is required')
    if readout.dependencies != tuple(n.id for n in supports):
        raise ValueError('Readout must consume all support evidence in saved order')
    ids = {n.id for n in supports}
    if any(n.parent and n.parent not in ids for n in program.nodes):
        raise ValueError('Fulfillment cannot gate support evidence')
    visited = set()
    for node in program.nodes:
        if node.parent and node.parent not in visited:
            raise ValueError('Save nested evidence in ancestor-first execution order')
        visited.add(node.id)
    normalized = [' '.join(n.question.lower().split()) for n in program.nodes]
    if len(set(normalized)) != len(normalized):
        raise ValueError('Evidence questions must be distinct from each other and fulfillment')
    if original is not None and (program.instruction, program.rubric, program.requirements, program.outcomes) != (
            original.instruction, original.rubric, original.requirements, original.outcomes):
        raise ValueError('Original instruction, rubric, requirement ledger and outcome stay frozen')
    return program


def promote_decomposition(program):
    """Explicit new program/hash, never reinterpret a saved v1 execution template."""
    from .decomposition import validate_decomposition
    validate_decomposition(program)
    return validate_refinement(replace(program, checker_template=template('check')), program)


class EvidenceRefinementCompiler(RobustCompiler):
    def __init__(self, calls, original):
        super().__init__(calls)
        self.original = original

    def compile(self, instruction, rubric, *, slot):
        if (instruction, rubric) != (self.original.instruction, self.original.rubric):
            raise ValueError('Instruction or rubric changed')
        value, _ = self.calls.call('compile_refinement', {'original': self.original.to_dict(),
            'contract': CONTRACT, 'max_checks': 4, 'minimum_supports': 2},
            object_schema({'nodes': array(NODE_SCHEMA)}), template=template('compile'), slot=slot, max_tokens=2048)
        row = self.original.to_dict()
        row.update(nodes=value['nodes'], mode='tree', checker_template=template('check'))
        return validate_refinement(RobustProgram.from_dict(row), self.original)

    def audit(self, program, *, slot):
        validate_refinement(program, self.original)
        value, ref = self.calls.call('audit', {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'contract': CONTRACT}, AUDIT_SCHEMA,
            template=template('audit'), slot=slot, max_tokens=2048)
        return checked_audit(value, ref)

    def audit_pair(self, decomposed=None, *, slot):
        programs = {'broad': self.original}
        if decomposed is not None:
            validate_refinement(decomposed, self.original)
            programs['decomposed'] = decomposed
        value, ref = self.calls.call('audit_pair', {'instruction': self.original.instruction,
            'rubric': self.original.rubric, 'programs': {k: p.to_dict() for k, p in programs.items()},
            'contracts': {'broad': 'direct-image-fulfillment', 'decomposed': CONTRACT}},
            object_schema({key: AUDIT_SCHEMA for key in programs}),
            template=template('audit') + '\nWhen auditing a pair, the broad control is one direct-image fulfillment check; the nested evidence-only restrictions apply only to decomposed. Audit each separately.',
            slot=slot, max_tokens=2048)
        return {key: checked_audit(value[key], ref) for key in programs}


class EvidenceRefinementChecker(DecompositionChecker):
    contract = CONTRACT

    def validate_program(self, program):
        return validate_refinement(program)
