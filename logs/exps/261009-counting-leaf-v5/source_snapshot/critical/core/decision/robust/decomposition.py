"""Enforced evidence decomposition, using the unchanged v3 execution format."""
from dataclasses import asdict
import json
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.decision.compiler import object_schema, array, TEXT, AUDIT_SCHEMA, media_inputs
from .compiler import NODE_SCHEMA, RobustCompiler, checked_audit
from .executor import OBS_SCHEMA
from .models import GATES, RobustProgram, validate

TEMPLATES = Path(__file__).parents[2] / 'prompts/templates/forced_decomposition_v1'
CONTRACT = 'forced-evidence-readout-v1'


def template(name):
    return (TEMPLATES / (name + '.txt')).read_text()


def validate_decomposition(program, original=None):
    validate(program)
    if len(program.outcomes) != 1 or not 3 <= len(program.nodes) <= 4:
        raise ValueError('Forced decomposition needs one outcome, two or three supports and one readout')
    if program.mode != 'tree' or program.checker_template != template('check'):
        raise ValueError('Forced decomposition execution contract changed')
    supports, readout = program.nodes[:-1], program.nodes[-1]
    if any(n.role != 'support' or n.outcome_id or n.dependencies or n.inferences for n in supports):
        raise ValueError('Evidence checks must be independent supports without completion credit')
    if readout.role != 'requested' or readout.outcome_id != program.outcomes[0].id or readout.inferences:
        raise ValueError('One final requested readout without shortcuts is required')
    if readout.dependencies != tuple(n.id for n in supports):
        raise ValueError('Readout must consume every support observation in order')
    for i, node in enumerate(program.nodes):
        if node.parent != (program.nodes[i-1].id if i else ''):
            raise ValueError('Forced evidence/readout nodes must execute in saved chain order')
        valid_activation = set(node.active_on) == set(GATES) if i else not node.active_on
        if not valid_activation:
            raise ValueError('Do not suppress known negative or unknown support branches')
    normalize = lambda value: ' '.join(value.lower().split())
    if len({normalize(n.question) for n in supports}) != len(supports):
        raise ValueError('Duplicate evidence questions are not decomposition')
    if any(normalize(n.question) == normalize(readout.question) for n in supports):
        raise ValueError('Support cannot duplicate the fulfillment readout')
    if original is not None and (program.instruction, program.rubric, program.requirements, program.outcomes) != (
            original.instruction, original.rubric, original.requirements, original.outcomes):
        raise ValueError('Original instruction, rubric, ledger and outcome must remain frozen')
    return program


class DecompositionCompiler(RobustCompiler):
    def __init__(self, calls, original):
        super().__init__(calls)
        self.original = original

    def compile_from(self, *, slot):
        value, _ = self.calls.call('compile_decomposition', {'original': self.original.to_dict(),
            'contract': CONTRACT, 'max_checks': 4, 'minimum_supports': 2},
            object_schema({'nodes': array(NODE_SCHEMA)}), template=template('compile'), slot=slot, max_tokens=2048)
        row = self.original.to_dict()
        row.update(nodes=value['nodes'], mode='tree', checker_template=template('check'))
        return validate_decomposition(RobustProgram.from_dict(row), self.original)

    def audit(self, program, *, slot):
        validate_decomposition(program, self.original)
        value, ref = self.calls.call('audit', {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'contract': CONTRACT}, AUDIT_SCHEMA,
            template=template('audit'), slot=slot, max_tokens=2048)
        return checked_audit(value, ref)

    def audit_pair(self, decomposed=None, *, slot):
        programs = {'broad': self.original}
        if decomposed is not None:
            validate_decomposition(decomposed, self.original)
            programs['decomposed'] = decomposed
        value, ref = self.calls.call('audit_pair', {'instruction': self.original.instruction, 'rubric': self.original.rubric,
            'programs': {key: p.to_dict() for key, p in programs.items()}, 'contract': CONTRACT},
            object_schema({key: AUDIT_SCHEMA for key in programs}), template=template('audit'), slot=slot, max_tokens=2048)
        return {key: checked_audit(value[key], ref) for key in programs}


class DecompositionChecker:
    contract = CONTRACT

    def __init__(self, calls):
        self.calls = calls
        self.identity = {'provider': calls.identity, 'checker': self.contract, 'scope': getattr(calls, 'case_id', None)}

    def validate_program(self, program):
        return validate_decomposition(program)

    def check(self, program, node, outcome, evidence, dependencies, *, slot, final=False):
        self.validate_program(program)
        expected = list(node.dependencies)
        if [d['check_id'] for d in dependencies] != expected:
            raise ValueError('Saved dependency context differs from forced execution contract')
        schema = object_schema({**OBS_SCHEMA['properties'], 'used_dependency_ids': array(TEXT)})
        value, ref = self.calls.call('check', {'instruction': program.instruction, 'rubric': program.rubric,
            'node': asdict(node), 'outcome': asdict(outcome) if outcome else None,
            'dependencies': dependencies, 'contract': self.contract}, schema, template=program.checker_template,
            media=media_inputs(evidence) if node.role == 'support' else (), slot=slot, final=final, max_tokens=1024)
        path = self.calls.directory / 'jobs' / (ref + '.json')
        job = json.loads(path.read_text())
        row = {**value, 'execution_ref': ref, 'completion_tokens': int(job['response'].get('completionTokens', 0))}
        if value.get('used_dependency_ids') != expected:
            # Preserve actual completed-call usage; executor records this as invalid,
            # unresolved evidence rather than resampling or accepting an ignored dependency.
            job['observation_validation_error'] = 'Readout did not acknowledge every dependency in saved order'
            save_json(path, job)
            row.update(status='invalid_dependency_consumption', evidence=job['observation_validation_error'])
        return row


def validate_broad(program, original):
    validate(program)
    if len(program.nodes) != 1 or program.nodes[0].role != 'requested' or program.nodes[0].dependencies or program.nodes[0].parent or program.nodes[0].inferences:
        raise ValueError('Broad control must retain one direct visual fulfillment check')
    if (program.instruction, program.rubric, program.requirements, program.outcomes, program.mode, program.checker_template) != (
            original.instruction, original.rubric, original.requirements, original.outcomes, original.mode, original.checker_template):
        raise ValueError('Broad control original coverage and execution contract must remain frozen')
    return program


class BroadCompiler(RobustCompiler):
    def __init__(self, calls, original):
        super().__init__(calls)
        self.original = original

    def audit(self, program, *, slot):
        validate_broad(program, self.original)
        return super().audit(program, slot=slot)
