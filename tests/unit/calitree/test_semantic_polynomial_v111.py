from itertools import product
import numpy as np

from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration.semantic_residual_runtime_v104 import compile_residual, ResidualExecutor
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS


def fixture(repeated=False):
    names = ['local_progress_witness', 'local_any_uncertainty']
    native = {'scale_and_bias': [1., [.01, -.02, .01]], 'features_info': {'float_features': [
        {'feature_index': i, 'flat_feature_index': i} for i in range(2)]},
        'oblivious_trees': [{'splits': [{'split_type': 'FloatFeature', 'float_feature_index': 0, 'border': .5},
                                      {'split_type': 'FloatFeature', 'float_feature_index': 0 if repeated else 1, 'border': .5}],
                            'leaf_values': [.001, -.001, 0., -.002, .001, .001, .001, .002, -.003, -.003, -.001, .004]} for _ in range(128)]}
    meta = {'version': 'source-held-semantic-residual-v103', 'depth': 2, 'iterations': 128, 'strength': 1., 'features': names,
            'feature_descriptions': {n: DESCRIPTIONS[n] for n in names}}
    return native, meta


def test_shared_terms_match_every_branch_and_keep_actual_interaction():
    native, meta = fixture(); old = ResidualExecutor(compile_residual(native, meta)); compressed = compile_polynomial(native, meta)
    new = ResidualExecutor(compressed)
    assert len(compressed['clauses']) == 3 and sum(len(c['conditions']) == 2 for c in compressed['clauses']) == 1
    for flags in product((False, True), repeat=2):
        values = dict(zip(meta['features'], flags)); a = old.evaluate(values, [.51, .48, .01]); b = new.evaluate(values, [.51, .48, .01])
        assert np.allclose(a['residual'], b['residual'], atol=1e-12, rtol=0) and a['prediction'] == b['prediction']


def test_repeated_split_predicates_reduce_without_changing_any_valid_input():
    native, meta = fixture(repeated=True); old = ResidualExecutor(compile_residual(native, meta)); compiled = compile_polynomial(native, meta); new = ResidualExecutor(compiled)
    assert all(len(c['conditions']) == 1 for c in compiled['clauses'])
    for flag in (False, True):
        values = dict.fromkeys(meta['features'], flag)
        assert np.allclose(old.evaluate(values, [.2, .3, .5])['residual'], new.evaluate(values, [.2, .3, .5])['residual'], atol=1e-12, rtol=0)


def test_constant_model_keeps_a_valid_bias_only_executable_policy():
    native, meta = fixture()
    native['oblivious_trees'] = [{'splits': [], 'leaf_values': [0., 0., 0.]} for _ in range(128)]
    compiled = compile_polynomial(native, meta); executor = ResidualExecutor(compiled)
    assert compiled['features'] == []
    result = executor.evaluate({}, [.2, .3, .5])
    assert result['residual'] == [.01, -.02, .01] and result['prediction'] == 2


def test_multiple_numeric_bounds_reduce_to_the_strictest_float32_threshold():
    native, meta = fixture(repeated=True)
    from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT
    meta['features'][0] = 'teacher_support_yes'
    meta['feature_descriptions'] = {n: {**DESCRIPTIONS, **SUPPORT}[n] for n in meta['features']}
    for tree in native['oblivious_trees']:
        tree['splits'][0]['border'] = .3; tree['splits'][1]['border'] = .7
    old = ResidualExecutor(compile_residual(native, meta)); compiled = compile_polynomial(native, meta); new = ResidualExecutor(compiled)
    assert all(len(t['conditions']) <= 1 for t in compiled['clauses'])
    for value in (.1, .3, .5, .7, .9):
        values = {'teacher_support_yes': value, 'local_any_uncertainty': False}
        a = old.evaluate(values, [.2, .3, .5]); b = new.evaluate(values, [.2, .3, .5])
        assert np.allclose(a['residual'], b['residual'], atol=1e-12, rtol=0) and a['prediction'] == b['prediction']
