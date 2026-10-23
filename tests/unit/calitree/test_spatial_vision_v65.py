import numpy as np

from run.spatial_vision_features_v65 import probes, locate, relative_margin, statistics, SCORES


def program(instruction, target='original book', reference='headphones'):
    return {'checks': [{'role': 'outcome', 'kind': 'spatial_relation', 'target': target, 'reference': reference, 'requirement_ids': ['r1']}],
            'requirements': [{'id': 'r1', 'source_quote': instruction}]}


def test_probe_types_are_instruction_relative_and_reject_unsupported_depth():
    assert probes(program('Move book to the left of the headphones'))[0]['axis'] == 'left'
    assert probes(program('Move book behind the headphones')) == []
    assert probes(program('Do not move book to the left of the headphones')) == []
    p = probes(program('Move book and headphones closer to each other', target='book and headphones', reference='Their source distance'))
    assert p[0]['type'] == 'proximity' and p[0]['sign'] == 1.
    p = probes(program('Lift book up', reference='Its source position'))
    assert p[0]['type'] == 'motion' and p[0]['axis'] == 'above'


def test_goal_margin_is_translation_invariant_and_left_right_symmetric():
    target, reference = np.asarray([.2, .3]), np.asarray([.8, .7])
    expected = relative_margin(target, reference, 'left')
    assert np.isclose(expected, .6)
    assert np.isclose(relative_margin(target + .1, reference + .1, 'left'), expected)
    assert np.isclose(relative_margin([.8, .3], [.2, .7], 'right'), expected)


def test_localization_and_identical_pair_have_no_spurious_motion():
    grid = np.eye(9)
    vectors = np.concatenate([grid[:5], grid])
    center, score, gap = locate(vectors, grid[0])
    assert np.allclose(center, [1/6, 1/6], atol=1e-10)
    assert score == 1 and gap == 1
    probe = {'type': 'axis', 'axis': 'left', 'target_vector': grid[0], 'reference_vector': grid[8]}
    result = statistics(vectors, vectors, [probe])
    assert result['spatial_axis_available'] and not result['spatial_motion_available']
    assert np.isclose(result['spatial_axis_delta_mean'], 0.)
    assert np.isclose(result['spatial_axis_edited_margin_min'], 2/3)
    assert not any('coordinate' in name or 'case' in name for name in result)
    assert all(statistics(vectors, vectors, [])[name] == 0 for name in SCORES)
