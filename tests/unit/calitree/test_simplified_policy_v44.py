import numpy as np

from run.calitree_simplified_policy_v44 import feature_columns


def test_feature_simplification_excludes_held_observations_and_targets():
    names = ['meaning_progress_none_all', 'task_compound', 'judge_predicts_no', 'expert_0_predicts_yes']
    # On training rows columns 0/1 coincide, 2 is constant, 3 varies independently.
    matrix = np.asarray([[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]], dtype=np.float32)
    assert feature_columns(names, matrix, [0, 1, 2], 'dedup') == [0, 3]
    changed = matrix.copy()
    changed[3] = [0, 1, 1, 0]
    assert feature_columns(names, changed, [0, 1, 2], 'dedup') == [0, 3]
    assert feature_columns(names, matrix, [0, 1, 2], 'dedup_noexpert') == [0]
    assert feature_columns(names, matrix, [0, 1, 2], 'meaning') == [0, 1, 2, 3]
