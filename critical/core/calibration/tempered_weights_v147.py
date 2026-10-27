"""Moderate inverse-frequency weighting, between row-equal and class-equal."""
import numpy as np


def weights(y, exponent, original, multiplier=1.):
    y, original = np.asarray(y), np.asarray(original)
    if (y.ndim != 1 or not len(y) or not np.all(np.isin(y, (0, 1, 2))) or
            original.shape != y.shape or original.dtype != bool or
            exponent not in (0., .25, .5, .75, 1.) or multiplier not in (1., 5., 25.)):
        raise ValueError('Known weighting exponent, training grades and original mask required')
    w = np.where(original, multiplier, 1.)
    initial = w.copy()
    for grade in np.unique(y):
        mask = y == grade
        w[mask] /= initial[mask].sum()**exponent
    return w/w.sum()
