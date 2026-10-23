"""Learn a semantic expert router from source-excluded expert predictions.

Source and protected/legacy membership are fitting metadata only. Inference
accepts Boolean semantic features, with no identity or example lookup interface.
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedGroupKFold

from .base import Calibrator
from .boundary_experts_v55 import BoundaryExperts

VERSION = 'source-held-semantic-mixture-v61'
MEMBERS = ('legacy_boundary', 'expanded_semantic', 'explanation')
THRESHOLDS = (.25, .5, .65, .8, .95)


def varying_columns(names, matrix, rows):
    selected, seen = [], set()
    for i, name in enumerate(names):
        if name.startswith('expert_'):
            continue
        v = matrix[rows, i]
        if np.all(v == v[0]):
            continue
        signature = v.tobytes()
        if signature not in seen:
            seen.add(signature)
            selected.append(i)
    if not selected:
        raise ValueError('No varying declared inputs')
    return selected


def mixed_features(names, matrix, cube):
    """Fixed Boolean support bins/relative comparisons, never calibrated truth."""
    matrix, cube = np.asarray(matrix), np.asarray(cube)
    if cube.shape != (len(matrix), 3, 3) or np.any(~np.isfinite(cube)) or np.any(cube < 0) or not np.allclose(cube.sum(axis=2), 1.):
        raise ValueError('Three normalized class-support vectors required')
    if not np.all((matrix == 0) | (matrix == 1)):
        raise ValueError('Declared Boolean inputs required')
    raw_columns = [i for i, name in enumerate(names) if not name.startswith('expert_')]
    columns, extra_names = [], []
    tops = np.argmax(cube, axis=2)
    for member, name in enumerate(MEMBERS):
        for label in range(3):
            extra_names.append(f'mixture_{name}_predicts_{label}')
            columns.append(tops[:, member] == label)
            for threshold in THRESHOLDS:
                extra_names.append(f'mixture_{name}_class_{label}_support_ge_{threshold}')
                columns.append(cube[:, member, label] >= threshold)
        ordered = np.sort(cube[:, member], axis=1)
        margin = ordered[:, -1] - ordered[:, -2]
        for threshold in (.1, .25, .5, .75):
            extra_names.append(f'mixture_{name}_margin_ge_{threshold}')
            columns.append(margin >= threshold)
    for a, b in ((0, 1), (0, 2), (1, 2)):
        for label in range(3):
            extra_names.append(f'mixture_{MEMBERS[a]}_class_{label}_stronger_than_{MEMBERS[b]}')
            columns.append(cube[:, a, label] > cube[:, b, label])
    for label in range(3):
        extra_names.append(f'mixture_all_predict_{label}')
        columns.append(np.all(tops == label, axis=1))
    extra = np.stack(columns, axis=1).astype(np.float32)
    return [names[i] for i in raw_columns] + extra_names, np.concatenate([matrix[:, raw_columns], extra], axis=1)


class SemanticPanel(Calibrator):
    version = VERSION + '-panel'

    def __init__(self, feature_names, *, trees=128, inner_folds=5):
        self.feature_names, self.trees, self.inner_folds = list(feature_names), trees, inner_folds
        self.classes_ = np.asarray([0, 1, 2])

    def _fit_members(self, X, y, rows, original, legacy):
        result = []
        for name in MEMBERS:
            selected = [i for i in rows if name != 'legacy_boundary' or legacy[i]]
            eligible = [i for i, n in enumerate(self.feature_names) if
                        (name != 'legacy_boundary' or not n.startswith(('intent_', 'rationale_'))) and
                        (name != 'explanation' or n.startswith(('intent_', 'rationale_', 'task_', 'judge_')) or n == 'evidence_missing')]
            names, matrix = [self.feature_names[i] for i in eligible], X[:, eligible]
            cols = varying_columns(names, matrix, selected)
            if set(y[selected]) != {0, 1, 2}:
                raise ValueError('All classes required in every fitting expert')
            weights = np.asarray([5. if original[i] and name != 'legacy_boundary' else 1. for i in selected])
            if name == 'legacy_boundary':
                model = BoundaryExperts(balanced=True)
                # Production uses the frozen 128-tree definition; tiny test
                # panels may reduce the number without changing its objective.
                if self.trees != 128:
                    model.forest = lambda: RandomForestClassifier(n_estimators=self.trees, bootstrap=False,
                        min_samples_leaf=1, max_features='sqrt', class_weight='balanced', random_state=20261020, n_jobs=2)
                family = 'boundary'
            else:
                model = RandomForestClassifier(n_estimators=self.trees, bootstrap=False, min_samples_leaf=1,
                            max_features='sqrt', random_state=20261020, n_jobs=2)
                family = 'forest'
            model.fit(matrix[selected][:, cols], y[selected], sample_weight=weights)
            result.append({'name': name, 'columns': [eligible[i] for i in cols], 'family': family, 'model': model,
                           'fit_rows': list(selected)})
        return result

    @staticmethod
    def _predict_members(members, X):
        return np.stack([m['model'].predict_proba(X[:, m['columns']], 'minimum') if m['family'] == 'boundary'
                         else m['model'].predict_proba(X[:, m['columns']]) for m in members], axis=1)

    def fit(self, X, y, *, groups, original, legacy, sample_weight=None):
        if sample_weight is not None:
            raise ValueError('Panel uses its declared protected-example weights')
        X, y, groups = np.asarray(X), np.asarray(y), np.asarray(groups)
        original, legacy = np.asarray(original, dtype=bool), np.asarray(legacy, dtype=bool)
        if not np.all((X == 0) | (X == 1)) or len({len(X), len(y), len(groups), len(original), len(legacy)}) != 1:
            raise ValueError('Aligned Boolean fitting rows and metadata required')
        splitter = StratifiedGroupKFold(n_splits=self.inner_folds, shuffle=True, random_state=20261021)
        self.oof = np.full((len(X), 3, 3), np.nan)
        self.inner_trace = []
        for train, held in splitter.split(X, y, groups):
            assert not set(groups[train]) & set(groups[held])
            members = self._fit_members(X, y, train, original, legacy)
            self.oof[held] = self._predict_members(members, X[held])
            self.inner_trace.append({'train_rows': [int(i) for i in train], 'held_rows': [int(i) for i in held],
                                     'training_sources': sorted(set(groups[train])), 'held_sources': sorted(set(groups[held])),
                                     'member_fit_rows': {m['name']: [int(i) for i in m['fit_rows']] for m in members}})
        assert np.all(np.isfinite(self.oof))
        self.members = self._fit_members(X, y, list(range(len(X))), original, legacy)
        return self

    def expert_supports(self, X):
        return self._predict_members(self.members, np.asarray(X))

    def predict_proba(self, X):
        return self.expert_supports(X).mean(axis=1)

    def predict(self, X):
        return [int(v) for v in np.argmax(self.predict_proba(X), axis=1)]


class SourceHeldMixture(Calibrator):
    version = VERSION

    def __init__(self, feature_names, *, family='forest', trees=128, inner_folds=5):
        if family not in ('forest', 'balanced_forest', 'boundary'):
            raise ValueError('Unknown mixture router')
        self.feature_names, self.family, self.trees, self.inner_folds = list(feature_names), family, trees, inner_folds
        self.classes_ = np.asarray([0, 1, 2])

    def fit(self, X, y, *, groups, original, legacy, sample_weight=None):
        if sample_weight is not None:
            raise ValueError('Mixture chooses protected weight using original accuracy only')
        panel = SemanticPanel(self.feature_names, trees=self.trees, inner_folds=self.inner_folds)
        panel.fit(X, y, groups=groups, original=original, legacy=legacy)
        return self.fit_from_panel(panel, X, y, original=original)

    def fit_from_panel(self, panel, X, y, *, original):
        X, y, original = np.asarray(X), np.asarray(y), np.asarray(original, dtype=bool)
        self.panel = panel
        self.meta_names, oof_matrix = mixed_features(self.feature_names, X, panel.oof)
        # The original examples are explicitly protected training data. Their
        # final-panel feature view is added to OOF views to enforce the actual
        # inference path, with no per-case override or held-source labels.
        _, protected = mixed_features(self.feature_names, X[original], panel.expert_supports(X[original]))
        matrix = np.concatenate([oof_matrix, protected], axis=0)
        target = np.concatenate([y, y[original]])
        self.columns = varying_columns(self.meta_names, matrix, list(range(len(matrix))))
        matrix = matrix[:, self.columns]
        for weight in (1., 5., 25.):
            weights = np.concatenate([np.where(original, weight, 1.), np.full(original.sum(), weight)])
            if self.family == 'boundary':
                model = BoundaryExperts(balanced=True)
                if self.trees != 128:
                    model.forest = lambda: RandomForestClassifier(n_estimators=self.trees, bootstrap=False,
                        min_samples_leaf=1, max_features='sqrt', class_weight='balanced', random_state=20261020, n_jobs=2)
            else:
                model = RandomForestClassifier(n_estimators=self.trees, bootstrap=False, min_samples_leaf=1,
                    max_features='sqrt', class_weight='balanced' if self.family == 'balanced_forest' else None,
                    random_state=20261020, n_jobs=2)
            model.fit(matrix, target, sample_weight=weights)
            p = (model.predict_proba(protected[:, self.columns], 'minimum') if self.family == 'boundary'
                 else model.predict_proba(protected[:, self.columns]))
            correct = int(np.sum(np.argmax(p, axis=1) == y[original]))
            self.model, self.protected_weight, self.protected_correct = model, weight, correct
            if correct == int(original.sum()):
                break
        return self

    def predict_proba(self, X):
        X = np.asarray(X)
        _, matrix = mixed_features(self.feature_names, X, self.panel.expert_supports(X))
        return (self.model.predict_proba(matrix[:, self.columns], 'minimum') if self.family == 'boundary'
                else self.model.predict_proba(matrix[:, self.columns]))

    def predict(self, X):
        return [int(v) for v in np.argmax(self.predict_proba(X), axis=1)]
