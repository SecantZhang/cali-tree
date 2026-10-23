from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from critical.core.calibration import semantic_policy_v59 as policy
from critical.core.calibration.boundary_experts_v55 import BoundaryExperts
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_semantic_expert_policy_v49 import artifact as old_artifact


def artifact(family='forest', mode='routed', threshold=0.):
    value = {'version': policy.VERSION, 'feature_contract_ref': policy.evidence.CONTRACT_REF,
             'expert_runtimes': old_artifact()['expert_runtimes'], 'feature_names': ['meaning_progress_none_all'],
             'family': family, 'mode': mode, 'threshold': threshold}
    value['heads'] = ([{'labels': [0, 1, 2], 'trees': [{'support': [.9, .09, .01]}]}] if family == 'forest'
                      else [{'labels': list(pair), 'trees': [{'support': [1 - p, p]}]}
                            for pair, p in zip(policy.PAIRS, (.8, .6, .7))])
    value['artifact_ref'] = digest(value)
    return value


def test_routed_direct_support_gate_and_missing_fallback(monkeypatch):
    monkeypatch.setattr(policy.evidence, 'feature_values', lambda p, r: None if r is None else {'meaning_progress_none_all': True})
    record = synthetic_record(meaning_available=True)
    routed = policy.SemanticPolicy(artifact()).resolve(None, record, 2)
    assert routed['prediction'] == 1 and routed['covered'] and routed['support'] == .09
    assert policy.SemanticPolicy(artifact(mode='direct')).resolve(None, record, 2)['prediction'] == 0
    fallback = policy.SemanticPolicy(artifact(threshold=.1)).resolve(None, record, 2)
    assert fallback['prediction'] == 2 and not fallback['covered']
    missing = policy.SemanticPolicy(artifact()).resolve(None, None, -1)
    assert missing['prediction'] == -1 and not missing['covered']


def test_boundary_minimum_and_complete_tie_are_explicit(monkeypatch):
    monkeypatch.setattr(policy.evidence, 'feature_values', lambda p, r: {'meaning_progress_none_all': True})
    runtime = policy.SemanticPolicy(artifact(family='boundary'))
    assert np.allclose(runtime.supports({'meaning_progress_none_all': True}), [1/6, 1/3, .5])
    tied = artifact(family='boundary')
    for head in tied['heads']:
        head['trees'] = [{'support': [.5, .5]}]
    tied['artifact_ref'] = digest({k: v for k, v in tied.items() if k != 'artifact_ref'})
    result = policy.SemanticPolicy(tied).resolve(None, synthetic_record(meaning_available=True), 0)
    assert result['prediction'] == 0 and result['covered']


@pytest.mark.parametrize('family', ['forest', 'boundary'])
def test_exported_probabilities_match_fitted_models(family):
    matrix = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
    labels = np.asarray([0, 1, 2, 0])
    model = (RandomForestClassifier(n_estimators=8, bootstrap=False, random_state=1) if family == 'forest'
             else BoundaryExperts(balanced=True)).fit(matrix, labels)
    experts = {ref: SimpleNamespace(artifact=a) for ref, a in old_artifact()['expert_runtimes'].items()}
    names = ['meaning_progress_none_all', 'judge_predicts_no']
    runtime = policy.SemanticPolicy(policy.export_policy(model, names, experts, family=family))
    expected = model.predict_proba(matrix) if family == 'forest' else model.predict_proba(matrix, 'minimum')
    actual = [runtime.supports(dict(zip(names, row))) for row in matrix]
    assert np.allclose(actual, expected, rtol=0, atol=1e-12)


def test_semantic_names_hash_and_mode_are_validated():
    original = artifact()
    invalid = deepcopy(original)
    invalid['heads'][0]['trees'][0]['support'] = [0., 0., 1.]
    with pytest.raises(ValueError, match='Changed'):
        policy.SemanticPolicy(invalid)
    for field, value, message in [('feature_names', ['case_id'], 'Undeclared'), ('threshold', -1., 'decision'), ('mode', 'lookup', 'decision')]:
        invalid = {**original, field: value}
        invalid['artifact_ref'] = digest({k: v for k, v in invalid.items() if k != 'artifact_ref'})
        with pytest.raises(ValueError, match=message):
            policy.SemanticPolicy(invalid)
