"""One bounded CART tree over declared Boolean evidence; no teacher at inference."""
from copy import deepcopy

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from .base import Calibrator
from .class_balance_v141 import training_weights
from ..decision.artifacts import digest

VERSION = 'standalone-boolean-tree-v173'
ANCHOR_WEIGHTS = (1., 5., 25., 125., 625.)
LABELS = ('No', 'Partial', 'Yes')


def execute(artifact, values):
    """Read Boolean evidence only. No case membership or teacher prediction."""
    if artifact.get('artifact_ref') != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}):
        raise ValueError('Changed standalone tree')
    if artifact.get('version') != VERSION:
        raise ValueError('Unsupported standalone tree')
    node = artifact['tree']
    while 'feature' in node:
        value = values.get(node['feature'])
        if type(value) is not bool:
            raise ValueError('Required Boolean evidence unavailable')
        node = node['if_true'] if value else node['if_false']
    grade = node['grade']
    if type(grade) is not int or grade not in (0, 1, 2):
        raise ValueError('Invalid leaf grade')
    return grade


def render(artifact):
    lines = ['One standalone decision tree over extracted evidence. Missing/invalid upstream evidence uses the regular judge.',
             'False predicates mean not established; their physical negations are not necessarily proved.']
    def walk(node, depth):
        prefix = '  '*depth
        if 'feature' not in node:
            lines.append(prefix+'RETURN '+LABELS[node['grade']]+f" (fitting sources: {node['fitting_sources']})")
            return
        lines.append(prefix+'IF '+artifact['descriptions'][node['feature']]+':')
        walk(node['if_true'], depth+1)
        lines.append(prefix+'ELSE (not established):')
        walk(node['if_false'], depth+1)
    walk(artifact['tree'], 0)
    return '\n'.join(lines)+'\n'


class SingleTree(Calibrator):
    version = VERSION

    def __init__(self, names, *, leaves=32, balanced=True):
        if not names or len(names) != len(set(names)) or type(leaves) is not int or leaves < 2 or type(balanced) is not bool:
            raise ValueError('Unique feature names and a leaf budget required')
        self.names, self.leaves, self.balanced = list(names), leaves, balanced

    def _matrix(self, X):
        a = np.asarray(X)
        if a.ndim != 2 or a.shape[1] != len(self.names) or not np.all((a == 0) | (a == 1)):
            raise ValueError('Aligned Boolean evidence required')
        return a.astype(np.float32)

    def fit(self, X, y, *, sample_weight=None, original=None, groups=None,
            protected_X=None, protected_y=None):
        a, y = self._matrix(X), np.asarray(y, dtype=int)
        if sample_weight is not None or y.shape != (len(a),) or not set(y) <= {0, 1, 2}:
            raise ValueError('Three-grade fitting targets and internal weighting required')
        original = np.zeros(len(a), dtype=bool) if original is None else np.asarray(original)
        if original.shape != y.shape or original.dtype != bool or groups is None or len(groups) != len(a):
            raise ValueError('Aligned protection and fitting source membership required')
        p = self._matrix(protected_X) if protected_X is not None else a[:0]
        py = np.asarray(protected_y if protected_y is not None else [], dtype=int)
        if py.shape != (len(p),):
            raise ValueError('Aligned protected cases required')
        self.attempts = []
        for anchor in ANCHOR_WEIGHTS:
            weights = training_weights(y, original=original, original_weight=anchor, balanced=self.balanced)
            model = DecisionTreeClassifier(criterion='log_loss', max_leaf_nodes=self.leaves,
                                           min_samples_leaf=1, random_state=20261026)
            model.fit(a, y, sample_weight=weights*len(a))
            correct = int(np.sum(model.predict(p) == py)) if len(p) else 0
            self.attempts.append({'original_weight': anchor, 'protected_correct': correct,
                                  'class_weight_mass': [float(weights[y == k].sum()) for k in range(3)]})
            if correct == len(p):
                break
        self.model, self.original_weight = model, anchor
        self.retained = correct == len(p)
        self.fitting_X, self.fitting_groups = a, np.asarray(groups)
        return self

    def predict(self, X):
        return self.model.predict(self._matrix(X)).astype(int).tolist()

    def metadata(self):
        return {'version': VERSION, 'leaves': int(self.model.get_n_leaves()), 'depth': int(self.model.get_depth()),
                'retained': self.retained, 'attempts': deepcopy(self.attempts)}

    def artifact(self, descriptions):
        native = self.model.tree_
        assignments = self.model.apply(self.fitting_X)
        def node(i):
            if native.children_left[i] == native.children_right[i]:
                values = native.value[i][0]
                return {'grade': int(self.model.classes_[int(np.argmax(values))]),
                        'class_support': [float(values[j]/values.sum()) for j in range(len(values))],
                        'fitting_rows': int(np.sum(assignments == i)),
                        'fitting_sources': len(set(self.fitting_groups[assignments == i]))}
            if native.threshold[i] != .5:
                raise ValueError('Only Boolean splits may be exported')
            return {'feature': self.names[native.feature[i]],
                    'if_false': node(native.children_left[i]), 'if_true': node(native.children_right[i])}
        tree = node(0)
        used = set()
        def collect(n):
            if 'feature' in n:
                used.add(n['feature']); collect(n['if_false']); collect(n['if_true'])
        collect(tree)
        result = {'version': VERSION, 'tree': tree, 'descriptions': {n: descriptions[n] for n in sorted(used)},
                  'feature_names': sorted(used), 'metadata': self.metadata(), 'leaf_budget': self.leaves,
                  'balanced': self.balanced, 'standalone': True}
        result['rubric'] = render(result)
        result['artifact_ref'] = digest(result)
        return result
