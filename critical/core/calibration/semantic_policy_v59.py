"""Portable, closed-vocabulary forest or boundary policy for existing judges.

No model calls or example identifiers are accepted by the inference interface.
Fitting provenance belongs in the experiment manifest, outside this artifact.
"""
from copy import deepcopy
import math

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as evidence
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

VERSION = 'portable-semantic-policy-v59'
PAIRS = ((0, 1), (1, 2), (0, 2))


class SemanticPolicy:
    def __init__(self, artifact):
        keys = {'version', 'feature_contract_ref', 'expert_runtimes', 'feature_names',
                'family', 'heads', 'mode', 'threshold', 'artifact_ref'}
        if set(artifact) != keys or artifact['version'] != VERSION or artifact['feature_contract_ref'] != evidence.CONTRACT_REF:
            raise ValueError('Invalid portable policy contract')
        if digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact['artifact_ref']:
            raise ValueError('Changed portable policy artifact')
        self.experts = {ref: PortableRuleExecutor(value) for ref, value in sorted(artifact['expert_runtimes'].items())}
        names = artifact['feature_names']
        allowed = set(evidence.FEATURES) | {'evidence_missing'} | {'judge_predicts_' + name for name in ('unresolved', 'no', 'partial', 'yes')}
        if not 1 <= len(self.experts) <= 16 or not names or len(set(names)) != len(names) or not set(names) <= allowed:
            raise ValueError('Undeclared portable policy inputs')
        if artifact['mode'] not in ('direct', 'routed') or type(artifact['threshold']) not in (float, int) or not 0 <= artifact['threshold'] <= 1:
            raise ValueError('Invalid portable decision rule')
        if artifact['mode'] == 'direct' and artifact['threshold'] != 0:
            raise ValueError('Direct arm has no support gate')
        if artifact['family'] == 'forest':
            expected_labels = [[0, 1, 2]]
        elif artifact['family'] == 'boundary':
            expected_labels = [list(pair) for pair in PAIRS]
        else:
            raise ValueError('Unknown portable policy family')
        if [head['labels'] for head in artifact['heads']] != expected_labels:
            raise ValueError('Changed boundary definitions')
        visited = 0
        def validate(node, labels, depth=0):
            nonlocal visited
            visited += 1
            if visited > 500000 or depth > 64:
                raise ValueError('Portable tree bound exceeded')
            if set(node) == {'support'}:
                values = node['support']
                if len(values) != len(labels) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values) or not math.isclose(sum(values), 1., abs_tol=1e-9):
                    raise ValueError('Invalid portable leaf')
            elif set(node) == {'feature', 'false', 'true'} and node['feature'] in names:
                validate(node['false'], labels, depth + 1)
                validate(node['true'], labels, depth + 1)
            else:
                raise ValueError('Invalid portable branch')
        for head in artifact['heads']:
            if set(head) != {'labels', 'trees'} or not 1 <= len(head['trees']) <= 512:
                raise ValueError('Invalid portable head')
            for tree in head['trees']:
                validate(tree, head['labels'])
        self.artifact = deepcopy(artifact)

    def supports(self, values):
        heads = []
        for head in self.artifact['heads']:
            totals = [0.] * len(head['labels'])
            for node in head['trees']:
                while 'feature' in node:
                    node = node['true'] if values[node['feature']] else node['false']
                totals = [a + b for a, b in zip(totals, node['support'])]
            heads.append([v / len(head['trees']) for v in totals])
        if self.artifact['family'] == 'forest':
            return heads[0]
        scores = [1.] * 3
        for pair, support in zip(PAIRS, heads):
            # Match the training implementation's positive-class complement.
            positive = support[1]
            for label, value in zip(pair, (1 - positive, positive)):
                scores[label] = min(scores[label], value)
        total = sum(scores)
        return [v / total for v in scores] if total > 0 else [1 / 3] * 3

    def resolve(self, program, record, regular):
        if type(regular) is not int or regular not in (-1, 0, 1, 2):
            raise ValueError('Invalid regular label')
        values = evidence.feature_values(program, record)
        if values is None:
            return {'covered': False, 'prediction': regular, 'support': 0., 'reason': 'missing_evidence', 'matching_experts': []}
        votes = [expert.predict_records([record])[0]['prediction'] for expert in self.experts.values()]
        available = sorted({p for p in [regular, *votes] if p >= 0})
        values = {**values, 'evidence_missing': False,
                  **{'judge_predicts_' + name: regular == label for name, label in zip(('unresolved', 'no', 'partial', 'yes'), (-1, 0, 1, 2))}}
        support = self.supports(values)
        choices = range(3) if self.artifact['mode'] == 'direct' else available
        selected = max(choices, key=lambda c: (support[c], -c)) if available else -1
        score = support[selected] if selected >= 0 else 0.
        covered = selected >= 0 and score >= self.artifact['threshold']
        return {'covered': covered, 'prediction': selected if covered else regular, 'support': score,
                'class_support': support, 'reason': 'semantic_policy' if covered else 'insufficient_support',
                'matching_experts': [ref for ref, vote in zip(self.experts, votes) if covered and vote == selected]}


def export_policy(model, names, experts, *, family, mode='routed', threshold=0.):
    def convert(tree, node=0):
        if tree.children_left[node] == -1:
            values = [float(v) for v in tree.value[node][0]]
            return {'support': [v / sum(values) for v in values]}
        if not math.isclose(float(tree.threshold[node]), .5, abs_tol=1e-12):
            raise ValueError('Only declared Boolean predicates may split')
        return {'feature': names[int(tree.feature[node])], 'false': convert(tree, int(tree.children_left[node])),
                'true': convert(tree, int(tree.children_right[node]))}
    if family == 'forest':
        if list(model.classes_) != [0, 1, 2]:
            raise ValueError('Three fixed classes required')
        heads = [([0, 1, 2], model)]
    elif family == 'boundary':
        heads = [(list(pair), model.heads[pair]) for pair in PAIRS]
        if any(list(head.classes_) != [False, True] for _, head in heads):
            raise ValueError('Binary boundary classes required')
    else:
        raise ValueError('Unknown portable policy family')
    artifact = {'version': VERSION, 'feature_contract_ref': evidence.CONTRACT_REF,
                'expert_runtimes': {ref: expert.artifact for ref, expert in sorted(experts.items())},
                'feature_names': list(names), 'family': family,
                'heads': [{'labels': labels, 'trees': [convert(estimator.tree_) for estimator in head.estimators_]} for labels, head in heads],
                'mode': mode, 'threshold': threshold}
    artifact['artifact_ref'] = digest(artifact)
    SemanticPolicy(artifact)
    return artifact
