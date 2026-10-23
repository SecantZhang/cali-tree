from copy import deepcopy

import pytest

from critical.core.calibration import semantic_expert_policy_v49 as policy
from critical.core.calibration.semantic_hierarchy import portable_runtime_v8 as runtime
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record, CONTRACT_REF
from critical.core.decision.artifacts import digest


def artifact(threshold=0.):
    experts = {}
    for label in (1, 2):
        expert = {'version': runtime.VERSION, 'feature_contract_ref': CONTRACT_REF,
                  'tree': {'prediction': label}, 'predicate_descriptions': {}}
        expert['artifact_ref'] = digest(expert)
        experts[expert['artifact_ref']] = expert
    value = {'version': policy.VERSION, 'feature_contract_ref': policy.evidence.CONTRACT_REF,
             'expert_runtimes': experts, 'feature_names': ['meaning_progress_none_all'],
             'forest': [{'probabilities': [.9, .09, .01]}], 'threshold': threshold}
    value['artifact_ref'] = digest(value)
    return value


def test_selector_only_chooses_available_labels_and_respects_confidence_fallback(monkeypatch):
    monkeypatch.setattr(policy.evidence, 'feature_values', lambda p, r: {'meaning_progress_none_all': True})
    record = synthetic_record(meaning_available=True)
    result = policy.SemanticExpertPolicy(artifact()).resolve(None, record, 2)
    assert result['prediction'] == 1 and result['covered']
    assert result['confidence'] == .09 and result['matching_experts']
    fallback = policy.SemanticExpertPolicy(artifact(.1)).resolve(None, record, 2)
    assert fallback['prediction'] == 2 and not fallback['covered']


def test_missing_evidence_uses_regular_without_expert_evaluation():
    result = policy.SemanticExpertPolicy(artifact()).resolve(None, None, 2)
    assert result['prediction'] == 2 and not result['covered']
    assert result['reason'] == 'missing_evidence'


def test_selector_rejects_case_identifier_predicates_even_with_valid_outer_hash():
    value = deepcopy(artifact())
    value['feature_names'] = ['case_id']
    value['artifact_ref'] = digest({k: v for k, v in value.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='Undeclared'):
        policy.SemanticExpertPolicy(value)
