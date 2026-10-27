"""Share equivalent semantic feature combinations across boosted trees.

Trees testing the same named predicates in different orders represent functions
on the same Boolean cube. Align their leaf coordinates, sum their class-score
tables, and store only exactly nonzero leaves. No labels or cases enter merging.
"""
from collections import defaultdict
import math

import numpy as np

from ..decision.artifacts import digest

VERSION = 'equivalent-semantic-factor-merge-v175'


def canonical_table(tree):
    features = tree['features']
    if len(features) != len(set(features)) or len(features) > 8:
        raise ValueError('Distinct Boolean tests, depth at most eight, required')
    values = np.asarray(tree['values'], dtype=float)
    if values.shape != (3*(1 << len(features)),) or not np.all(np.isfinite(values)):
        raise ValueError('Finite three-class leaf table required')
    ordered = tuple(sorted(features))
    positions = {feature: i for i, feature in enumerate(ordered)}
    native_index = [sum(((leaf >> positions[feature]) & 1) << bit for bit, feature in enumerate(features))
                    for leaf in range(1 << len(ordered))]
    return ordered, values.reshape(-1, 3)[native_index]


def compile_factors(classifier, feature_names, descriptions):
    if (not feature_names or len(feature_names) != len(set(feature_names)) or
            not math.isfinite(classifier['scale']) or len(classifier['bias']) != 3 or
            any(not math.isfinite(x) for x in classifier['bias'])):
        raise ValueError('Finite frozen classifier and unique named evidence required')
    # Retain semantic name identity; equal observed columns do not establish
    # logical equivalence and are never a merge criterion.
    grouped = defaultdict(list)
    for i, tree in enumerate(classifier['trees']):
        if any(type(j) is not int or not 0 <= j < len(feature_names) for j in tree['features']):
            raise ValueError('Invalid named feature index')
        features, table = canonical_table(tree)
        grouped[features].append((i, table))
    factors = []
    for features, members in sorted(grouped.items()):
        values = [[math.fsum(table[leaf, c] for _, table in members) for c in range(3)]
                  for leaf in range(1 << len(features))]
        factors.append({'features': list(features), 'source_trees': [i for i, _ in members],
                        'nonzero_leaves': {str(i): v for i, v in enumerate(values) if any(v)}})
    used = sorted({j for factor in factors for j in factor['features']})
    result = {'version': VERSION, 'source_classifier_ref': digest(classifier), 'feature_names': feature_names,
              'descriptions': {feature_names[j]: descriptions[feature_names[j]] for j in used},
              'scale': classifier['scale'], 'bias': list(classifier['bias']), 'factors': factors,
              'source_tree_count': len(classifier['trees']),
              'merge_contract': 'Only identical named-predicate sets; align order and sum all class contributions. Exact in real arithmetic, not guaranteed bit-identical float accumulation. No rounding, pruning, semantic widening, fitting or labels.'}
    result['artifact_ref'] = digest(result)
    FactorExecutor(result)
    return result


class FactorExecutor:
    """Standalone compact scorer; the source forest is not retained."""
    def __init__(self, artifact):
        if (artifact.get('version') != VERSION or
                artifact.get('artifact_ref') != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Changed factor artifact')
        names = artifact['feature_names']
        if not names or len(names) != len(set(names)):
            raise ValueError('Unique named evidence required')
        seen, source = set(), []
        factors = []
        for factor in artifact['factors']:
            features = tuple(factor['features'])
            if (features != tuple(sorted(set(features))) or len(features) > 8 or features in seen or
                    any(type(j) is not int or not 0 <= j < len(names) for j in features)):
                raise ValueError('Invalid or repeated semantic feature set')
            seen.add(features); source.extend(factor['source_trees'])
            table = {}
            for key, vector in factor['nonzero_leaves'].items():
                index = int(key)
                if str(index) != key or not 0 <= index < (1 << len(features)) or len(vector) != 3 or any(not math.isfinite(v) for v in vector):
                    raise ValueError('Invalid sparse leaf')
                table[index] = tuple(vector)
            factors.append((features, table))
        if sorted(source) != list(range(artifact['source_tree_count'])):
            raise ValueError('Source trees must contribute exactly once')
        if (len(artifact['bias']) != 3 or not math.isfinite(artifact['scale']) or
                any(not math.isfinite(v) for v in artifact['bias'])):
            raise ValueError('Finite scale and bias required')
        used = {j for features, _ in factors for j in features}
        if set(artifact['descriptions']) != {names[j] for j in used}:
            raise ValueError('Complete semantic descriptions required')
        self.names, self.factors = list(names), factors
        self.scale, self.bias = artifact['scale'], tuple(artifact['bias'])
        self.artifact_ref = artifact['artifact_ref']

    def logits(self, values):
        vector = [values[name] for name in self.names]
        if any(type(v) is not bool for v in vector):
            raise ValueError('Boolean evidence required')
        contributions = []
        for features, table in self.factors:
            leaf = sum(int(vector[j]) << bit for bit, j in enumerate(features))
            contributions.append(table.get(leaf, (0., 0., 0.)))
        return [self.scale*math.fsum(v[c] for v in contributions)+self.bias[c] for c in range(3)]

    def probabilities(self, values):
        logits = self.logits(values); maximum = max(logits)
        weights = [math.exp(v-maximum) for v in logits]; total = sum(weights)
        return [v/total for v in weights]

    def predict_matrix(self, matrix):
        a = np.asarray(matrix)
        if a.ndim != 2 or a.shape[1] != len(self.names) or not np.all((a == 0) | (a == 1)):
            raise ValueError('Aligned Boolean matrix required')
        result = np.zeros((len(a), 3), dtype=float)
        for features, table in self.factors:
            index = np.zeros(len(a), dtype=int)
            for bit, j in enumerate(features): index |= a[:, j].astype(int) << bit
            dense = np.zeros((1 << len(features), 3))
            for leaf, vector in table.items(): dense[leaf] = vector
            result += dense[index]
        result = result*self.scale+np.asarray(self.bias)
        result = np.exp(result-result.max(axis=1, keepdims=True))
        return result/result.sum(axis=1, keepdims=True)
