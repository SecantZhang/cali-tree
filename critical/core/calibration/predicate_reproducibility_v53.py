"""Label-free cross-view predicate priors; no example lookup at inference."""
import math

import numpy as np


def reproducibility(primary, alternative, source_groups, minimum_sources=3):
    a, b = np.asarray(primary, dtype=bool), np.asarray(alternative, dtype=bool)
    if a.shape != b.shape or a.ndim != 2 or len(source_groups) != len(a):
        raise ValueError('Aligned Boolean evidence pairs required')
    scores = []
    for j in range(a.shape[1]):
        positive = a[:, j] | b[:, j]
        negative = ~a[:, j] | ~b[:, j]
        pos_sources = len({g for g, present in zip(source_groups, positive) if present})
        neg_sources = len({g for g, present in zip(source_groups, negative) if present})
        score = None
        if pos_sources >= minimum_sources and neg_sources >= minimum_sources:
            positive_agreement = float(np.sum(a[:, j] & b[:, j]) / np.sum(positive))
            negative_agreement = float(np.sum(~a[:, j] & ~b[:, j]) / np.sum(negative))
            score = (positive_agreement + negative_agreement) / 2
        scores.append({'score': score, 'positive_source_witnesses': pos_sources, 'negative_source_witnesses': neg_sources})
    return scores


def representative_columns(names, matrix, train, scores, reliable=False):
    groups = {}
    for i, name in enumerate(names):
        if name.startswith('expert_'):
            continue
        values = matrix[train, i]
        if np.all(values == values[0]):
            continue
        groups.setdefault(values.tobytes(), []).append(i)
    def rank(i):
        score = scores[i]['score']
        return (-(score if score is not None else .5), not names[i].startswith('meaning_'), i)
    return [min(indices, key=rank) if reliable else indices[0] for indices in groups.values()]


def prior_columns(names, scores, strength, scope='all', uniform=1):
    columns = []
    for i, name in enumerate(names):
        value = scores[i]['score']
        qualified = not name.startswith(('judge_', 'expert_', 'evidence_')) and (scope != 'meaning' or name.startswith('meaning_'))
        multiplicity = uniform if uniform > 1 else 1 + (math.floor(strength * value) if qualified and value is not None else 0)
        columns.extend([i] * multiplicity)
    return columns
