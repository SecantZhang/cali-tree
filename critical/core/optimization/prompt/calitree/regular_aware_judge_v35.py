"""Opt-in regular-aware policy; reuse bound evidence and one flat judgment.

This policy always needs the regular judge, including on previously covered
inputs. It does not change the cheaper EvidenceCoveredJudge default.
"""
from ....calibration.semantic_hierarchy.portable_features_v8 import project
from ....decision.artifacts import digest
from ....decision.bound_evidence_v2 import validate_program
from ....decision.calls import BudgetExhausted, ProviderStopped
from ....decision.compiler import media_inputs
from .evidence_covered_judge import BoundEvidencePipeline
from .task_coverage import LABELS, SCHEMA, TEMPLATES


class RegularAwareJudge:
    def __init__(self, calls, policy, *, evidence_cache=None, identity=None,
                 extractor=None, regular_prompt=None):
        if evidence_cache is not None and (
                identity is None or evidence_cache.identity != identity
                or getattr(calls, 'identity', identity) != identity):
            raise ValueError('Inference identity differs from cached extraction identity')
        self.calls, self.policy, self.evidence_cache = calls, policy, evidence_cache
        self.extractor = extractor if extractor is not None else BoundEvidencePipeline(calls)
        self.regular_prompt = regular_prompt if regular_prompt is not None else (TEMPLATES / 'regular.txt').read_text()

    def judge(self, instruction, evidence, *, program=None, observation=None,
              interpretation=None, case_id=None, max_tokens=2048):
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError('A nonempty instruction is required')
        record = None
        extraction_error = None
        origin = 'provided' if any(v is not None for v in (program, observation, interpretation)) else 'fresh'
        try:
            if origin == 'fresh' and self.evidence_cache is not None:
                entry = self.evidence_cache.lookup(instruction, evidence)
                if entry is not None:
                    program, observation, interpretation = (entry[k] for k in ('program', 'observation', 'interpretation'))
                    origin = 'content_cache'
            if program is None:
                # Sibling outputs share the instruction compiler's durable slot.
                program = self.extractor.compile(instruction, case_id='compile-' + digest(instruction))
            validate_program(program)
            if program['instruction'] != instruction:
                raise ValueError('Instruction/program mismatch')
            observation, interpretation, pair = self.extractor.extract(
                program, evidence, observation=observation, interpretation=interpretation, case_id=case_id)
            record = project(program, observation, pair, interpretation)
        except (BudgetExhausted, ProviderStopped):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            extraction_error = type(exc).__name__

        regular_ref = None
        regular_error = None
        regular = -1
        value = {'label': 'unresolved', 'rationale': 'The regular judgment could not be obtained.'}
        try:
            response, regular_ref = self.calls.call(
                'flat_judge', {'instruction': instruction}, SCHEMA,
                template=self.regular_prompt, media=media_inputs(evidence),
                case_id=case_id, slot='once', max_tokens=max_tokens)
            if (not isinstance(response, dict) or set(response) != {'rationale', 'label'}
                    or response['label'] not in (*LABELS, 'unresolved')
                    or not isinstance(response['rationale'], str) or not response['rationale'].strip()):
                raise ValueError('Invalid regular judgment')
            value = response
            regular = LABELS.index(value['label']) if value['label'] in LABELS else -1
        except (BudgetExhausted, ProviderStopped):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            regular_error = type(exc).__name__

        route = {'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
        if record is not None:
            route = self.policy.resolve(program, record, regular)
        result = {'route': route, 'regular_judgment': value, 'regular_execution_ref': regular_ref,
                  'regular_error': regular_error, 'extraction_error': extraction_error, 'evidence_source': origin}
        if route['covered']:
            return {**result, 'judgment': {'label': LABELS[route['prediction']],
                    'rationale': 'Verified semantic policy decision; evidence and expert support are recorded in route.'},
                    'source': 'verified_semantic_policy', 'execution_ref': None}
        return {**result, 'judgment': value, 'source': 'regular_judge', 'execution_ref': regular_ref}
