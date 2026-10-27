"""Small weighted semantic trees correcting a frozen human-grade score.

The residual predicts label frequencies, not physical truth or correctness
confidence. All source groups and protected rows constrain fitting only.
"""
import numpy as np

from .base import Calibrator
from .rubric_score_v82 import log_support


def corrected_support(support, delta, strength):
    p = np.asarray(support, dtype=float); log_support(p)
    d = np.asarray(delta, dtype=float)
    if d.shape != p.shape or not np.all(np.isfinite(d)) or not 0 <= strength <= 1:
        raise ValueError('Aligned finite semantic residual required')
    result = np.maximum(p+strength*d, 1e-9)
    return result/result.sum(axis=1, keepdims=True)


class SemanticResidual(Calibrator):
    version = 'source-held-semantic-residual-v103'

    def __init__(self, names, *, depth=2, iterations=128):
        if not names or len(set(names)) != len(names) or depth not in (2, 3) or iterations < 1:
            raise ValueError('Named small semantic tree required')
        self.names, self.depth, self.iterations = list(names), depth, iterations

    def fit(self, X, y, *, support, groups, protected_X, protected_y, protected_support, sample_weight=None):
        from catboost import CatBoostRegressor
        a = np.asarray(X, dtype=float); y = np.asarray(y); p = np.asarray(support, dtype=float); log_support(p)
        if (sample_weight is not None or a.shape != (len(y), len(self.names)) or len(groups) != len(y) or
                not np.all(np.isfinite(a)) or not np.all(np.isin(y, (0, 1, 2)))):
            raise ValueError('Finite aligned source-group fitting rows required')
        y = y.astype(int); unique, counts = np.unique(groups, return_counts=True); sizes = dict(zip(unique, counts))
        weights = np.asarray([1./sizes[g] for g in groups]); weights /= weights.sum()
        target = np.eye(3)[y]-p
        self.model = CatBoostRegressor(loss_function='MultiRMSE', depth=self.depth, iterations=self.iterations,
            learning_rate=.05, l2_leaf_reg=10., random_seed=20261023, thread_count=2, verbose=False,
            allow_writing_files=False, bootstrap_type='No', random_strength=0., allow_const_label=True)
        self.model.fit(a, target, sample_weight=weights*len(weights))
        delta = np.asarray(self.model.predict(a)); px = np.asarray(protected_X, dtype=float); py = np.asarray(protected_y, dtype=int)
        pp = np.asarray(protected_support, dtype=float); log_support(pp)
        pd = np.asarray(self.model.predict(px)) if len(py) else np.empty((0, 3))
        self.trials = []
        for strength in (0., .25, .5, .75, 1.):
            fit_p = corrected_support(p, delta, strength); protected_p = corrected_support(pp, pd, strength)
            self.trials.append({'strength': strength, 'retained': bool(np.all(np.argmax(protected_p, axis=1) == py)),
                'source_weighted_accuracy': float(weights @ (np.argmax(fit_p, axis=1) == y)),
                'squared_error': float(weights @ np.sum((fit_p-np.eye(3)[y])**2, axis=1))})
        passing = [t for t in self.trials if t['retained']]
        if not passing:
            raise ValueError('The original teacher fails actual protected retention')
        self.strength = min(passing, key=lambda t: (-t['source_weighted_accuracy'], t['squared_error'], t['strength']))['strength']
        return self

    def predict_proba(self, X, *, support):
        return corrected_support(support, self.model.predict(np.asarray(X, dtype=float)), self.strength)

    def predict(self, X, *, support):
        return np.argmax(self.predict_proba(X, support=support), axis=1).tolist()

    def metadata(self):
        return {'version': self.version, 'features': self.names, 'depth': self.depth, 'iterations': self.iterations,
                'strength': self.strength, 'strength_trials': self.trials,
                'equation': 'normalize(max(teacher support + strength * small semantic-tree residual,1e-9)); choose largest class mass.',
                'limit': 'Statistical human-grade score correction, not a physical certificate or calibrated correctness probability.'}

    def artifact(self, descriptions):
        return {**self.metadata(), 'feature_descriptions': {n: descriptions[n] for n in self.names}}
