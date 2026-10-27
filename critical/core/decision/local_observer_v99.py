"""One local observation for a review input, never one call per predicate."""
from ...lm_engine.local_qwen_grammar_v95 import LocalQwenGrammarEngine
from ..calibration.local_semantic_runtime_v99 import checkpoint_compute_ref
from . import local_rubric_evidence_v94 as facts
from .artifacts import digest
from .bound_evidence_v2 import image_identity


class LocalObserver:
    def __init__(self, engine, profile, template, expected_checkpoint_compute_ref):
        if not isinstance(engine, LocalQwenGrammarEngine) or engine.history is None:
            raise ValueError('A logged, pinned local grammar engine is required')
        if (engine.name != profile['engine'] or engine.model != profile['model'] or engine.device != profile['device'] or
                engine.max_tokens != profile['max_new_tokens'] or engine.max_pixels != profile['max_pixels_per_image'] or
                checkpoint_compute_ref(engine.identity) != expected_checkpoint_compute_ref or
                profile['contract_ref'] != facts.CONTRACT_REF or profile['schema_ref'] != digest(facts.schema())):
            raise ValueError('Local observer differs from the trained computation')
        self.engine, self.profile, self.template = engine, profile, template
        self.identity_ref, self.template_ref = digest(profile), digest(template)

    def observe(self, program, evidence, pair_ref):
        _, measured_pair = image_identity(evidence)
        if measured_pair != pair_ref:
            raise ValueError('Local observer received a different image pair')
        prompt = facts.prompt(program, self.template)
        response = self.engine.generate(prompt, [
            {'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'path': evidence['source_image']},
            {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'path': evidence['edited_image']}], facts.schema(), strict_schema=True)
        if response['finishReason'] != 'stop':
            raise ValueError('Truncated local observation remains unavailable')
        value = facts.validate(response['parsed'])
        return facts.bind(program, pair_ref, self.identity_ref, digest(prompt), value)
