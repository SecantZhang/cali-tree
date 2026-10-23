"""Bound original evidence -> guarded frozen expert, otherwise regular judge.

This restores the trained feature computation instead of sending conditional
rules back to an LLM. Covered outputs are the original expert's predictions.
"""
from ....decision.bound_compiler_v3 import BoundInstructionCompilerV3
from ....decision.bound_evidence_v2 import BoundVisualObserver, image_identity, validate_program
from ....decision.semantic_interpretation_v5 import make_input, schema, validate, PROMPT
from .task_coverage import LABELS, SCHEMA, TEMPLATES
from ....decision.compiler import media_inputs


class BoundEvidencePipeline:
    def __init__(self, calls):
        self.calls = calls

    def compile(self, instruction, *, case_id=None):
        return BoundInstructionCompilerV3(self.calls).compile(instruction, case_id=case_id, max_tokens=8192)['program']

    def extract(self, program, evidence, *, observation=None, interpretation=None, case_id=None):
        pair_ref = image_identity(evidence)[1]
        if observation is None:
            observation = BoundVisualObserver(self.calls).observe(program, evidence, case_id=case_id, max_tokens=16384)['observation']
        payload = make_input(program, observation, pair_ref)
        if interpretation is None:
            interpretation, _ = self.calls.call('instruction_relative_interpretation', payload, schema(payload),
                                                template=PROMPT, slot='once', max_tokens=8192, case_id=case_id)
        validate(payload, interpretation)
        return observation, interpretation, pair_ref


class EvidenceCoveredJudge:
    def __init__(self, calls, gate, *, extractor=None, regular_prompt=None):
        self.calls, self.gate = calls, gate
        self.extractor = extractor if extractor is not None else BoundEvidencePipeline(calls)
        self.regular_prompt = regular_prompt if regular_prompt is not None else (TEMPLATES / 'regular.txt').read_text()

    def judge(self, instruction, evidence, *, program=None, observation=None, interpretation=None,
              case_id=None, max_tokens=2048):
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError('A nonempty instruction is required')
        route = {'covered': False, 'prediction': -1, 'reason': 'invalid_or_missing_bound_evidence', 'matches': []}
        error = None
        try:
            if program is None:
                program = self.extractor.compile(instruction, case_id=case_id)
            validate_program(program)
            if program['instruction'] != instruction:
                raise ValueError('Instruction/program mismatch')
            if self.gate.accepts_task(program):
                observation, interpretation, pair = self.extractor.extract(
                    program, evidence, observation=observation, interpretation=interpretation, case_id=case_id)
                route = self.gate.select_bound(program, observation, pair, interpretation)
            else:
                route['reason'] = 'unseen_task_profile'
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            error = type(exc).__name__
        if route['covered']:
            return {'judgment': {'label': LABELS[route['prediction']],
                                 'rationale': 'Frozen expert prediction; supporting rule and evidence traces are recorded in route.matches.'},
                    'source': 'frozen_tree', 'route': route, 'execution_ref': None, 'extraction_error': error}
        value, ref = self.calls.call('flat_judge', {'instruction': instruction}, SCHEMA,
                                     template=self.regular_prompt, media=media_inputs(evidence),
                                     case_id=case_id, slot='once', max_tokens=max_tokens)
        if (set(value) != {'rationale', 'label'} or value['label'] not in (*LABELS, 'unresolved')
                or not isinstance(value['rationale'], str) or not value['rationale'].strip()):
            raise ValueError('Invalid fallback judge response')
        return {'judgment': value, 'source': 'regular_judge', 'route': route,
                'execution_ref': ref, 'extraction_error': error}
