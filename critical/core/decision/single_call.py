"""One multimodal evidence observation followed by a versioned, pure label policy.

This is an opt-in judge, not a change to the fulfillment leaf optimizer. Checks
share one model call and therefore are not independent observations.
"""
from itertools import product
from pathlib import Path

from .compiler import TEXT, array, enum, media_inputs, object_schema


VERSION = 'single-call-evidence-v1'
POLICY_VERSION = 'core-fulfillment-material-shortfall-v1'
TEMPLATE = Path(__file__).parents[1] / 'prompts/templates/single_call_evidence_v1/check.txt'
STATES = ('complete', 'incomplete', 'absent', 'unknown')
TARGET_STATES = ('matched', 'wrong_target', 'unknown')
INTEGRITY_STATES = ('preserved', 'material_deviation', 'meaning_destroyed', 'unknown')
POLICY = {
    'version': POLICY_VERSION,
    'no': 'Wrong target, destroyed source meaning, or all core requirements absent.',
    'yes': 'Matched target, preserved relevant source meaning, every material requirement complete.',
    'partial': 'Some core fulfillment, with at least one material requirement shortfall or material source deviation.',
    'unknown': 'Enumerate possible evidence states; resolve only if every completion yields the same label.',
    'weights': None,
    'fitted_parameters': False,
}
FACT_SCHEMA = lambda states: object_schema({'state': enum(states), 'evidence': TEXT})
REQUIREMENT_SCHEMA = object_schema({
    'id': TEXT, 'source_quote': TEXT, 'question': TEXT,
    'role': enum(('core', 'constraint')), 'state': enum(STATES), 'evidence': TEXT,
})
SCHEMA = object_schema({
    'instruction_scope': TEXT,
    'target': FACT_SCHEMA(TARGET_STATES),
    'source_integrity': FACT_SCHEMA(INTEGRITY_STATES),
    'requirements': {**array(REQUIREMENT_SCHEMA), 'minItems': 1, 'maxItems': 6},
})


def prompt():
    return TEMPLATE.read_text()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_observation(value, instruction):
    """Reject malformed or ungrounded records rather than inventing a label."""
    if not _text(instruction) or not isinstance(value, dict) or set(value) != set(SCHEMA['properties']):
        raise ValueError('Invalid instruction or evidence observation fields')
    if not _text(value['instruction_scope']):
        raise ValueError('Missing instruction scope')
    for name, states in (('target', TARGET_STATES), ('source_integrity', INTEGRITY_STATES)):
        fact = value[name]
        if (not isinstance(fact, dict) or set(fact) != {'state', 'evidence'}
                or fact['state'] not in states or not _text(fact['evidence'])):
            raise ValueError('Invalid ' + name + ' observation')
    requirements = value['requirements']
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 6:
        raise ValueError('One to six material requirements required')
    ids, questions = set(), set()
    for r in requirements:
        if not isinstance(r, dict) or set(r) != set(REQUIREMENT_SCHEMA['properties']):
            raise ValueError('Invalid requirement fields')
        if not all(_text(r[k]) for k in ('id', 'source_quote', 'question', 'evidence')):
            raise ValueError('Missing requirement text or evidence')
        if r['source_quote'] not in instruction:
            raise ValueError('Requirement quote must occur in the instruction')
        question = ' '.join(r['question'].casefold().split())
        if r['id'] in ids or question in questions:
            raise ValueError('Duplicate requirement identity or question')
        ids.add(r['id']); questions.add(question)
        if r['role'] not in ('core', 'constraint') or r['state'] not in STATES:
            raise ValueError('Invalid requirement role or state')
    if not any(r['role'] == 'core' for r in requirements):
        raise ValueError('At least one core requirement is required')
    return value


def _resolved_label(target, integrity, requirements, states):
    if target == 'wrong_target' or integrity == 'meaning_destroyed':
        return 'no'
    if all(s == 'absent' for r, s in zip(requirements, states) if r['role'] == 'core'):
        return 'no'
    if integrity == 'preserved' and all(s == 'complete' for s in states):
        return 'yes'
    return 'partial'


def apply_label_policy(value, instruction):
    """No LLM, reference labels, scores, thresholds, or case-specific rules."""
    validate_observation(value, instruction)
    target = value['target']['state']
    integrity = value['source_integrity']['state']
    reqs = value['requirements']
    targets = TARGET_STATES[:-1] if target == 'unknown' else (target,)
    integrities = INTEGRITY_STATES[:-1] if integrity == 'unknown' else (integrity,)
    choices = [STATES[:-1] if r['state'] == 'unknown' else (r['state'],) for r in reqs]
    labels = sorted({_resolved_label(t, i, reqs, states)
                     for t, i, *states in product(targets, integrities, *choices)})
    label = labels[0] if len(labels) == 1 else None
    return {'label': label, 'resolved': label is not None, 'possible_labels': labels,
            'policy_version': POLICY_VERSION,
            'reason': 'Every possible evidence completion yields ' + label if label else
                      'Unknown evidence can change the overall label'}


class SingleCallEvidenceJudge:
    """Use the existing durable LM transport for exactly one shared observation."""
    def __init__(self, calls):
        self.calls = calls
        self.identity = {'provider': calls.identity, 'judge': VERSION, 'policy': POLICY_VERSION}

    def judge(self, instruction, evidence, *, slot='once', case_id=None, max_tokens=16384):
        kwargs = {'case_id': case_id} if case_id is not None else {}
        observed, ref = self.calls.call(
            'single_call_evidence', {'instruction': instruction}, SCHEMA,
            template=prompt(), media=media_inputs(evidence), slot=slot,
            max_tokens=max_tokens, **kwargs)
        return {**apply_label_policy(observed, instruction),
                'observations': observed, 'execution_ref': ref, 'version': VERSION}
