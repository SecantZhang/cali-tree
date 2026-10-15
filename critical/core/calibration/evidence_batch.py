"""Regularized batch calibration of cached, instruction-grounded evidence.

The learner consumes only instruction/evidence records and training labels. It
never consumes images, source IDs, task categories, human means, or test labels.
The portable artifact contains vocabulary, scaling and coefficients, not pickle.
"""
from copy import deepcopy

import numpy as np

from .base import Calibrator
from ..decision.artifacts import digest
from ..decision.single_call import (
    INTEGRITY_STATES, STATES, TARGET_STATES, apply_label_policy, validate_observation,
)


LABELS = ('no', 'partial', 'yes')
VERSION = 'evidence-text-logistic-v1'
TEXT_CONFIG = {'ngram_range': (1, 2), 'min_df': 2, 'max_features': 256,
               'token_pattern': r'(?u)\b[a-zA-Z][a-zA-Z]+\b', 'sublinear_tf': True}
FEATURE_NAMES = (
    tuple('target:' + s for s in TARGET_STATES)
    + tuple('integrity:' + s for s in INTEGRITY_STATES)
    + tuple(role + ':' + s for role in ('core', 'constraint') for s in STATES)
    + ('core_count', 'constraint_count')
)


def evidence_features(record):
    """Explicit whitelist prevents reference labels and dataset identity leaking."""
    if set(record) != {'instruction', 'observations'}:
        raise ValueError('Calibration inputs contain only instruction and observations')
    obs = validate_observation(record['observations'], record['instruction'])
    reqs = obs['requirements']
    numbers = [float(obs['target']['state'] == s) for s in TARGET_STATES]
    numbers += [float(obs['source_integrity']['state'] == s) for s in INTEGRITY_STATES]
    for role in ('core', 'constraint'):
        selected = [r for r in reqs if r['role'] == role]
        numbers += [sum(r['state'] == state for r in selected) / max(1, len(selected)) for state in STATES]
    numbers += [sum(r['role'] == role for r in reqs) / 6 for role in ('core', 'constraint')]
    text = '\n'.join([obs['instruction_scope'], obs['target']['evidence'], obs['source_integrity']['evidence']]
                     + [r['question'] + ' ' + r['evidence'] for r in reqs])
    return numbers, text


class EvidenceBatchCalibrator(Calibrator):
    """Multinomial L2 model; missing evidence and decisive No remain protected."""
    version = VERSION

    def __init__(self, *, regularization=1.0):
        if not np.isfinite(regularization) or regularization <= 0:
            raise ValueError('Positive finite regularization C required')
        self.regularization = float(regularization)
        self._artifact = None

    def fit(self, X, y, *, sample_weight=None):
        from scipy.sparse import csr_matrix, hstack
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        records, targets = list(X), list(y)
        if len(records) != len(targets) or not records or set(targets) != {0, 1, 2}:
            raise ValueError('Matched training rows covering all three ordinal classes required')
        features = [evidence_features(r) for r in records]
        numeric = np.asarray([f[0] for f in features], dtype=float)
        mean = numeric.mean(axis=0); scale = numeric.std(axis=0)
        scale[scale == 0] = 1
        vectorizer = TfidfVectorizer(**TEXT_CONFIG)
        try:
            text = vectorizer.fit_transform([f[1] for f in features])
        except ValueError as exc:
            if not any(s in str(exc).lower() for s in ('empty vocabulary', 'no terms remain', 'max_df corresponds')):
                raise
            # Small synthetic/degenerate batches can still use structured evidence.
            vectorizer = None; text = csr_matrix((len(records), 0))
        matrix = hstack([csr_matrix((numeric-mean)/scale), text], format='csr')
        model = LogisticRegression(C=self.regularization, solver='lbfgs', max_iter=2000,
                                   class_weight='balanced', random_state=20261013)
        model.fit(matrix, targets, sample_weight=sample_weight)
        self._artifact = {
            'version': VERSION, 'regularization': self.regularization,
            'labels': list(LABELS), 'classes': [int(v) for v in model.classes_],
            'feature_names': list(FEATURE_NAMES), 'text_config': {**TEXT_CONFIG, 'ngram_range': [1, 2]},
            'mean': mean.tolist(), 'scale': scale.tolist(),
            'vocabulary': {k: int(v) for k, v in vectorizer.vocabulary_.items()} if vectorizer is not None else {},
            'idf': vectorizer.idf_.tolist() if vectorizer is not None else [],
            'coef': model.coef_.tolist(), 'intercept': model.intercept_.tolist(),
            'training_rows': len(records), 'training_ref': digest({'X': records, 'y': targets}),
            'guards': 'Keep unresolved evidence unresolved and fixed-policy No as No; calibrate other resolved records.',
        }
        return self

    def _probabilities(self, X):
        from scipy.sparse import csr_matrix, hstack
        from sklearn.feature_extraction.text import TfidfVectorizer

        if self._artifact is None:
            raise RuntimeError('Fit or restore the calibrator before prediction')
        a = self._artifact
        rows = [evidence_features(r) for r in X]
        if not rows: return np.empty((0, 3))
        numeric = np.asarray([r[0] for r in rows], dtype=float)
        if a['vocabulary']:
            vectorizer = TfidfVectorizer(**TEXT_CONFIG, vocabulary=a['vocabulary'])
            vectorizer.idf_ = np.asarray(a['idf'])
            text = vectorizer.transform([r[1] for r in rows])
        else: text = csr_matrix((len(rows), 0))
        matrix = hstack([csr_matrix((numeric-np.asarray(a['mean']))/np.asarray(a['scale'])), text], format='csr')
        logits = np.asarray(matrix @ np.asarray(a['coef']).T) + np.asarray(a['intercept'])
        exp = np.exp(logits-logits.max(axis=1, keepdims=True))
        return exp/exp.sum(axis=1, keepdims=True)

    def predict_records(self, X):
        records = list(X)
        probabilities = self._probabilities(records)
        result = []
        for record, probs in zip(records, probabilities):
            original = apply_label_policy(record['observations'], record['instruction'])
            label = LABELS[int(np.argmax(probs))]
            guard = None
            if original['label'] is None:
                label, guard = None, 'unresolved_evidence'
            elif original['label'] == 'no':
                label, guard = 'no', 'fixed_policy_no'
            result.append({'label': label, 'probabilities': dict(zip(LABELS, map(float, probs))),
                           'guard': guard, 'version': VERSION})
        return result

    def predict(self, X):
        # Ordinal class outputs honor the existing Calibrator interface. NaN marks
        # unresolved observations; callers needing JSON use predict_records().
        return [float(LABELS.index(r['label'])) if r['label'] is not None else float('nan')
                for r in self.predict_records(X)]

    def metadata(self):
        if self._artifact is None: return {'version': VERSION, 'regularization': self.regularization}
        return deepcopy(self._artifact)

    @classmethod
    def restore(cls, artifact):
        a = deepcopy(artifact)
        if (a.get('version') != VERSION or a.get('labels') != list(LABELS)
                or a.get('classes') != [0, 1, 2] or a.get('feature_names') != list(FEATURE_NAMES)
                or a.get('text_config') != {**TEXT_CONFIG, 'ngram_range': [1, 2]}):
            raise ValueError('Unsupported calibration feature contract')
        n = len(FEATURE_NAMES); v = len(a['vocabulary'])
        arrays = [np.asarray(a[k], dtype=float) for k in ('mean', 'scale', 'coef', 'intercept', 'idf')]
        if ([x.shape for x in arrays] != [(n,), (n,), (3, n+v), (3,), (v,)]
                or not all(np.isfinite(x).all() for x in arrays)
                or not (arrays[1] > 0).all()
                or set(a['vocabulary'].values()) != set(range(v))):
            raise ValueError('Invalid calibration coefficient dimensions or values')
        model = cls(regularization=a['regularization']); model._artifact = a
        return model


def select_and_fit(records, targets, *, seed=20261013):
    """Three-fold selection on calibration data only; no evaluation argument."""
    from sklearn.model_selection import StratifiedKFold

    records, targets = list(records), list(targets)
    if len(records) != len(targets) or any(targets.count(label) < 3 for label in range(3)):
        raise ValueError('At least three calibration records per class required for three-fold selection')
    folds = list(StratifiedKFold(n_splits=3, shuffle=True, random_state=seed).split(records, targets))
    candidates = []
    for c in (.1, 1., 10.):
        predictions = [None] * len(records)
        for train, validation in folds:
            model = EvidenceBatchCalibrator(regularization=c).fit(
                [records[i] for i in train], [targets[i] for i in train])
            values = model.predict_records([records[i] for i in validation])
            for i, value in zip(validation, values): predictions[i] = value['label']
        recalls = [sum(predictions[i] == LABELS[label] for i, y in enumerate(targets) if y == label)
                   / sum(y == label for y in targets) for label in range(3)]
        candidates.append({'regularization': c, 'macro_recall': sum(recalls)/3,
                           'per_class_recall': recalls, 'out_of_fold_predictions': predictions})
    best = max(candidates, key=lambda row: (row['macro_recall'], -row['regularization']))
    model = EvidenceBatchCalibrator(regularization=best['regularization']).fit(records, targets)
    return model, {'folds': [{'train': a.tolist(), 'validation': b.tolist()} for a, b in folds],
                   'candidates': candidates, 'selected_regularization': best['regularization'],
                   'note': 'Calibration-only model-selection diagnostic, not independent test accuracy.'}
