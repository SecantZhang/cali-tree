import itertools
import json

import numpy as np
import pytest

from critical.core.calibration.boosted_factor_merge_v175 import compile_factors, FactorExecutor


def classifier():
    return {'scale': .7, 'bias': [.1, -.2, .3], 'trees': [
        {'features': [0, 1], 'values': [0., 0., 0., 1., -1., 0., 0., 2., -2., 3., 1., -4.]},
        {'features': [1, 0], 'values': [0., 0., 0., 0., -2., 2., -1., 1., 0., -3., -1., 4.]},
        {'features': [2], 'values': [0., .1, -.1, -.1, 0., .1]}]}


def native_logits(model, row):
    out = np.zeros(3)
    for tree in model['trees']:
        index = sum(int(row[j]) << bit for bit, j in enumerate(tree['features']))
        out += tree['values'][3*index:3*index+3]
    return out*model['scale']+model['bias']


def test_reordered_semantic_tests_merge_with_exact_cancellation():
    model = classifier(); names = ['completion', 'preservation', 'identity']
    artifact = compile_factors(model, names, dict(zip(names, names)))
    assert len(artifact['factors']) == 2
    assert artifact['factors'][0]['nonzero_leaves'] == {}
    runtime = FactorExecutor(json.loads(json.dumps(artifact)))
    assert not hasattr(runtime, 'classifier')
    matrix = list(itertools.product((False, True), repeat=3))
    for row in matrix:
        assert np.allclose(runtime.logits(dict(zip(names, row))), native_logits(model, row), atol=1e-15)
    assert np.allclose(runtime.predict_matrix(matrix), [runtime.probabilities(dict(zip(names, r))) for r in matrix])


def test_equal_observations_do_not_merge_different_semantic_predicates():
    m = {'scale': 1., 'bias': [0., 0., 0.], 'trees': [
        {'features': [0], 'values': [0., 0., 0., 1., 0., -1.]},
        {'features': [1], 'values': [0., 0., 0., 1., 0., -1.]}]}
    artifact = compile_factors(m, ['progress', 'completion'], {'progress': 'Some progress', 'completion': 'All complete'})
    assert len(artifact['factors']) == 2


def test_missing_or_non_boolean_evidence_and_tampering_rejected():
    names = ['a', 'b', 'c']; artifact = compile_factors(classifier(), names, dict(zip(names, names)))
    runtime = FactorExecutor(artifact)
    with pytest.raises(ValueError, match='Boolean'): runtime.probabilities({'a': 1, 'b': False, 'c': True})
    artifact['bias'][0] += 1
    with pytest.raises(ValueError, match='Changed'): FactorExecutor(artifact)


def test_constant_trees_and_multiple_source_orders():
    m = {'scale': 1., 'bias': [0., 0., 0.], 'trees': [
        {'features': [], 'values': [1., 2., 3.]}, {'features': [], 'values': [-1., -2., -3.]}]}
    runtime = FactorExecutor(compile_factors(m, ['a'], {'a': 'A'}))
    assert runtime.logits({'a': True}) == [0., 0., 0.]
