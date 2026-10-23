from copy import deepcopy

import pytest

from critical.core.calibration import visual_semantic_policy_v69 as policy
from critical.core.calibration.semantic_hierarchy import portable_runtime_v8 as legacy
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import CONTRACT_REF
from critical.core.decision.artifacts import digest
from critical.vision import paired_features_v69 as vision
from run import paired_vision_features_v63 as previous_vision


def artifact():
    expert = {'version': legacy.VERSION, 'feature_contract_ref': CONTRACT_REF, 'tree': {'prediction': 0}, 'predicate_descriptions': {}}
    expert['artifact_ref'] = digest(expert)
    spec = {'model': vision.MODEL, 'revision': vision.REVISION, 'files': {}, 'backend': 'mps', 'dtype': 'float32',
            'torch': '2.9.0', 'transformers': '4.57.6', 'feature_contract': vision.CONTRACT_REF}
    value = {'version': policy.VERSION, 'semantic_contract_ref': policy.evidence.CONTRACT_REF,
             'language_contract_ref': policy.language.CONTRACT_REF, 'vision_contract_ref': vision.CONTRACT_REF,
             'encoder_spec': spec, 'feature_names': ['meaning_progress_none_all'],
             'classifier': {'scale': 1., 'bias': [0., 0., 0.], 'trees': [{'features': [0], 'values': [3., 0., 0., 0., 3., 0.]}]},
             'expert_runtimes': {expert['artifact_ref']: expert}}
    value['artifact_ref'] = digest(value)
    return value


def test_runtime_feature_contract_is_identical_to_the_evaluated_projection():
    assert vision.CONTRACT_REF == previous_vision.CONTRACT_REF
    assert vision.SPECS == previous_vision.SPECS


def test_oblivious_tree_leaf_order_and_untrusted_feature_rejection():
    runtime = policy.VisualSemanticPolicy(artifact())
    assert max(range(3), key=lambda c: runtime.probabilities({'meaning_progress_none_all': False})[c]) == 0
    assert max(range(3), key=lambda c: runtime.probabilities({'meaning_progress_none_all': True})[c]) == 1
    bad = deepcopy(artifact()); bad['feature_names'] = ['case_id']
    bad['artifact_ref'] = digest({k: v for k, v in bad.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        policy.VisualSemanticPolicy(bad)


def test_visual_evidence_from_another_pair_cannot_override_regular(monkeypatch):
    runtime = policy.VisualSemanticPolicy(artifact())
    called = []
    monkeypatch.setattr(policy.shared.evidence, 'project', lambda *args: called.append(True))
    visual = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF, 'program_ref': 'p',
              'image_pair_ref': 'other-pair', 'encoder_spec_ref': digest(runtime.artifact['encoder_spec']), 'measurements': {}}
    result = runtime.resolve_bound({'program_ref': 'p'}, None, 'pair', None, {'label': 'yes', 'rationale': 'Regular outcome.'}, visual)
    assert result['prediction'] == 2 and not result['covered'] and not called


def test_artifact_mutation_and_invalid_regular_are_rejected():
    bad = artifact(); bad['classifier']['bias'][0] = 8.
    with pytest.raises(ValueError, match='Changed'):
        policy.VisualSemanticPolicy(bad)
    with pytest.raises(ValueError, match='regular'):
        policy.regular_label({'label': 'yes', 'rationale': ''})
