from copy import deepcopy
from itertools import product

import pytest

from critical.core.calibration import shared_regions_v27 as shared
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_semantic_regions_v26 import fixture
from tests.unit.calitree.test_task_coverage import program


def test_boolean_simplification_removes_a_complementary_branch_and_absorbs():
    terms = {(1, frozenset({('a', True), ('b', True)})): {'scope'},
             (1, frozenset({('a', True), ('b', False)})): {'scope'},
             (1, frozenset({('a', True), ('b', True), ('c', False)})): {'scope'}}
    reduced, steps = shared.simplify(terms)
    assert reduced == {(1, frozenset({('a', True)})): {'scope'}}
    assert steps and shared.equivalent(terms, reduced)['passed']
    for bits in product((False, True), repeat=3):
        values = dict(zip(('a','b','c'), bits))
        assert any(shared.matches(k[1], values) for k in terms) == any(shared.matches(k[1], values) for k in reduced)


def test_same_label_does_not_allow_unsafe_merging_or_scope_cartesian_products():
    left = (2, frozenset({('a', True)})); right = (2, frozenset({('a', False)}))
    terms = {left: {'scopeA'}, right: {'scopeB'}}
    reduced, _ = shared.simplify(terms)
    assert reduced == terms
    assert not shared.equivalent(terms, {(2, frozenset()): {'scopeA', 'scopeB'}})['passed']
    assert not shared.equivalent(terms, {(0, left[1]): {'scopeA'}, right: {'scopeB'}})['passed']


def test_partial_scope_overlap_is_preserved_exactly():
    terms = {(0, frozenset({('a', True), ('b', True)})): {'s1','s2'},
             (0, frozenset({('a', True), ('b', False)})): {'s2','s3'}}
    reduced, _ = shared.simplify(terms)
    assert shared.equivalent(terms, reduced)['passed']
    assert not shared.implies_union(frozenset(), [frozenset({('a', True)})])[0]
    with pytest.raises(ValueError, match='budget'):
        shared.implies_union(frozenset(), [frozenset({('a', True)}), frozenset({('a', False)})], max_states=1)


def test_literal_canonicalization_deduplicates_without_assuming_feature_aliases():
    term = shared.cube([{'feature': 'meaning_available', 'value': True}]*2)
    assert len(term) == 1
    with pytest.raises(ValueError, match='Contradictory'):
        shared.cube([{'feature': 'meaning_available', 'value': True}, {'feature': 'meaning_available', 'value': False}])


def test_compiled_gate_preserves_routes_and_omits_old_region_executor():
    rows, programs, _, original = fixture()
    gate, report = shared.build(original, rows, programs)
    restored = shared.SharedRegionGate(gate.export())
    assert report['boolean_equivalence']['passed']
    assert gate.artifact['core_gate'] == original.previous.export()
    assert 'previous_gate' not in gate.artifact and gate.artifact['core_gate']['version'] != original.artifact['version']
    for row in rows:
        p = programs[row['source_group']]
        before, after = original.select(p, row['features']), restored.select(p, row['features'])
        assert (before['covered'], before['prediction']) == (after['covered'], after['prediction'])
        assert after['semantic_regions']
    assert not gate.shortlist(program('New appearance request'))['decision_ready']
    assert not gate.shortlist(program('Add something', 'presence'))['task_supported']
    assert not gate.select(program('New appearance request'), None)['covered']


def test_counts_deduplicate_sources_and_build_is_order_independent():
    rows, programs, _, original = fixture()
    gate, report = shared.build(original, rows, programs)
    again, report2 = shared.build(original, list(reversed(rows)), programs)
    assert gate.export() == again.export() and report == report2
    for region in gate.regions.values():
        expected = set()
        for row in rows:
            if region['region_ref'] in gate.select(programs[row['source_group']], row['features'])['semantic_regions']:
                expected.add(row['source_group'])
        assert region['support']['sources'] == len(expected)


def test_prior_conflict_veto_survives_and_tampered_artifacts_fail(monkeypatch):
    rows, programs, _, original = fixture(); gate, _ = shared.build(original, rows, programs)
    monkeypatch.setattr(gate.previous, 'select', lambda *args: {'covered': False, 'prediction': -1, 'reason': 'conflicting_supported_experts', 'matches': []})
    assert gate.select(programs[rows[0]['source_group']], rows[0]['features'])['reason'] == 'conflicting_supported_experts'
    artifact = gate.export(); r = artifact['regions'][0]; r['expert_refs'] = ['missing-expert']
    r['region_ref'] = digest({k:v for k,v in r.items() if k != 'region_ref'})
    artifact['artifact_ref'] = digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='references'):
        shared.SharedRegionGate(artifact)


def test_equivalent_regions_share_across_distinct_experts_without_double_counting():
    rows, programs, _, original = fixture()
    artifact = original.previous.export(); semantic = artifact['previous_gate']; base = semantic['base_gate']
    source_ref = next(iter(original.regions.values()))['expert_ref']
    clone = deepcopy(base['experts'][source_ref])
    relevant_rules = [r for r in base['rules'] if r['expert_ref'] == source_ref]
    common = set.intersection(*(set((c['feature'], c['value']) for c in semantic['envelopes'][digest(r)]['conditions']) for r in relevant_rules))
    feature, value = next((f,v) for f,v in sorted(common) if f not in clone['predicate_descriptions'])
    clone['tree'] = {'feature': feature, 'true': deepcopy(clone['tree']), 'false': deepcopy(clone['tree'])}
    clone['predicate_descriptions'][feature] = shared.evidence.FEATURES[feature]
    clone['artifact_ref'] = digest({k:v for k,v in clone.items() if k != 'artifact_ref'})
    base['experts'][clone['artifact_ref']] = clone
    for rule in relevant_rules:
        extra = deepcopy(rule); extra['expert_ref'] = clone['artifact_ref']; base['rules'].append(extra)
        semantic['envelopes'][digest(extra)] = deepcopy(semantic['envelopes'][digest(rule)])
    for item in (base, semantic, artifact):
        item['artifact_ref'] = digest({k:v for k,v in item.items() if k != 'artifact_ref'})
    previous = shared.core.restore(artifact)
    expanded = shared.old.build(previous, rows, programs)
    gate, report = shared.build(expanded, rows, programs)
    assert report['after']['regions'] < report['before']['regions']
    assert report['after']['cross_expert_regions'] > 0
    for region in gate.regions.values():
        if source_ref in region['expert_refs']:
            assert clone['artifact_ref'] in region['expert_refs']
            sources = {r['source_group'] for r in rows if region['region_ref'] in gate.select(programs[r['source_group']], r['features'])['semantic_regions']}
            assert region['support']['sources'] == len(sources)


def test_symbolic_equivalence_matches_exhaustive_small_boolean_domains():
    import random
    randomizer = random.Random(27)
    names = ('a','b','c','d')
    for _ in range(24):
        terms = {}
        for __ in range(8):
            term = frozenset((name, randomizer.choice((False, True))) for name in names if randomizer.random() < .65)
            terms.setdefault((randomizer.randrange(3), term), set()).add(randomizer.choice(('s1','s2')))
        reduced, _ = shared.simplify(terms)
        assert shared.equivalent(terms, reduced)['passed']
        for scope in ('s1','s2'):
            for bits in product((False, True), repeat=4):
                values = dict(zip(names,bits))
                before = {label for (label,term),ss in terms.items() if scope in ss and shared.matches(term,values)}
                after = {label for (label,term),ss in reduced.items() if scope in ss and shared.matches(term,values)}
                assert before == after
