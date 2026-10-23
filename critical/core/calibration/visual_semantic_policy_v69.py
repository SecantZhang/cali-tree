"""Portable Boolean boosted policy with bound local-vision evidence.

The artifact stores semantic tree parameters, never case IDs, training examples,
raw embeddings, executable pickle objects or source-membership overrides.
"""
from copy import deepcopy
import math

from ..decision.artifacts import digest
from . import shared_regions_v27 as shared
from . import evidence_coverage_v20 as evidence
from . import judge_semantics_v60 as language
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from ...vision import paired_features_v69 as vision
from ...vision.paired_encoder_v69 import encoder_spec

VERSION = 'frozen-visual-semantic-policy-v69'
LABELS = ('no', 'partial', 'yes')


def regular_label(judgment):
    if judgment is None:
        return -1
    if (not isinstance(judgment, dict) or set(judgment) != {'label', 'rationale'} or judgment['label'] not in (*LABELS, 'unresolved') or
            not isinstance(judgment['rationale'], str) or not judgment['rationale'].strip()):
        raise ValueError('Invalid regular judgment')
    return LABELS.index(judgment['label']) if judgment['label'] in LABELS else -1


class VisualSemanticPolicy:
    def __init__(self, artifact):
        expected = {'version', 'semantic_contract_ref', 'language_contract_ref', 'vision_contract_ref',
                    'encoder_spec', 'feature_names', 'classifier', 'expert_runtimes', 'artifact_ref'}
        if set(artifact) != expected or artifact['version'] != VERSION:
            raise ValueError('Invalid visual policy artifact')
        if digest({k: v for k, v in artifact.items() if k != 'artifact_ref'}) != artifact['artifact_ref']:
            raise ValueError('Changed visual policy artifact')
        if (artifact['semantic_contract_ref'] != evidence.CONTRACT_REF or artifact['language_contract_ref'] != language.CONTRACT_REF or
                artifact['vision_contract_ref'] != vision.CONTRACT_REF or artifact['encoder_spec']['feature_contract'] != vision.CONTRACT_REF):
            raise ValueError('Changed semantic/vision contracts')
        if artifact['encoder_spec']['model'] != vision.MODEL or artifact['encoder_spec']['revision'] != vision.REVISION:
            raise ValueError('Changed visual encoder')
        allowed = set(evidence.FEATURES) | set(language.SPECS) | set(vision.SPECS) | {'evidence_missing'}
        allowed |= {'judge_predicts_' + name for name in ('unresolved', *LABELS)}
        names = artifact['feature_names']
        if not names or len(set(names)) != len(names) or not set(names) <= allowed:
            raise ValueError('Undeclared inference feature')
        classifier = artifact['classifier']
        if set(classifier) != {'scale', 'bias', 'trees'} or not 1 <= len(classifier['trees']) <= 2000 or len(classifier['bias']) != 3:
            raise ValueError('Invalid boosted classifier')
        values = [classifier['scale'], *classifier['bias']]
        count = 0
        for tree in classifier['trees']:
            if set(tree) != {'features', 'values'} or len(tree['features']) > 8 or len(tree['values']) != 3 * 2 ** len(tree['features']):
                raise ValueError('Invalid symmetric semantic tree')
            if any(type(i) is not int or not 0 <= i < len(names) for i in tree['features']):
                raise ValueError('Invalid feature index')
            count += len(tree['values'])
            if count > 1600000:
                raise ValueError('Visual policy size bound exceeded')
            values.extend(tree['values'])
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Nonfinite classifier value')
        self.experts = {ref: PortableRuleExecutor(value) for ref, value in sorted(artifact['expert_runtimes'].items())}
        if not 1 <= len(self.experts) <= 16:
            raise ValueError('Invalid availability expert bank')
        self.artifact = deepcopy(artifact)

    def probabilities(self, values):
        names, model = self.artifact['feature_names'], self.artifact['classifier']
        vector = [values[name] for name in names]
        if any(type(value) is not bool for value in vector):
            raise ValueError('Declared Boolean feature values required')
        logits = [0., 0., 0.]
        for tree in model['trees']:
            leaf = sum(int(vector[i]) << bit for bit, i in enumerate(tree['features']))
            start = 3 * leaf
            logits = [logits[c] + tree['values'][start + c] for c in range(3)]
        logits = [model['scale'] * value + bias for value, bias in zip(logits, model['bias'])]
        maximum = max(logits)
        support = [math.exp(value - maximum) for value in logits]
        total = sum(support)
        return [value / total for value in support]

    def _resolve(self, program, record, judgment, measured):
        regular = regular_label(judgment)
        values = evidence.feature_values(program, record)
        if values is None:
            return {'covered': False, 'prediction': regular, 'reason': 'missing_semantic_evidence'}
        votes = [expert.predict_records([record])[0]['prediction'] for expert in self.experts.values()]
        if not any(v >= 0 for v in [regular, *votes]):
            return {'covered': False, 'prediction': regular, 'reason': 'no_available_judgment'}
        values = {**values, **language.project(program, judgment), **vision.predicates(measured), 'evidence_missing': False,
                  **{'judge_predicts_' + name: regular == label for name, label in zip(('unresolved', *LABELS), (-1, 0, 1, 2))}}
        probability = self.probabilities(values)
        prediction = max(range(3), key=lambda c: (probability[c], -c))
        return {'covered': True, 'prediction': prediction, 'reason': 'visual_semantic_policy', 'class_support': probability,
                'matching_legacy_experts': [ref for ref, vote in zip(self.experts, votes) if vote == prediction]}

    def resolve_bound(self, program, observation, pair_ref, interpretation, judgment, vision_record):
        regular = regular_label(judgment)
        try:
            if (not isinstance(vision_record, dict) or vision_record.get('version') != vision.VERSION or
                    vision_record.get('feature_contract_ref') != vision.CONTRACT_REF or
                    vision_record.get('program_ref') != program['program_ref'] or vision_record.get('image_pair_ref') != pair_ref or
                    vision_record.get('encoder_spec_ref') != digest(self.artifact['encoder_spec'])):
                raise ValueError('Unbound visual evidence')
            record = shared.evidence.project(program, observation, pair_ref, interpretation)
            return self._resolve(program, record, judgment, vision_record['measurements'])
        except (ValueError, KeyError, TypeError):
            return {'covered': False, 'prediction': regular, 'reason': 'invalid_or_missing_bound_evidence'}


def export_classifier(native, feature_names, experts, identity):
    float_features = native['features_info']['float_features']
    columns = {f['feature_index']: f['flat_feature_index'] for f in float_features}
    trees = []
    for tree in native['oblivious_trees']:
        features = []
        for split in tree['splits'] or []:
            if split['split_type'] != 'FloatFeature' or not math.isclose(split['border'], .5, abs_tol=1e-12):
                raise ValueError('Only declared Boolean splits may be exported')
            features.append(int(columns[split['float_feature_index']]))
        trees.append({'features': features, 'values': tree['leaf_values']})
    scale, bias = native['scale_and_bias']
    artifact = {'version': VERSION, 'semantic_contract_ref': evidence.CONTRACT_REF,
                'language_contract_ref': language.CONTRACT_REF, 'vision_contract_ref': vision.CONTRACT_REF,
                'encoder_spec': encoder_spec(identity), 'feature_names': list(feature_names),
                'classifier': {'scale': scale, 'bias': bias, 'trees': trees},
                'expert_runtimes': {ref: expert.artifact for ref, expert in sorted(experts.items())}}
    artifact['artifact_ref'] = digest(artifact)
    VisualSemanticPolicy(artifact)
    return artifact
