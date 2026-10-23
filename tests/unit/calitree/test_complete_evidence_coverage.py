from critical.core.calibration import evidence_coverage_v20 as base, complete_evidence_coverage as complete
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_evidence_coverage_v20 import guarded_data


def test_retained_child_completes_missing_region_without_changing_existing_predictions():
    data, programs, models = guarded_data(); full, _ = base.build(models, data, programs)
    artifact = full.export(); artifact['rules'] = artifact['rules'][:1]
    used = {r['expert_ref'] for r in artifact['rules']}; artifact['experts'] = {k:v for k,v in artifact['experts'].items() if k in used}
    artifact['artifact_ref'] = digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})
    partial = base.EvidenceCoverageGate(artifact)
    assert sum(partial.select(programs[r['source_group']], r['features'])['covered'] for r in data) == 4
    final, report = complete.complete(partial, models, data, programs)
    assert report['additional_search'] and len(report['added_regions']) == 1 and report['uncovered_local_sources'] == 0
    for row in data:
        before = partial.select(programs[row['source_group']], row['features'])
        after = final.select(programs[row['source_group']], row['features'])
        assert after['covered'] and after['prediction'] == row['reference']
        if before['covered']:
            assert after['prediction'] == before['prediction']
    assert set(final.base.artifact['experts']) <= {m['runtime']['artifact_ref'] for m in models}


def test_complete_gate_does_not_search_again():
    data, programs, models = guarded_data(); full, _ = base.build(models, data, programs)
    final, report = complete.complete(full, models, data, programs)
    assert not report['additional_search'] and not report['added_regions']
    assert report['uncovered_local_sources'] == 0


def test_completion_budget_cannot_force_an_unsupported_route():
    data, programs, models = guarded_data(xor=True)
    partial, _ = base.build(models, data, programs, base.Config(max_guards=1))
    final, report = complete.complete(partial, models, data, programs)
    assert report['uncovered_local_sources'] == 8 and not report['added_regions']
    assert all(not final.select(programs[r['source_group']], r['features'])['covered'] for r in data)
