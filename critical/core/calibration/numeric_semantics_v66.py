"""Learn thresholds on declared relative visual scores, preserving local labels."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from .base import Calibrator
from .boundary_experts_v55 import BoundaryExperts
from .evidence_coverage_v20 import FEATURES
from .judge_semantics_v60 import SPECS as LANGUAGE
VISUAL_SCORES = ('global_preservation', 'patch_preservation_min', 'patch_preservation_q25', 'patch_preservation_median',
                 'target_match', 'target_source', 'target_edited', 'goal_global_source', 'goal_global_edited',
                 'goal_patch_source', 'goal_patch_edited', 'goal_global_delta', 'goal_patch_delta',
                 'property_delta_min', 'property_delta_mean', 'property_delta_max', 'target_source_margin',
                 'property_margin_source', 'property_margin_edited')
TYPES = ('axis', 'proximity', 'motion')
SPATIAL_SCORES = tuple(f'spatial_{kind}_{stat}' for kind in TYPES for stat in ('source_margin_min', 'edited_margin_min', 'delta_min', 'delta_mean')) + ('spatial_grounding_min', 'spatial_grounding_margin_min')
NUMERIC = {'score_' + name for name in (*VISUAL_SCORES, *SPATIAL_SCORES)}
BOOLEAN = set(FEATURES) | set(LANGUAGE) | {'evidence_missing', 'vision_available', 'vision_property_probe_available'}
BOOLEAN |= {'judge_predicts_' + name for name in ('unresolved', 'no', 'partial', 'yes')}
BOOLEAN |= {'spatial_' + kind + '_available' for kind in TYPES}


class NumericSemanticPolicy(Calibrator):
    version = 'continuous-relative-semantic-policy-v66'

    def __init__(self, feature_names, *, family='forest', iterations=1200):
        if family not in ('forest', 'boundary', 'boost') or not set(feature_names) <= NUMERIC | BOOLEAN:
            raise ValueError('Declared semantic fields and supported family required')
        self.feature_names, self.family, self.iterations = list(feature_names), family, iterations
        self.classes_ = np.asarray([0, 1, 2])

    def validate(self, X):
        X = np.asarray(X)
        if X.ndim != 2 or X.shape[1] != len(self.feature_names) or not np.isfinite(X).all():
            raise ValueError('Aligned finite semantic values required')
        for i, name in enumerate(self.feature_names):
            if name in BOOLEAN and not np.all((X[:, i] == 0) | (X[:, i] == 1)):
                raise ValueError('Boolean semantic field changed type')
            limit = 4.000001 if name in {'score_property_delta_min', 'score_property_delta_mean', 'score_property_delta_max'} else 2.000001
            if name in NUMERIC and np.any(np.abs(X[:, i]) > limit):
                raise ValueError('Relative comparison score outside declared bounds')
        return X

    def fit(self, X, y, *, original, sample_weight=None):
        if sample_weight is not None:
            raise ValueError('Original weight selected by training retention only')
        X, y, original = self.validate(X), np.asarray(y), np.asarray(original, dtype=bool)
        self.weight_trials = []
        for weight in (1., 5., 25.):
            weights = np.where(original, weight, 1.)
            if self.family == 'forest':
                model = RandomForestClassifier(n_estimators=128, bootstrap=False, min_samples_leaf=1, max_features='sqrt', random_state=20261020, n_jobs=2)
            elif self.family == 'boundary':
                model = BoundaryExperts(balanced=True)
            else:
                from catboost import CatBoostClassifier
                model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=self.iterations, learning_rate=.05,
                    l2_leaf_reg=3., bootstrap_type='No', random_strength=0., random_seed=20261021, thread_count=2,
                    verbose=False, allow_writing_files=False)
            self.model = model.fit(X, y, sample_weight=weights)
            correct = int(np.sum(np.argmax(self.predict_proba(X[original]), axis=1) == y[original]))
            self.weight_trials.append({'weight': weight, 'original_correct': correct})
            self.original_weight, self.original_correct = weight, correct
            if correct == int(original.sum()):
                break
        return self

    def predict_proba(self, X):
        X = self.validate(X)
        return self.model.predict_proba(X, 'minimum') if self.family == 'boundary' else self.model.predict_proba(X)

    def predict(self, X):
        return [int(value) for value in np.argmax(self.predict_proba(X), axis=1)]
