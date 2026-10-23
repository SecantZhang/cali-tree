"""Frozen semantic forest selecting among existing experts and regular judge.

Optional research candidate. No raw text, source/case IDs, image hashes, examples,
or model calls participate in routing. Artifact provenance is stored separately.
"""
from copy import deepcopy
import math

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as evidence
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

VERSION = 'frozen-semantic-expert-selector-v49'
LABEL_NAMES = ('unresolved', 'no', 'partial', 'yes')


class SemanticExpertPolicy:
    def __init__(self, artifact):
        expected = {'version', 'feature_contract_ref', 'expert_runtimes', 'feature_names', 'forest', 'threshold', 'artifact_ref'}
        if set(artifact) != expected or artifact['version'] != VERSION or artifact['feature_contract_ref'] != evidence.CONTRACT_REF:
            raise ValueError('Invalid semantic selector contract')
        if digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact['artifact_ref']:
            raise ValueError('Changed semantic selector artifact')
        self.experts = {ref: PortableRuleExecutor(value) for ref, value in sorted(artifact['expert_runtimes'].items())}
        if not 1 <= len(self.experts) <= 16:
            raise ValueError('Invalid expert count')
        allowed = set(evidence.FEATURES) | {'evidence_missing'} | {'judge_predicts_' + x for x in LABEL_NAMES}
        allowed |= {f'expert_{i}_predicts_{x}' for i in range(len(self.experts)) for x in LABEL_NAMES}
        names = artifact['feature_names']
        if not names or len(names) != len(set(names)) or not set(names) <= allowed:
            raise ValueError('Undeclared semantic input')
        if type(artifact['threshold']) not in (int, float) or not 0 <= artifact['threshold'] <= 1:
            raise ValueError('Invalid confidence threshold')
        if not 1 <= len(artifact['forest']) <= 512:
            raise ValueError('Invalid forest size')
        visited = 0
        def validate(node, depth=0):
            nonlocal visited
            visited += 1
            if visited > 200000 or depth > 64:
                raise ValueError('Forest validation bound exceeded')
            if set(node) == {'probabilities'}:
                p = node['probabilities']
                if len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in p) or not math.isclose(sum(p), 1., abs_tol=1e-9):
                    raise ValueError('Invalid leaf probabilities')
            elif set(node) == {'feature', 'false', 'true'} and node['feature'] in names:
                validate(node['false'], depth + 1)
                validate(node['true'], depth + 1)
            else:
                raise ValueError('Invalid semantic forest node')
        for tree in artifact['forest']:
            validate(tree)
        self.artifact = deepcopy(artifact)

    def resolve(self, program, record, regular):
        if type(regular) is not int or regular not in (-1, 0, 1, 2):
            raise ValueError('Invalid regular label')
        values = evidence.feature_values(program, record)
        if values is None:
            return {'covered': False, 'prediction': regular, 'confidence': 0., 'reason': 'missing_evidence', 'matching_experts': []}
        votes = [e.predict_records([record])[0]['prediction'] for e in self.experts.values()]
        values = {**values, 'evidence_missing': False,
                  **{'judge_predicts_' + name: regular == label for name, label in zip(LABEL_NAMES, (-1, 0, 1, 2))}}
        values.update({f'expert_{i}_predicts_{name}': vote == label for i, vote in enumerate(votes)
                       for name, label in zip(LABEL_NAMES, (-1, 0, 1, 2))})
        total = [0., 0., 0.]
        for tree in self.artifact['forest']:
            node = tree
            while 'feature' in node:
                node = node['true'] if values[node['feature']] else node['false']
            total = [a + b for a, b in zip(total, node['probabilities'])]
        probabilities = [v / len(self.artifact['forest']) for v in total]
        available = sorted({p for p in [regular, *votes] if p >= 0})
        selected = max(available, key=lambda c: (probabilities[c], -c)) if available else -1
        confidence = probabilities[selected] if selected >= 0 else 0.
        covered = selected >= 0 and confidence >= self.artifact['threshold']
        prediction = selected if covered else regular
        return {'covered': covered, 'prediction': prediction, 'confidence': confidence,
                'probabilities': probabilities, 'reason': 'semantic_selector' if covered else 'low_confidence',
                'matching_experts': [ref for ref, vote in zip(self.experts, votes) if covered and vote == selected]}


def export_forest(model, names, experts, *, threshold=0.):
    if list(model.classes_) != [0, 1, 2]:
        raise ValueError('Three fixed label classes required')
    def convert(tree, node=0):
        if tree.children_left[node] == -1:
            values = [float(v) for v in tree.value[node][0]]
            return {'probabilities': [v / sum(values) for v in values]}
        if not math.isclose(float(tree.threshold[node]), .5, abs_tol=1e-12):
            raise ValueError('Only declared Boolean predicates may split')
        return {'feature': names[int(tree.feature[node])], 'false': convert(tree, int(tree.children_left[node])),
                'true': convert(tree, int(tree.children_right[node]))}
    artifact = {'version': VERSION, 'feature_contract_ref': evidence.CONTRACT_REF,
                'expert_runtimes': {ref: e.artifact for ref, e in sorted(experts.items())}, 'feature_names': list(names),
                'forest': [convert(estimator.tree_) for estimator in model.estimators_], 'threshold': threshold}
    artifact['artifact_ref'] = digest(artifact)
    SemanticExpertPolicy(artifact)
    return artifact
