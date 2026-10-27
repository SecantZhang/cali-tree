from copy import deepcopy
import pytest

from critical.core.calibration.semantic_residual_runtime_v104 import compile_residual, ResidualExecutor, f32
from critical.core.calibration.local_semantic_runtime_v99 import content_ref
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS


def compiled():
    native = {'scale_and_bias': [1, [0., 0., 0.]], 'features_info': {'float_features': [{'feature_index': 0, 'flat_feature_index': 0}]},
              'oblivious_trees': [{'splits': [{'split_type': 'FloatFeature', 'float_feature_index': 0, 'border': .5}],
                                  'leaf_values': [0., 0., 0., -.001, .001, 0.]} for _ in range(128)]}
    meta = {'version': 'source-held-semantic-residual-v103', 'depth': 2, 'iterations': 128, 'strength': 1., 'features': ['local_progress_witness'],
            'feature_descriptions': {'local_progress_witness': DESCRIPTIONS['local_progress_witness']}}
    return compile_residual(native, meta)


def test_shared_clauses_preserve_weights_and_require_bound_boolean_concepts():
    artifact = compiled(); assert len(artifact['clauses']) == 1
    executor = ResidualExecutor(artifact)
    assert executor.evaluate({'local_progress_witness': False}, [.51, .48, .01])['prediction'] == 0
    assert executor.evaluate({'local_progress_witness': True}, [.51, .48, .01])['prediction'] == 1
    with pytest.raises(ValueError, match='unavailable'):
        executor.evaluate({'local_progress_witness': 1}, [.51, .48, .01])


def test_rendered_policy_cannot_drift_from_executable_weights_even_when_rehashed():
    artifact = compiled(); changed = deepcopy(artifact); changed['clauses'][0]['weights'][1] += .1
    changed['artifact_ref'] = content_ref(changed)
    with pytest.raises(ValueError, match='Rendered'):
        ResidualExecutor(changed)


def test_continuous_threshold_uses_catboost_float32_conversion():
    artifact = compiled(); clause = artifact['clauses'][0]; name = 'teacher_support_yes'
    desc = 'The existing teacher assigns this model support to yes; it is not calibrated correctness.'
    clause['conditions'][0]['feature'] = name; clause['conditions'][0]['border'] = f32(.7)
    artifact['features'] = [name]; artifact['feature_descriptions'] = {name: desc}
    from critical.core.calibration.semantic_residual_runtime_v104 import render
    artifact['rubric'] = render(artifact); artifact['artifact_ref'] = content_ref(artifact)
    executor = ResidualExecutor(artifact)
    # A double just above the float32 border still belongs to its <= leaf.
    assert executor.evaluate({name: f32(.7)+1e-10}, [.51, .48, .01])['residual'] == [0., 0., 0.]
    assert executor.evaluate({name: f32(.7)+1e-6}, [.51, .48, .01])['prediction'] == 1
