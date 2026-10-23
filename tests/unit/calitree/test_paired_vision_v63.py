import numpy as np
import pytest

from run.paired_vision_features_v63 import query_plan, crop_boxes, statistics, predicates, SPECS, normalized


def test_property_probes_follow_authorized_endpoint_and_not_retention_words():
    p = {'instruction': 'Make the red cylinder matte', 'checks': [{'role': 'outcome', 'kind': 'attribute', 'target': 'the original red cylinder'}],
         'contract': {'authorized_changes': ['Make the red cylinder matte while retaining the glossy unrelated sphere.']}}
    plan = query_plan(p)
    assert [probe['family'] for probe in plan['probes']] == ['finish']
    assert 'matte surface' in plan['probes'][0]['positive']
    p['contract']['authorized_changes'] = ['Change the red cylinder color from red to blue.']
    plan = query_plan(p)
    assert len(plan['probes']) == 1 and plan['probes'][0]['family'] == 'color'
    assert 'blue cylinder' in plan['probes'][0]['positive']


def test_fixed_grid_has_full_view_and_thirteen_local_views():
    boxes = crop_boxes(480, 320)
    assert len(boxes) == 14 and boxes[0] == (0, 0, 480, 320)
    assert all(0 <= a < c <= 480 and 0 <= b < d <= 320 for a, b, c, d in boxes)


def test_identical_or_relocated_patch_content_has_zero_property_delta():
    rng = np.random.RandomState(2)
    source = normalized(rng.normal(size=(14, 8)))
    text = {'target': rng.normal(size=8), 'goal': rng.normal(size=8),
            'probes': [{'positive': rng.normal(size=8), 'negative': rng.normal(size=(2, 8))}]}
    original = statistics(source, source, text)
    edited = source.copy(); edited[1:] = edited[1:][::-1]
    moved = statistics(source, edited, text)
    assert np.isclose(original['global_preservation'], 1.) and np.isclose(original['target_match'], 1.)
    assert np.isclose(original['goal_patch_delta'], 0.) and np.isclose(original['property_delta_mean'], 0.)
    assert all(np.isclose(original[k], moved[k]) for k in original)
    assert set(predicates(original)) == set(SPECS)


def test_property_scores_capture_change_direction_without_labels():
    source, edited = np.tile([0., 1.], (14, 1)), np.tile([1., 0.], (14, 1))
    text = {'target': np.asarray([0., 1.]), 'goal': np.asarray([1., 0.]),
            'probes': [{'positive': np.asarray([1., 0.]), 'negative': np.asarray([[0., 1.]])}]}
    a, b = statistics(source, edited, text), statistics(edited, source, text)
    assert a['property_delta_mean'] > 0 and b['property_delta_mean'] < 0
    assert predicates(a)['vision_property_delta_mean_ge_0.1']
    assert not predicates(b)['vision_property_delta_mean_ge_0.1']
    assert all(type(v) is bool for v in predicates(a).values())


def test_missing_and_invalid_vectors_do_not_silently_create_coverage():
    assert predicates(None) == dict.fromkeys(SPECS, False)
    with pytest.raises(ValueError, match='nonzero'):
        normalized(np.zeros((14, 8)))
