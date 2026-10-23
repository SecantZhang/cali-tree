"""Closed language cues in bound physical descriptions, never world-truth labels.

Negated mentions remain mentions and are paired with a negation cue. No raw
instruction, question, object name, reference label or identifier is a predictor.
"""
import re

from ..decision.artifacts import digest
from ..decision.bound_evidence_v2 import derive_record, ROLES

VERSION = 'bound-description-qualifiers-v54'
PATTERNS = {
    'partial_extent': r'\b(?:slight(?:ly)?|partial(?:ly)?|somewhat|partway|subtle|modest|minor|limited|incomplete(?:ly)?)\b',
    'complete_extent': r'\b(?:full(?:y)?|complete(?:ly)?|entire(?:ly)?|whole|throughout|clearly|distinctly)\b',
    'uncertainty': r'\b(?:unclear|uncertain|ambiguous|insufficient|not\s+clear(?:ly)?|cannot\s+(?:be\s+)?(?:confirm|determine|tell|verify))\b',
    'no_change': r'\b(?:unchanged|remains?\s+(?:the\s+)?same|no\s+(?:(?:clear|visible|discernible)\s+)?(?:change|movement|rotation|difference))\b',
    'change': r'\b(?:changed?|moved?|shifted?|rotated?|resized?|reoriented?|transformed?|altered?|different)\b',
    'replacement': r'\b(?:replaced?|replacement|substitute[ds]?|substitution|different\s+(?:object|entity|instance)|(?:new|another)\s+(?:object|instance)|lost|missing|disappeared|deformed|deformation)\b',
    'correspondence': r'\b(?:recognizable|corresponding|same|retained|preserved|consistent|similar)\b',
    'wrong_target': r'\b(?:wrong|unrelated|elsewhere|instead|substitute[ds]?)\b',
    'negation': r"\b(?:not|no|never|without|cannot|can't|doesn't|hasn't|isn't|neither|nor)\b"}
TEXT_FIELDS = ('source_evidence', 'edited_evidence', 'comparison')
COMBINED_CUES = ('partial_extent', 'uncertainty', 'no_change', 'replacement')
SPECS = {'qualifier_available': 'Valid bound physical descriptions are available for qualifier extraction.'}
for role in ROLES:
    for field in TEXT_FIELDS:
        for cue in PATTERNS:
            SPECS[f'qualifier_{role}_{field}_{cue}_any'] = f'At least one {role} {field} contains the declared {cue} language cue; this is not an affirmative factual claim.'
    for state in ('true', 'false', 'unknown'):
        for cue in COMBINED_CUES:
            SPECS[f'qualifier_{role}_desired_{state}_{cue}_any'] = f'A {role} check with desired_state={state} mentions {cue} in edited evidence/comparison.'
CONTRACT_REF = digest({'version': VERSION, 'patterns': PATTERNS, 'specs': SPECS,
                       'semantics': 'Evidence-description language indicators, not factual assertions. Negation is explicit and may co-occur with extent cues.',
                       'prohibited': 'Raw text vectors, object names, instructions, case/source IDs, hashes, coordinates, counts and majority thresholds as predictors.'})


def project(program, observation, pair_ref):
    if program is None or observation is None:
        return None
    record = derive_record(program, observation, pair_ref)
    values = dict.fromkeys(SPECS, False)
    values['qualifier_available'] = True
    for check in record['checks'].values():
        role, state, obs = check['role'], check['desired_state'], check['observation']
        for field in TEXT_FIELDS:
            for cue, pattern in PATTERNS.items():
                values[f'qualifier_{role}_{field}_{cue}_any'] |= re.search(pattern, obs[field], re.I) is not None
        text = obs['edited_evidence'] + ' ' + obs['comparison']
        if state in ('true', 'false', 'unknown'):
            for cue in COMBINED_CUES:
                values[f'qualifier_{role}_desired_{state}_{cue}_any'] |= re.search(PATTERNS[cue], text, re.I) is not None
    return {'version': VERSION, 'features': values}
