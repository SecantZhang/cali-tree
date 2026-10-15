from copy import deepcopy
import pytest

from run.calitree_semantic_transfer import (
    GROUPS, POLICY_SOURCE, LABELS, ObservableDNFCalibrator, evaluate,
    inference_case, predict_frozen, read, select_cases,
)


def test_balanced_sampling_excludes_sources_and_is_order_independent():
    candidates = [{'id': f'{k}-{i}', 'reference': label, 'group': f'{k}-{i}', 'task': str(i % 3)}
                  for k, label in enumerate(LABELS) for i in range(7)]
    excluded = {'0-0', '1-0', '2-0'}
    chosen = select_cases(candidates, excluded)
    assert chosen == select_cases(list(reversed(candidates)), excluded)
    assert len({c['group'] for c in chosen}) == 12
    assert not {c['group'] for c in chosen} & excluded
    assert [sum(c['reference'] == k for c in chosen) for k in LABELS] == [4, 4, 4]


def test_sampling_does_not_replace_with_sibling_or_relax_class_balance():
    candidates = [{'id': str(i), 'reference': label, 'group': label, 'task': 'x'}
                  for label in LABELS for i in range(10)]
    with pytest.raises(ValueError, match='Insufficient unseen'):
        select_cases(candidates, set())


def test_inference_input_whitelist_drops_reference_and_editor():
    case = dict(case='H01', id='ledger-only', instruction='Move it', evidence={'source_image': 'a', 'edited_image': 'b'},
                reference='yes', human_score=2, editing_model='secret', group='secret')
    clean = inference_case(case)
    assert set(clean) == {'case', 'id', 'instruction', 'evidence'}
    clean['evidence']['source_image'] = 'changed'
    assert case['evidence']['source_image'] == 'a'


@pytest.fixture
def saved_policies():
    if not (POLICY_SOURCE / 'results.json').exists():
        pytest.skip('Local experiment artifacts unavailable')
    return {g: read(POLICY_SOURCE / 'rules' / g / 'teacher_distilled/policy.json') for g in GROUPS}


def test_all_four_frozen_policies_predict_without_fit_or_mutation(monkeypatch, saved_policies):
    original = read(POLICY_SOURCE / 'results.json')
    records = [r['facts'] for r in original['groups']['G2']['teacher_distilled']['cases']]
    before = deepcopy([saved_policies, records])
    def forbidden(*args, **kwargs):
        raise AssertionError('A transfer benchmark must never fit')
    monkeypatch.setattr(ObservableDNFCalibrator, 'fit', forbidden)
    result = predict_frozen(saved_policies, records)
    assert set(result) == set(GROUPS)
    assert result['G2'] == [r['decision'] for r in original['groups']['G2']['teacher_distilled']['cases']]
    assert [saved_policies, records] == before


def test_missing_evidence_stays_in_denominator(saved_policies):
    predictions = predict_frozen(saved_policies, [None] * 12)
    cases = [dict(case=str(i), id=str(i), instruction='x', human_score=i % 3, reference=LABELS[i % 3]) for i in range(12)]
    evaluated = evaluate(cases, predictions)
    for arm in evaluated.values():
        assert arm['metrics']['correct'] == 0
        assert arm['metrics']['total'] == 12
        assert arm['class_metrics']['unresolved'] == 12


def test_scoring_labels_cannot_change_frozen_predictions(saved_policies):
    original = read(POLICY_SOURCE / 'results.json')['groups']['G2']['teacher_distilled']['cases']
    records = [r['facts'] for r in original]
    predictions = predict_frozen(saved_policies, records)
    before = deepcopy(predictions)
    cases = [dict(case=str(i), id=str(i), instruction='ignored by scoring', human_score=i % 3, reference=LABELS[i % 3]) for i in range(12)]
    evaluate(cases, predictions)
    for c in cases:
        c['reference'] = LABELS[(LABELS.index(c['reference']) + 1) % 3]
    evaluate(cases, predictions)
    assert predictions == before == predict_frozen(saved_policies, records)
