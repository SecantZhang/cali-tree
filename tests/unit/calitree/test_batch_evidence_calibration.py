"""No-API calibration, leakage guards, semantic text use, and portable replay."""
from copy import deepcopy
import json

import numpy as np
import pytest

from critical.core.calibration.base import Calibrator
from critical.core.calibration.evidence_batch import (
    EvidenceBatchCalibrator, evidence_features, select_and_fit,
)
from run.calitree_batch_calibration import assert_disjoint, evaluate_cached


def record(state='incomplete', text='A small incidental highlight remains.'):
    return {'instruction': 'Change the object color', 'observations': {
        'instruction_scope': 'Change the intended object color.',
        'target': {'state': 'matched', 'evidence': 'The intended object is identifiable.'},
        'source_integrity': {'state': 'preserved', 'evidence': 'Relevant source content remains.'},
        'requirements': [{'id': 'r', 'source_quote': 'Change the object color',
                          'question': 'Is the requested color applied?', 'role': 'core',
                          'state': state, 'evidence': text}],
    }}


def training():
    X, y = [], []
    for _ in range(4):
        X += [record('absent', 'No requested change is visible.'),
              record(text='A material missing portion prevents completion.'),
              record(text='A small incidental highlight remains.')]
        y += [0, 1, 2]
    return X, y


def test_implements_calibrator_contract_and_uses_text_beyond_identical_states():
    X, y = training()
    model = EvidenceBatchCalibrator().fit(X, y)
    assert isinstance(model, Calibrator)
    # These have identical categorical checks but different evidence descriptions.
    result = model.predict_records([X[1], X[2]])
    assert [r['label'] for r in result] == ['partial', 'yes']
    assert model.predict([X[1], X[2]]) == [1., 2.]


def test_json_artifact_restores_identical_probabilities_without_refitting():
    X, y = training(); model = EvidenceBatchCalibrator().fit(X, y)
    portable = json.loads(json.dumps(model.metadata(), allow_nan=False))
    restored = EvidenceBatchCalibrator.restore(portable)
    assert restored.predict_records(X) == model.predict_records(X)


def test_observability_and_decisive_no_guards_survive_calibration():
    X, y = training(); model = EvidenceBatchCalibrator().fit(X, y)
    unknown = record('unknown'); wrong = record('complete')
    wrong['observations']['target']['state'] = 'wrong_target'
    values = model.predict_records([unknown, wrong])
    assert values[0]['label'] is None and values[0]['guard'] == 'unresolved_evidence'
    assert values[1]['label'] == 'no' and values[1]['guard'] == 'fixed_policy_no'


@pytest.mark.parametrize('field', ['reference', 'human_score', 'id', 'task', 'editing_model'])
def test_feature_inputs_reject_metadata_and_supervision(field):
    value = record(); value[field] = 'forbidden'
    with pytest.raises(ValueError): evidence_features(value)


def test_cached_evaluation_predictions_do_not_depend_on_evaluation_labels():
    X, y = training(); model = EvidenceBatchCalibrator().fit(X, y)
    old = {'cases': [{'case': 'F', 'id': 'heldout', 'instruction': X[2]['instruction'],
                      'reference': 'yes', 'prediction': 'partial',
                      'decision': {'observations': X[2]['observations'], 'execution_ref': 'cached'}}]}
    a = evaluate_cached(model, old)
    old['cases'][0]['reference'] = 'no'
    b = evaluate_cached(model, old)
    assert a[0]['calibration'] == b[0]['calibration']
    assert a[0]['prediction'] == b[0]['prediction'] == 'yes'


def test_source_group_overlap_and_training_duplicates_are_rejected():
    with pytest.raises(ValueError): assert_disjoint([{'id': 'train', 'group': 'same'}], [{'id': 'test', 'group': 'same'}])
    with pytest.raises(ValueError): assert_disjoint([{'id': 'a', 'group': 'same'}, {'id': 'b', 'group': 'same'}], [])
    assert_disjoint([{'id': 'a', 'group': 'train'}], [{'id': 'b', 'group': 'test'}])


def test_cv_and_final_fit_use_training_inputs_and_serialize_reproducibly():
    X, y = training()
    model, cv = select_and_fit(X, y)
    assert len(cv['folds']) == 3 and len(cv['candidates']) == 3
    assert model.metadata()['training_rows'] == 12
    assert cv['selected_regularization'] in (.1, 1., 10.)
    for fold in cv['folds']:
        assert not set(fold['train']) & set(fold['validation'])
        assert sorted(fold['train'] + fold['validation']) == list(range(12))
    assert np.allclose([sum(r['probabilities'].values()) for r in model.predict_records(X)], 1)


def test_invalid_artifact_dimensions_or_nonfinite_values_are_rejected():
    X, y = training(); artifact = EvidenceBatchCalibrator().fit(X, y).metadata()
    broken = deepcopy(artifact); broken['coef'][0].pop()
    with pytest.raises((ValueError, TypeError)): EvidenceBatchCalibrator.restore(broken)
    artifact['scale'][0] = 0
    with pytest.raises(ValueError): EvidenceBatchCalibrator.restore(artifact)
