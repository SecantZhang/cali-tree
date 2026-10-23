"""Sparse weighted semantic conditions, optionally including two-way ANDs."""
import warnings

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import PolynomialFeatures

from .base import Calibrator


class SemanticConjunctionPolicy(Calibrator):
    version = 'sparse-semantic-conjunction-policy-v50'

    def __init__(self, degree=1, C=1.):
        if degree not in (1, 2) or C <= 0:
            raise ValueError('Declared unary/binary semantic conditions and positive C required')
        self.degree, self.C = degree, C
        self.transform = PolynomialFeatures(degree=degree, interaction_only=True, include_bias=False)
        self.classes_ = np.asarray([0, 1, 2])

    def fit(self, X, y, *, sample_weight=None):
        values = np.asarray(X, dtype=np.float64)
        if not np.all((values == 0) | (values == 1)):
            raise ValueError('Only declared Boolean inputs may form conjunctions')
        matrix = self.transform.fit_transform(csr_matrix(values))
        self.heads, self.converged = [], True
        for label in self.classes_:
            head = LogisticRegression(solver='liblinear', penalty='l1', C=self.C, max_iter=3000,
                                      tol=1e-5, random_state=20261020)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                head.fit(matrix, np.asarray(y) == label, sample_weight=sample_weight)
            self.converged &= not any(issubclass(w.category, ConvergenceWarning) for w in caught)
            self.heads.append(head)
        return self

    def predict_proba(self, X):
        matrix = self.transform.transform(csr_matrix(np.asarray(X, dtype=np.float64)))
        probabilities = np.stack([h.predict_proba(matrix)[:, 1] for h in self.heads], axis=1)
        return probabilities / probabilities.sum(axis=1, keepdims=True)

    def predict(self, X):
        return [int(v) for v in np.argmax(self.predict_proba(X), axis=1)]

    def metadata(self):
        return {**super().metadata(), 'degree': self.degree, 'C': self.C, 'converged': self.converged,
                'expanded_feature_count': self.transform.n_output_features_,
                'nonzero_weights': [int(np.count_nonzero(h.coef_)) for h in self.heads]}
