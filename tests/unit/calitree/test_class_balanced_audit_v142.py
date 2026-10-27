import numpy as np
import pytest

from run.verify_calitree_class_balanced_v142 import native_classifier_support


def test_independent_native_classifier_replays_leaf_order_scale_and_bias():
    native = {'features_info': {'float_features': [
        {'feature_index': 7, 'flat_feature_index': 1},
        {'feature_index': 3, 'flat_feature_index': 0}]},
        'scale_and_bias': [2., [.1, -.2, .3]],
        'oblivious_trees': [{'splits': [
            {'split_type': 'FloatFeature', 'float_feature_index': 7, 'border': .5},
            {'split_type': 'FloatFeature', 'float_feature_index': 3, 'border': .5}],
            'leaf_values': [0., 1., 2., 1., 3., 2., 4., 1., 0., 2., 0., 5.]}]}
    X = [[0., 0.], [0., 1.], [1., 0.], [1., 1.]]
    logits = np.asarray([[0., 1., 2.], [1., 3., 2.], [4., 1., 0.], [2., 0., 5.]])*2+[.1, -.2, .3]
    masses = np.exp(logits-logits.max(axis=1, keepdims=True))
    assert np.allclose(native_classifier_support(native, X), masses/masses.sum(axis=1, keepdims=True))


def test_independent_classifier_rejects_nonboolean_split_contract():
    native = {'features_info': {'float_features': [{'feature_index': 0, 'flat_feature_index': 0}]},
        'scale_and_bias': [1., [0., 0., 0.]], 'oblivious_trees': [{
        'splits': [{'split_type': 'FloatFeature', 'float_feature_index': 0, 'border': .25}],
        'leaf_values': [0.]*6}]}
    with pytest.raises(AssertionError):
        native_classifier_support(native, [[0.], [1.]])


def test_parallel_outer_fit_can_use_parent_created_by_inner_fit(tmp_path, monkeypatch):
    from critical.core.decision.artifacts import save_json, digest
    from run import calitree_class_balanced_v141 as experiment
    class FakeClassifier:
        def __init__(self, **kwargs):
            pass
        def fit(self, X, y, **kwargs):
            return self
        def predict(self, X):
            return np.asarray(X)[:, 0].astype(int)
        def predict_proba(self, X):
            return np.eye(3)[self.predict(X)]
        def save_model(self, path, **kwargs):
            from pathlib import Path
            Path(path).write_text('{}')
        def load_model(self, path):
            pass
    monkeypatch.setattr(experiment, 'CatBoostClassifier', FakeClassifier)
    X = np.asarray([[0.], [1.], [2.]])
    y = np.asarray([0, 1, 2]); old = tmp_path/'old'; old.mkdir()
    save_json(old/'teacher.json', {'contract': {'rows': [0, 1, 2], 'columns': ['flag'],
        'matrix_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist())}})
    out = tmp_path/'out'
    (out/'teachers/fold0/inner0').mkdir(parents=True)
    result = experiment.fit_teacher({'key': 'fold0', 'old': str(old), 'rows': [0, 1, 2], 'inner': None},
                                    ['flag'], X, y, out)
    assert result['retained'] and (out/'teachers/fold0/teacher.json').exists()
