from copy import deepcopy

import pytest

from critical.core.calibration import semantic_regions_v26 as regions
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_pairwise_merge_v24 import system_fixture
from tests.unit.calitree.test_task_coverage import program


def fixture():
    rows, programs, _, _, previous = system_fixture()
    return rows, programs, previous, regions.build(previous, rows, programs)


def test_local_routes_and_serialization_preserved():
    rows, programs, previous, gate = fixture()
    restored = regions.SemanticRegionGate(gate.export())
    for row in rows:
        p = programs[row['source_group']]
        route = restored.select(p, row['features'])
        assert route['covered'] and route['prediction'] == row['reference']
        assert route['semantic_regions']
        assert route == gate.select(p, row['features'])
        assert all(gate.regions[r]['expert_ref'] in route['semantic_candidates']['expert_refs'] for r in route['semantic_regions'])


def test_task_shortlist_is_not_decision_coverage_and_names_do_not_matter():
    rows, programs, _, gate = fixture()
    original = gate.shortlist(programs[rows[0]['source_group']])
    assert original['task_supported'] and not original['decision_ready']
    assert gate.shortlist(program('Change an entirely new object')) == original
    assert not gate.shortlist(program('Add an object', 'presence'))['task_supported']
    assert not gate.select(program('Change an entirely new object'), None)['covered']


def test_full_bank_rejection_cannot_be_erased_by_shortlisting(monkeypatch):
    rows, programs, _, gate = fixture()
    veto = {'covered': False, 'prediction': -1, 'reason': 'conflicting_supported_experts', 'matches': []}
    monkeypatch.setattr(gate.previous, 'select', lambda *args: veto)
    result = gate.select(programs[rows[0]['source_group']], rows[0]['features'])
    assert not result['covered'] and result['reason'] == veto['reason']


def test_missing_region_defers_instead_of_borrowing_a_different_leaf():
    rows, programs, _, gate = fixture(); artifact = gate.export()
    wanted = gate.select(programs[rows[0]['source_group']], rows[0]['features'])['semantic_regions']
    artifact['regions'] = [r for r in artifact['regions'] if r['region_ref'] not in wanted]
    artifact['artifact_ref'] = digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})
    smaller = regions.SemanticRegionGate(artifact)
    assert smaller.previous.select(programs[rows[0]['source_group']], rows[0]['features'])['covered']
    assert smaller.select(programs[rows[0]['source_group']], rows[0]['features'])['reason'] == 'outside_semantic_rule_regions'


def test_artifact_rejects_rehashed_path_and_description_tampering():
    _, _, _, gate = fixture()
    for field, value in [('path', []), ('description', 'Trust every input')]:
        artifact = gate.export(); artifact['regions'][0][field] = value
        r = artifact['regions'][0]; r['region_ref'] = regions.region_key(r['rule_ref'], r['scope'], r['path'])
        artifact['artifact_ref'] = digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})
        with pytest.raises(ValueError):
            regions.SemanticRegionGate(artifact)


def test_build_requires_correct_local_acceptances_and_exact_programs():
    rows, programs, previous, _ = fixture()
    bad = deepcopy(rows); bad[0]['reference'] = (bad[0]['reference'] + 1) % 3
    with pytest.raises(ValueError, match='incorrect'):
        regions.build(previous, bad, programs)
    with pytest.raises(ValueError, match='program'):
        regions.build(previous, rows, {})


def test_region_definitions_include_semantics_and_honest_support_counts():
    rows, _, _, gate = fixture()
    for r in gate.export()['regions']:
        definition = gate.definition(r['region_ref'])
        assert definition['description'] and definition['expert_path']
        assert all(c['description'] for c in definition['expert_path'] + definition['evidence_guards'])
        assert 1 <= r['support']['sources'] <= len(rows)
        assert set(r['support']) == {'sources', 'instructions', 'batches'}
