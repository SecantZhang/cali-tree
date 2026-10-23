import inspect

import numpy as np
import pytest

from critical.core.calibration.source_held_mixture_v61 import SemanticPanel, SourceHeldMixture, mixed_features


def test_support_bins_and_comparisons_are_closed_booleans_with_explicit_ties():
    cube = np.asarray([[[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[1/3] * 3] * 3])
    names, X = mixed_features(['meaning_progress_none_all', 'expert_0_predicts_no'], np.ones((2, 2)), cube)
    assert 'expert_0_predicts_no' not in names
    assert set(np.unique(X)) <= {0, 1}
    flags = dict(zip(names, X[1]))
    assert flags['mixture_all_predict_0']
    assert flags['mixture_legacy_boundary_class_0_support_ge_0.25']
    assert not flags['mixture_legacy_boundary_class_0_support_ge_0.5']
    assert not flags['mixture_legacy_boundary_class_0_stronger_than_expanded_semantic']


@pytest.fixture(scope='module')
def fitted_panel():
    rng = np.random.RandomState(8)
    X = np.asarray([[a, b, int(rng.randint(2)), int(rng.randint(2))]
                    for g in range(12) for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))], dtype=np.float32)
    y = np.asarray([0 if not r[0] else 1 if not r[1] else 2 for r in X])
    groups = np.repeat(np.arange(12).astype(str), 4)
    original, legacy = np.arange(len(X)) < 8, np.arange(len(X)) < 32
    names = ['meaning_progress_none_all', 'task_outcome_attribute', 'rationale_completion_unnegated', 'judge_predicts_no']
    panel = SemanticPanel(names, trees=8, inner_folds=3).fit(X, y, groups=groups, original=original, legacy=legacy)
    return panel, X, y, groups, original, legacy, names


def test_every_oof_row_and_all_expert_members_exclude_its_entire_source(fitted_panel):
    panel, X, y, groups, original, legacy, _ = fitted_panel
    covered = []
    for fold in panel.inner_trace:
        assert not set(fold['training_sources']) & set(fold['held_sources'])
        for name, rows in fold['member_fit_rows'].items():
            assert set(rows) <= set(fold['train_rows'])
            assert not set(groups[rows]) & set(fold['held_sources'])
            if name == 'legacy_boundary':
                assert all(legacy[rows])
        covered += fold['held_rows']
    assert sorted(covered) == list(range(len(X)))
    assert panel.oof.shape == (len(X), 3, 3) and np.all(np.isfinite(panel.oof))


@pytest.mark.parametrize('family', ['forest', 'balanced_forest', 'boundary'])
def test_actual_final_prediction_retains_originals_without_identity_input(fitted_panel, family):
    panel, X, y, _, original, _, names = fitted_panel
    model = SourceHeldMixture(names, family=family, trees=8, inner_folds=3).fit_from_panel(panel, X, y, original=original)
    assert model.protected_correct == int(original.sum())
    assert model.predict(X[original]) == [int(v) for v in y[original]]
    assert list(inspect.signature(model.predict).parameters) == ['X']
    assert model.protected_weight in (1., 5., 25.)
