from copy import deepcopy

import numpy as np
import pytest

from run.calitree_matched_policy_v58 import half_cases, fixed_splits, decisions


def fixtures():
    local = [{'case': 'local', 'source_group': 'protected', 'reference': 0}]
    recent = [{'case': f'R{i}', 'source_group': f'g{i // 2}', 'reference': i % 3} for i in range(30)]
    additions = [{'case': f'{uid}-{editor}', 'task_uid': uid, 'editor': editor, 'source_group': source}
                 for uid, source in [('protected-task', 'protected'), ('a', 'g0'), ('b', 'g0'), ('c', 'g10')]
                 for editor in ('e1', 'e2', 'e3', 'e4')]
    return local, recent, additions


def test_every_held_source_sibling_excluded_without_changing_primary_folds():
    local, recent, additions = fixtures()
    examples = local + recent + additions
    zero = list(fixed_splits(local, recent, additions, 'zero'))
    for coverage in ('half', 'full'):
        splits = list(fixed_splits(local, recent, additions, coverage))
        assert [held for _, held in splits] == [held for _, held in zero]
        for train, held in splits:
            sources = {examples[i]['source_group'] for i in held}
            assert not sources & {examples[i]['source_group'] for i in train}
            assert 0 in train
            if 'g0' in sources:
                assert all(examples[i].get('task_uid') not in ('a', 'b') for i in train)
        assert sorted(i for _, held in splits for i in held) == list(range(1, 31))


def test_half_sample_is_order_and_label_independent_two_per_task():
    _, _, additions = fixtures()
    chosen = half_cases(additions)
    modified = deepcopy(list(reversed(additions)))
    for i, e in enumerate(modified):
        e.update(reference=i % 3, regular=(i + 1) % 3, features={'different': True})
    assert half_cases(modified) == chosen
    for uid in {e['task_uid'] for e in additions}:
        assert sum(e['case'] in chosen for e in additions if e['task_uid'] == uid) == 2
    with pytest.raises(ValueError, match='four distinct'):
        half_cases(additions[:-1])


def test_gates_recompute_routed_support_and_preserve_missing_fallback():
    e = {'features': {'valid': True}, 'regular': 2}
    decision = decisions(np.array([.5, .5, 0.]), e, [-1, 1, 0])
    assert decision['direct'] == decision['routed'] == 0
    assert decision['gate_0.5'] == 0 and decision['gate_0.65'] == 2
    assert decision['accept_0.5'] and not decision['accept_0.65']
    missing = decisions(np.array([1., 0., 0.]), {'features': None, 'regular': -1}, [0, 1])
    assert missing['direct'] == missing['routed'] == missing['gate_0.0'] == -1
    assert not missing['accept_0.0']
