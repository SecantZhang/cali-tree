"""Opt-in bound visual-policy inference with the unchanged regular fallback."""
from ....calibration.visual_semantic_policy_v69 import regular_label, LABELS
from ....decision.calls import ProviderStopped, BudgetExhausted
from ....decision.compiler import media_inputs
from .evidence_covered_judge import BoundEvidencePipeline
from .task_coverage import SCHEMA, TEMPLATES

_UNSET = object()


class VisualSemanticJudge:
    def __init__(self, calls, policy, encoder, *, extractor=None):
        self.calls, self.policy, self.encoder = calls, policy, encoder
        self.extractor = extractor if extractor is not None else BoundEvidencePipeline(calls)

    def judge(self, instruction, evidence, *, case_id=None, program=_UNSET, observation=_UNSET,
              interpretation=_UNSET, regular_judgment=_UNSET, vision_record=_UNSET):
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError('Nonempty edit instruction required')
        regular_ref, regular_error = None, None
        if regular_judgment is _UNSET:
            if self.calls is None:
                raise ValueError('Provide cached regular judgment or an authorized call interface')
            try:
                regular_judgment, regular_ref = self.calls.call('flat_judge', {'instruction': instruction}, SCHEMA,
                    template=(TEMPLATES / 'regular.txt').read_text(), media=media_inputs(evidence),
                    case_id=case_id, slot='once', max_tokens=2048)
            except (ProviderStopped, BudgetExhausted):
                raise
            except (ValueError, RuntimeError, KeyError, TypeError) as exc:
                regular_judgment, regular_error = None, type(exc).__name__
        regular = regular_label(regular_judgment)
        route = {'covered': False, 'prediction': regular, 'reason': 'invalid_or_missing_bound_evidence'}
        extraction_error = None
        try:
            # Explicit None denotes a retained failed cache slot. It must never
            # trigger another model request; omission denotes a fresh stage.
            if program is None or observation is None or interpretation is None:
                raise ValueError('Retained missing bound-evidence slot')
            if program is _UNSET:
                program = self.extractor.compile(instruction, case_id=case_id)
            if program['instruction'] != instruction:
                raise ValueError('Instruction/program mismatch')
            observation, interpretation, pair = self.extractor.extract(program, evidence,
                observation=None if observation is _UNSET else observation,
                interpretation=None if interpretation is _UNSET else interpretation, case_id=case_id)
            if vision_record is _UNSET:
                vision_record = self.encoder.compute(program, evidence)
            route = self.policy.resolve_bound(program, observation, pair, interpretation, regular_judgment, vision_record)
        except (ProviderStopped, BudgetExhausted):
            raise
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            extraction_error = type(exc).__name__
        judgment = ({'label': LABELS[route['prediction']], 'rationale': 'The learned visual-semantic policy predicts this grade; supporting class scores and expert agreement are recorded in the route.'}
                    if route['covered'] else regular_judgment or {'label': 'unresolved', 'rationale': 'The retained regular judgment is unavailable.'})
        return {'judgment': judgment, 'route': route, 'source': 'visual_policy' if route['covered'] else 'regular_judge',
                'regular_execution_ref': regular_ref, 'regular_error': regular_error, 'extraction_error': extraction_error}
