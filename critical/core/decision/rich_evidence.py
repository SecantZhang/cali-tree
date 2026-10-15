"""Label-blind v2 extraction: generic collateral facts and verification visibility."""
from pathlib import Path

from .compiler import TEXT, enum, media_inputs, object_schema
from .single_call import SCHEMA as BASE_SCHEMA, validate_observation

VERSION = 'single-call-rich-evidence-v2'
TEMPLATE = Path(__file__).parents[1] / 'prompts/templates/single_call_evidence_v2/check.txt'
COLLATERAL_FIELDS = ('appearance_drift', 'entity_loss', 'entity_addition_or_duplication',
                     'relation_change', 'scene_replacement')
FACT_STATES = ('none', 'present', 'unknown')
VISIBILITY_STATES = ('full', 'partial', 'unobservable', 'not_applicable', 'unknown')
FACT = object_schema({'state': enum(FACT_STATES), 'evidence': TEXT})
SCHEMA = object_schema({**BASE_SCHEMA['properties'],
    'collateral': object_schema({name: FACT for name in COLLATERAL_FIELDS}),
    'verification_visibility': object_schema({'state': enum(VISIBILITY_STATES), 'evidence': TEXT}),
})


def prompt():
    return TEMPLATE.read_text()


def base_observation(value):
    return {k: value[k] for k in BASE_SCHEMA['properties']}


def validate_rich(value, instruction):
    if not isinstance(value, dict) or set(value) != set(SCHEMA['properties']):
        raise ValueError('Invalid rich evidence fields')
    validate_observation(base_observation(value), instruction)
    collateral = value['collateral']
    if not isinstance(collateral, dict) or set(collateral) != set(COLLATERAL_FIELDS):
        raise ValueError('All generic collateral observations are required')
    for fact, states in [*( (collateral[k], FACT_STATES) for k in COLLATERAL_FIELDS),
                         (value['verification_visibility'], VISIBILITY_STATES)]:
        if (not isinstance(fact, dict) or set(fact) != {'state', 'evidence'} or fact['state'] not in states
                or not isinstance(fact['evidence'], str) or not fact['evidence'].strip()):
            raise ValueError('Invalid collateral or visibility fact')
    return value


class RichEvidenceExtractor:
    def __init__(self, calls):
        self.calls = calls

    def extract(self, instruction, evidence, *, case_id=None, max_tokens=16384):
        kwargs = {'case_id': case_id} if case_id is not None else {}
        observed, ref = self.calls.call('rich_evidence', {'instruction': instruction}, SCHEMA,
                                       template=prompt(), media=media_inputs(evidence), slot='once',
                                       max_tokens=max_tokens, **kwargs)
        validate_rich(observed, instruction)
        return {'observations': observed, 'execution_ref': ref, 'version': VERSION}
