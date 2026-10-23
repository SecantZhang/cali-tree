from copy import deepcopy
from fractions import Fraction

import pytest

from critical.core.calibration import semantic_merge_v25 as semantic
from critical.core.calibration import pairwise_merge_v24 as baseline
from tests.unit.calitree.test_pairwise_merge_v24 import system_fixture


def test_distribution_overlap_is_normalized_and_empty_is_not_evidence():
    assert semantic.overlap(semantic.normalized({'a': 1, 'b': 1}), semantic.normalized({'a': 5, 'b': 5})) == 1
    assert semantic.overlap({'a': Fraction(1)}, {'b': Fraction(1)}) == 0
    assert semantic.overlap({}, {}) == 0


def test_shallow_profile_ignores_deep_nodes_and_collapses_quantifier_aliases():
    leaf = {'prediction': 0}
    tree = {'feature': 'meaning_progress_any', 'true': leaf,
            'false': {'feature': 'meaning_progress_all', 'true': leaf,
                      'false': {'feature': 'deep_all', 'true': leaf, 'false': leaf}}}
    assert semantic.predicate_profile(tree) == {'meaning_progress': Fraction(3, 2)}


def test_profiles_and_pairs_ignore_input_order_and_renamed_ids():
    data, programs, models, _, _ = system_fixture()
    bank = {m['runtime']['artifact_ref']: m for m in models}
    pairs, ps = semantic.ordered_pairs(bank, data, programs)
    assert semantic.ordered_pairs(dict(reversed(list(bank.items()))), list(reversed(data)), programs) == (pairs, ps)
    renamed = deepcopy(data); new_programs = {}; new_bank = deepcopy(bank)
    mapping = {r['source_group']: f'anonymous-{i}' for i, r in enumerate(data)}
    for r in renamed:
        old = r['source_group']; r['source_group'] = mapping[old]; r['case'] = 'unrelated'; r['batch'] = 'unused'
        new_programs[r['source_group']] = programs[old]
    for m in new_bank.values():
        m['policy']['training']['source_groups'] = [mapping[s] for s in m['policy']['training']['source_groups']]
    assert semantic.ordered_pairs(new_bank, renamed, new_programs) == (pairs, ps)


def test_unmatched_program_and_outside_scope_rejected():
    data, programs, models, _, _ = system_fixture(); bank = {m['runtime']['artifact_ref']: m for m in models}
    with pytest.raises(ValueError):
        semantic.profiles(bank, data, {})
    bad = deepcopy(programs); bad[data[0]['source_group']]['instruction'] = 'wrong'
    with pytest.raises(ValueError, match='mismatch'):
        semantic.profiles(bank, data, bad)


def test_id_scheduler_reproduces_v24_and_semantic_preserves_routes():
    data, programs, models, probes, gate = system_fixture()
    kwargs = {'config': baseline.Config(max_rounds=1, max_pair_fits=2), 'fit_config': baseline.learner.Config(max_depth=3)}
    control = baseline.develop(models, data, programs, gate, probes, **kwargs)
    for ordering in ('artifact_id', 'semantic'):
        result = semantic.develop(models, data, programs, gate, probes, ordering=ordering, **kwargs)
        for key in ('gate', 'models', 'accepted', 'initial_complexity', 'final_complexity', 'work', 'final_routing_check'):
            assert result[key] == control[key]
        assert len(result['schedules']) == 1
        assert result['work']['pair_fits'] <= 2


def test_profiles_only_credit_correct_child_support():
    data, programs, models, _, _ = system_fixture(); bank = {m['runtime']['artifact_ref']: m for m in models}
    correct = semantic.profiles(bank, data, programs)
    wrong = deepcopy(data)
    for row in wrong:
        row['reference'] = (row['reference'] + 1) % 3
    unsupported = semantic.profiles(bank, wrong, programs)
    assert all(p['supported_rows'] == 12 for p in correct.values())
    assert all(p['supported_rows'] == 0 and p['tasks'] == {} for p in unsupported.values())


def test_semantically_related_pair_precedes_artifact_id_order():
    from tests.unit.calitree.test_task_coverage import program
    data, programs, models, _, _ = system_fixture()
    # Three candidate handles: ID order starts with a mismatched task family.
    bank = {'a': deepcopy(models[0]), 'b': deepcopy(models[1]), 'c': deepcopy(models[1])}
    for row in data[:12]:
        programs[row['source_group']] = program(row['instruction'], 'presence')
    pairs, _ = semantic.ordered_pairs(bank, data, programs)
    control, _ = semantic.ordered_pairs(bank, data, programs, 'artifact_id')
    assert pairs[0]['children'] == ['b', 'c'] and pairs[0]['task_overlap'] == 1
    assert control[0]['children'] == ['a', 'b'] and control[0]['task_overlap'] == 0
    assert sorted(p['children'] for p in pairs) == sorted(p['children'] for p in control)
