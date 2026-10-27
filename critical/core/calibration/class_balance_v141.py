"""Training-only equal-class weights for the existing CatBoost architecture."""
import numpy as np

from .semantic_residual_v103 import SemanticResidual, corrected_support
from .rubric_score_v82 import log_support


def training_weights(y, *, groups=None, original=None, original_weight=1., balanced=True):
    """Normalize source/anchor weights, then give each observed grade equal mass.

    Group normalization is optional: the original main classifier uses equal
    row weights, whereas its residual uses equal source contributions before
    class reweighting. No evaluation labels or sampling enter this function.
    """
    labels = np.asarray(y)
    if (labels.ndim != 1 or not len(labels) or not np.all(np.isin(labels, (0, 1, 2))) or
            not np.isfinite(original_weight) or original_weight < 1):
        raise ValueError('Nonempty three-grade training labels and positive anchor weight required')
    weights = np.ones(len(labels), dtype=float)
    if groups is not None:
        groups = np.asarray(groups)
        if groups.shape != labels.shape:
            raise ValueError('Aligned source groups required')
        unique, counts = np.unique(groups, return_counts=True)
        sizes = dict(zip(unique, counts))
        weights /= np.asarray([sizes[g] for g in groups])
    if original is not None:
        original = np.asarray(original)
        if original.shape != labels.shape or original.dtype != bool:
            raise ValueError('Aligned Boolean original-case mask required')
        weights[original] *= original_weight
    if balanced:
        for grade in np.unique(labels):
            mask = labels == grade
            weights[mask] /= weights[mask].sum()
    weights /= weights.sum()
    return weights


def weight_receipt(y, weights):
    y, weights = np.asarray(y), np.asarray(weights)
    return {'rows': len(y), 'class_counts': [int(np.sum(y == k)) for k in range(3)],
            'class_weight_mass': [float(weights[y == k].sum()) for k in range(3)]}


def classification_metrics(rows, field='prediction'):
    """Keep invalid/unresolved predictions as errors, including in class recall."""
    if not rows:
        raise ValueError('Nonempty evaluation rows required')
    labels = np.asarray([r['reference'] for r in rows])
    predictions = np.asarray([r[field] for r in rows])
    if not np.all(np.isin(labels, (0, 1, 2))):
        raise ValueError('Three-grade references required')
    per_class = {}
    for grade, name in enumerate(('no', 'partial', 'yes')):
        actual = int(np.sum(labels == grade)); predicted = int(np.sum(predictions == grade))
        tp = int(np.sum((labels == grade) & (predictions == grade)))
        per_class[name] = {'correct': tp, 'total': actual, 'predicted': predicted,
            'recall': tp/actual if actual else None, 'precision': tp/predicted if predicted else 0.,
            'f1': 2*tp/(actual+predicted) if actual+predicted else 0.}
    recalls = [r['recall'] for r in per_class.values() if r['recall'] is not None]
    return {'correct': int(np.sum(labels == predictions)), 'total': len(rows),
        'accuracy': float(np.mean(labels == predictions)), 'balanced_accuracy': float(np.mean(recalls)),
        'macro_f1': float(np.mean([r['f1'] for r in per_class.values()])),
        'unresolved': int(np.sum(~np.isin(predictions, (0, 1, 2)))), 'per_class': per_class,
        'confusion_rows_reference_columns_prediction': [[int(np.sum((labels == i) & (predictions == j)))
            for j in range(3)] for i in range(3)]}


class ClassBalancedResidual(SemanticResidual):
    """The same residual trees; only fitting and strength-objective weights differ."""
    def fit(self, X, y, *, support, groups, protected_X, protected_y, protected_support, sample_weight=None):
        from catboost import CatBoostRegressor
        a, y, p = np.asarray(X, dtype=float), np.asarray(y), np.asarray(support, dtype=float)
        log_support(p)
        if (sample_weight is not None or a.shape != (len(y), len(self.names)) or
                p.shape != (len(y), 3) or not np.all(np.isfinite(a))):
            raise ValueError('Finite aligned residual fitting rows required')
        weights = training_weights(y, groups=groups)
        y = y.astype(int)
        self.model = CatBoostRegressor(loss_function='MultiRMSE', depth=self.depth, iterations=self.iterations,
            learning_rate=.05, l2_leaf_reg=10., random_seed=20261023, thread_count=2, verbose=False,
            allow_writing_files=False, bootstrap_type='No', random_strength=0., allow_const_label=True)
        self.model.fit(a, np.eye(3)[y]-p, sample_weight=weights*len(weights))
        delta = np.asarray(self.model.predict(a))
        px, py, pp = np.asarray(protected_X, dtype=float), np.asarray(protected_y, dtype=int), np.asarray(protected_support, dtype=float)
        log_support(pp)
        pd = np.asarray(self.model.predict(px)) if len(py) else np.empty((0, 3))
        self.trials = []
        for strength in (0., .25, .5, .75, 1.):
            fit_p = corrected_support(p, delta, strength)
            protected_p = corrected_support(pp, pd, strength)
            self.trials.append({'strength': strength,
                'retained': bool(np.all(np.argmax(protected_p, axis=1) == py)),
                'source_weighted_accuracy': float(weights @ (np.argmax(fit_p, axis=1) == y)),
                'squared_error': float(weights @ np.sum((fit_p-np.eye(3)[y])**2, axis=1))})
        passing = [t for t in self.trials if t['retained']]
        if not passing:
            raise ValueError('The original teacher fails actual protected retention')
        self.strength = min(passing, key=lambda t: (-t['source_weighted_accuracy'], t['squared_error'], t['strength']))['strength']
        self.weight_receipt = weight_receipt(y, weights)
        return self

    def metadata(self):
        return {**super().metadata(), 'training_weighting': 'Equal-source initial weights, normalized to equal total weight per observed training grade.',
                'strength_objective': 'The source_weighted_accuracy field uses those same class-balanced weights.',
                'training_weights': self.weight_receipt}
