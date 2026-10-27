import numpy as np

from run import calitree_semantic_context_projection_v171 as projection


def test_prior_locked_fitting_local_fields_match_serving_and_do_not_mutate_parent(monkeypatch):
    names = ['meaning_available', 'local_progress_witness']
    d = {'names': names, 'old_names': [], 'raw': None, 'semantic': None,
         'regular': np.array([0, 1]), 'sol': np.array([-1, -1]), 'valid': np.array([True, True])}
    T = np.array([[1., 1.], [1., 1.]])
    a = {'folder': 'fixture', 'full': np.array([[1., 0.], [1., 1.]]), 'T': T,
         'oof': np.array([[.6, .3, .1], [.3, .6, .1]]), 'genuine': np.array([True, True])}
    monkeypatch.setattr(projection, 'baseline_predictions', lambda *args: (np.array([0, 1]), np.array([True, False])))
    actual, fitting, report = projection.project_context(d, a, names)
    assert fitting.tolist() == actual.tolist() == [[True, False], [True, True]]
    assert T.tolist() == [[1., 1.], [1., 1.]]  # Frozen parent inputs were not changed.
    assert report['changed_fitting_rows'] == report['changed_fitting_indicators'] == 1
