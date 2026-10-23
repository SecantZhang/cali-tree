import numpy as np
import pytest

from critical.core.calibration.predicate_reproducibility_v53 import reproducibility, representative_columns, prior_columns


def test_reproducibility_balances_positive_negative_agreement_and_counts_sources():
    a = np.asarray([[1, 1], [1, 0], [0, 1], [0, 0]], dtype=np.float32)
    b = np.asarray([[1, 1], [0, 0], [0, 1], [0, 0]], dtype=np.float32)
    values = reproducibility(a, b, ['a', 'b', 'c', 'd'], minimum_sources=1)
    assert values[0]['score'] == pytest.approx((.5 + 2 / 3) / 2)
    assert values[1]['score'] == 1
    repeated = reproducibility(np.tile(a, (10, 1)), np.tile(b, (10, 1)), ['a', 'b', 'a', 'b'] * 10)
    assert all(v['score'] is None for v in repeated)


def test_reliable_representatives_preserve_training_vectors_without_reading_held_rows():
    X = np.asarray([[0, 0], [1, 1], [0, 0], [1, 0]], dtype=np.float32)
    scores = [{'score': .2}, {'score': .9}]
    names = ['outcome_all_true_all', 'meaning_progress_requested_endpoint_all']
    a = representative_columns(names, X, [0, 1, 2], scores, reliable=False)
    b = representative_columns(names, X, [0, 1, 2], scores, reliable=True)
    assert a == [0] and b == [1]
    assert np.array_equal(X[[0, 1, 2]][:, a], X[[0, 1, 2]][:, b])
    changed = X.copy()
    changed[3] = [0, 1]
    assert representative_columns(names, changed, [0, 1, 2], scores, reliable=True) == b


def test_prior_sampling_does_not_treat_cached_regular_labels_as_measured_reliability():
    names = ['meaning_progress_none_all', 'task_compound', 'judge_predicts_no']
    scores = [{'score': 1.}, {'score': None}, {'score': 1.}]
    assert prior_columns(names, scores, 4) == [0, 0, 0, 0, 0, 1, 2]
