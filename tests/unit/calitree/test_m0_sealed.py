"""Integrity and leakage checks against the actual sealed M0 reservation."""
from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from run.calitree_m0 import verify
from run.calitree_m0_finalize import independent_check
from run.calitree_single_call import ROOT, read, fingerprint
from critical.core.decision.artifacts import save_json


SOURCE = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'


@pytest.fixture
def bundle(tmp_path):
    if not (SOURCE / 'completion_seal.json').exists():
        pytest.skip('Local sealed M0 experiment unavailable')
    target = tmp_path / 'reservation'
    shutil.copytree(SOURCE, target)
    return target


def resign_base(bundle, rel):
    seal = read(bundle / 'seal.json')
    seal['files'][rel] = fingerprint(bundle / rel)
    save_json(bundle / 'seal.json', seal)


def test_real_bundle_contains_fifty_unexecuted_cases(bundle):
    result = verify(bundle)
    assert result['reserved_test_cases'] == 50 and result['source_overlap'] == 0
    assert result['model_calls'] == 0
    audit = independent_check(bundle, read(bundle / 'selection_protocol.json'))
    assert audit['unique_sources_across_partitions'] == 110
    assert audit['strict_globally_untouched_claim'] is False


def test_tampered_policy_snapshot_is_rejected(bundle):
    p = bundle / 'baseline_snapshot/G1/policy.json'
    p.write_text(p.read_text() + '\n')
    with pytest.raises(ValueError, match='Sealed artifact changed'):
        verify(bundle)


def test_resigned_train_test_source_leak_is_rejected(bundle):
    train = read(bundle / 'splits/train.json')['cases']
    test = read(bundle / 'splits/test.json')
    test['cases'][0] = {**train[0], 'case': 'F01'}
    save_json(bundle / 'splits/test.json', test)
    resign_base(bundle, 'splits/test.json')
    with pytest.raises(ValueError, match='Source leakage'):
        verify(bundle)


def test_resigned_reference_leak_into_model_inputs_is_rejected(bundle):
    inputs = read(bundle / 'test_inputs.json')
    inputs['cases'][0]['input']['reference'] = 'yes'
    save_json(bundle / 'test_inputs.json', inputs)
    resign_base(bundle, 'test_inputs.json')
    with pytest.raises(ValueError, match='Reserved model inputs changed'):
        verify(bundle)


def test_resigned_untouched_claim_is_rejected(bundle):
    p = read(bundle / 'study_protocol.json')
    p['test_scope'] = 'no_known_historical_exposure'
    save_json(bundle / 'study_protocol.json', p)
    resign_base(bundle, 'study_protocol.json')
    with pytest.raises(ValueError, match='mislabeled as untouched'):
        verify(bundle)


def test_fold_fit_validation_overlap_is_rejected(bundle):
    p = deepcopy(read(bundle / 'selection_protocol.json'))
    p['selection_folds'][0]['fit_ids'][0] = p['selection_folds'][0]['validation_ids'][0]
    with pytest.raises(AssertionError):
        independent_check(bundle, p)


def test_inference_on_reserved_set_invalidates_m0_state(bundle):
    save_json(bundle / 'predictions.json', {'unexpected': 'evaluation'})
    with pytest.raises(ValueError, match='already evaluated'):
        verify(bundle)
