"""Matched inference, source exclusions and reference isolation; no live APIs."""
from collections import Counter
from copy import deepcopy

import pytest

from critical.core.decision.rich_evidence import COLLATERAL_FIELDS
from run.calitree_benchmark36 import infer_arm, select_cases


def candidates():
    return [{'id': f'{label}-{i}', 'group': f'{label}-{i}', 'reference': label,
             'task': ('one', 'two')[i % 2]} for label in ('no', 'partial', 'yes') for i in range(5)]


def test_selection_is_balanced_source_distinct_excludes_fits_and_is_order_invariant():
    rows = candidates(); rows += [{**rows[0], 'id': 'duplicate-source'}]
    excluded = {'no-0', 'partial-0', 'yes-0'}
    selected = select_cases(rows, excluded, per_class=2)
    assert Counter(r['reference'] for r in selected) == {'no': 2, 'partial': 2, 'yes': 2}
    assert len({r['group'] for r in selected}) == 6
    assert not {r['group'] for r in selected} & excluded
    assert selected == select_cases(rows[::-1], excluded, per_class=2)
    with pytest.raises(ValueError): select_cases(rows, excluded, per_class=5)


def observation():
    return {'instruction_scope': 'Recolor the intended object.',
            'target': {'state': 'matched', 'evidence': 'Same target.'},
            'source_integrity': {'state': 'preserved', 'evidence': 'Same scene.'},
            'requirements': [{'id': 'r', 'source_quote': 'Change the object', 'question': 'Is it changed?',
                              'role': 'core', 'state': 'complete', 'evidence': 'The requested change is present.'}],
            'collateral': {k: {'state': 'none', 'evidence': 'No collateral change.'} for k in COLLATERAL_FIELDS},
            'verification_visibility': {'state': 'full', 'evidence': 'Target visible.'}}


class Calls:
    def __init__(self): self.requests = []
    def call(self, stage, payload, schema, **kwargs):
        self.requests.append((stage, payload, schema, kwargs))
        return ({'label': 'yes', 'rationale': 'Requested change visible.'} if stage == 'flat_judge' else observation()), 'receipt'


class FrozenPolicy:
    def predict_records(self, rows):
        assert all(set(row) == {'instruction', 'observations'} for row in rows)
        return [{'label': 'yes', 'guard': None, 'features': {'anonymous': 2}} for _ in rows]
    def fit(self, *args, **kwargs): raise AssertionError('Evaluation attempted fitting')


@pytest.mark.parametrize('arm', ['flat', 'calitree'])
def test_neither_arm_receives_reference_and_policy_never_fits(arm):
    case = {'id': 'evaluation-id', 'case': 'E01', 'instruction': 'Change the object',
            'reference': 'no', 'human_score': 0., 'task': 'forbidden-metadata',
            'evidence': {'source_image': '/tmp/source.png', 'edited_image': '/tmp/edited.png'}}
    calls = Calls(); before = infer_arm(case, arm, calls, policy=FrozenPolicy(), flat_prompt='Fixed prompt')
    changed = deepcopy(case); changed['reference'] = 'yes'; changed['human_score'] = 2.
    after = infer_arm(changed, arm, calls, policy=FrozenPolicy(), flat_prompt='Fixed prompt')
    assert before == after
    for _, payload, _, kwargs in calls.requests:
        assert payload == {'instruction': case['instruction']}
        assert [m['text'] for m in kwargs['media'] if m['type'] == 'text'] == ['SOURCE image', 'EDITED image']
    assert len(calls.requests) == 2  # one request per explicit invocation, no hidden stages


def test_unrecognized_arm_is_rejected_without_model_call():
    calls = Calls()
    with pytest.raises(ValueError): infer_arm({}, 'other', calls, policy=FrozenPolicy(), flat_prompt='x')
    assert not calls.requests
