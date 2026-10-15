"""Semantic policy regressions and a one-call durable mock; no live APIs."""
from copy import deepcopy

from PIL import Image
import pytest

from critical.core.decision.calls import DurableCalls
from critical.core.decision.single_call import SingleCallEvidenceJudge, apply_label_policy
from run.calitree_single_call import paired_comparison


INSTRUCTION = 'Move the remote to the right of the headphones'


def observation(*states):
    questions = ('Was the intended remote moved?', 'Is its resulting position right of the headphones?')
    return {
        'instruction_scope': 'Move the original remote relative to the headphones.',
        'target': {'state': 'matched', 'evidence': 'The same remote and headphones are identifiable.'},
        'source_integrity': {'state': 'preserved', 'evidence': 'Relevant scene content remains.'},
        'requirements': [
            {'id': str(i), 'source_quote': quote, 'question': questions[i],
             'role': role, 'state': state, 'evidence': 'Concrete visible source/edited evidence.'}
            for i, (state, role, quote) in enumerate(zip(
                states or ('complete', 'complete'), ('core', 'constraint'), ('Move the remote', 'right of the headphones')))
        ],
    }


def test_wrong_entity_cannot_pass_even_with_apparent_requested_result():
    value = observation()
    value['target']['state'] = 'wrong_target'
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'no'


def test_satisfied_spatial_constraint_does_not_substitute_for_missing_core_action():
    assert apply_label_policy(observation('absent', 'complete'), INSTRUCTION)['label'] == 'no'


def test_material_shortfall_is_partial_not_a_majority_vote():
    assert apply_label_policy(observation('complete', 'absent'), INSTRUCTION)['label'] == 'partial'
    assert apply_label_policy(observation('incomplete', 'complete'), INSTRUCTION)['label'] == 'partial'
    assert apply_label_policy(observation(), INSTRUCTION)['label'] == 'yes'


def test_missing_one_of_several_requested_actions_preserves_partial_fulfillment():
    value = observation('complete', 'absent')
    value['requirements'][1]['role'] = 'core'
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'partial'


def test_authorized_scene_change_is_preserved_but_unauthorized_loss_can_defeat_edit():
    value = observation()
    value['source_integrity']['state'] = 'material_deviation'
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'partial'
    value['source_integrity']['state'] = 'meaning_destroyed'
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'no'


def test_unknown_cannot_be_silently_counted_as_failure_or_success():
    result = apply_label_policy(observation('complete', 'unknown'), INSTRUCTION)
    assert result['label'] is None and result['possible_labels'] == ['partial', 'yes']
    result = apply_label_policy(observation('unknown', 'complete'), INSTRUCTION)
    assert result['label'] is None and result['possible_labels'] == ['no', 'partial', 'yes']


def test_unknown_resolves_only_when_it_cannot_change_label():
    value = observation('incomplete', 'unknown')
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'partial'
    value['target']['state'] = 'unknown'
    assert apply_label_policy(value, INSTRUCTION)['label'] is None
    value['source_integrity']['state'] = 'meaning_destroyed'
    assert apply_label_policy(value, INSTRUCTION)['label'] == 'no'


@pytest.mark.parametrize('damage', ['empty', 'quote', 'duplicate', 'no_core', 'overall_label', 'bad_state', 'no_evidence'])
def test_malformed_or_ungrounded_records_are_rejected(damage):
    value = observation()
    if damage == 'empty': value['requirements'] = []
    elif damage == 'quote': value['requirements'][0]['source_quote'] = 'invented requirement'
    elif damage == 'duplicate': value['requirements'][1]['id'] = value['requirements'][0]['id']
    elif damage == 'no_core': value['requirements'][0]['role'] = 'constraint'
    elif damage == 'overall_label': value['label'] = 'yes'
    elif damage == 'bad_state': value['target']['state'] = 'yes'
    elif damage == 'no_evidence': value['requirements'][0]['evidence'] = ' '
    with pytest.raises(ValueError): apply_label_policy(value, INSTRUCTION)


def test_one_call_contains_only_instruction_and_two_ordered_images_and_replays(tmp_path):
    evidence = {}
    for name in ('source_image', 'edited_image'):
        path = tmp_path / (name + '.png')
        Image.new('RGB', (4, 4), 'red').save(path)
        evidence[name] = str(path)
    requests = []

    class Engine:
        def generate(self, text, **kwargs):
            requests.append((text, kwargs))
            return {'parsed': observation(), 'finishReason': 'stop', 'completionTokens': 50}

    calls = DurableCalls(tmp_path / 'calls', lambda _: Engine(), identity={'model': 'mock'},
                         max_calls=1, max_completion_tokens=512)
    result = SingleCallEvidenceJudge(calls).judge(INSTRUCTION, evidence, max_tokens=512)
    assert result['label'] == 'yes' and calls.budget['calls'] == 1 and len(requests) == 1
    text, kwargs = requests[0]
    assert text.endswith('INPUT_JSON: {"instruction": "' + INSTRUCTION + '"}')
    assert [m.get('text') for m in kwargs['media_inputs'] if m['type'] == 'text'] == ['SOURCE image', 'EDITED image']
    assert [m['path'] for m in kwargs['media_inputs'] if m['type'] == 'image'] == list(evidence.values())
    assert 'label' not in kwargs['schema']['properties']

    def forbidden(_):
        raise AssertionError('Replay made a new call')
    replay = DurableCalls(tmp_path / 'calls', forbidden, identity={'model': 'mock'},
                          max_calls=1, max_completion_tokens=512)
    assert SingleCallEvidenceJudge(replay).judge(INSTRUCTION, evidence, max_tokens=512) == result


def test_paired_comparison_counts_regressions_and_unresolved_in_denominator():
    flat = {'cases': [{'case': 'a', 'id': 'a', 'reference': 'yes', 'prediction': 'partial'},
                      {'case': 'b', 'id': 'b', 'reference': 'no', 'prediction': 'no'}]}
    rows = deepcopy(flat['cases'])
    rows[0]['prediction'] = 'yes'; rows[1]['prediction'] = None
    paired = paired_comparison(flat, rows)
    assert paired['wins'] == ['a'] and paired['losses'] == ['b']
    assert paired['accuracy_difference'] == 0 and paired['mcnemar_exact_two_sided_p'] == 1
