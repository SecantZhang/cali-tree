"""Audit all reviewed rejections, protected routes and raw local preservation."""
import argparse
import json
from pathlib import Path

from critical.core.calibration import counterexample_coverage_v23 as calibration
from critical.core.calibration.evidence_support_v21 import SupportedCoverageGate
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import image_identity
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_evidence_coverage_v20 import CachedRegularCalls, baseline_prediction, scores
from run.calitree_task_coverage import ROOT, IDENTITY, read, fingerprint, exact


def audit(out):
    manifest = read(out / 'manifest.json'); protocol = read(out / 'protocol.json')
    assert digest(protocol) == manifest['protocol_ref']
    for name, expected in manifest['source_hashes'].items():
        assert fingerprint(name) == expected, name
    for name, expected in manifest['code_hashes'].items():
        assert fingerprint(ROOT / name) == expected, name
    previous = Path(manifest['previous_gate_run']); prior = Path(manifest['prior_directory'])
    meta = read(prior / 'manifest.json')['cases']; calls = CachedRegularCalls(prior)
    local = []; development = []; rebuilt_splits = []; rejected = protected_transfers = raw_hits = batches = clauses = literals = loo_rejected = 0
    for i in (1, 2, 3):
        cohorts, bound, protected, errors, _ = load_examples(previous, i)
        old = SupportedCoverageGate(read(previous / f'split{i}/gate.json'))
        rebuilt, report = calibration.fit(old, [bound[r['case']]['example'] for r in protected], [bound[r['case']]['example'] for r in errors])
        artifact = read(out / f'split{i}/gate.json')
        assert rebuilt.export() == artifact and report == read(out / f'split{i}/fit.json')
        gate = calibration.RejectionCoverageGate(artifact)
        assert artifact['previous_gate'] == old.export()  # No expert or old gate edits.
        serialized = json.dumps(artifact)
        for p in bound.values():
            assert p['example']['source_group'] not in serialized
            assert p['example']['program']['instruction'] not in serialized
        for clause in artifact['support_clauses']:
            assert 1 <= len(clause) <= 3
            for p in protected:
                example = bound[p['case']]['example']
                values = calibration.features.feature_values(example['program'], example['features'])
                assert any(values[c['feature']] == c['value'] for c in clause)
            clauses += 1; literals += len(clause)
        cache = BoundEvidenceCache(IDENTITY, artifact=read(out / f'split{i}/evidence_cache.json'))
        judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=IDENTITY)
        error_ids = {r['case'] for r in errors}; control_ids = {r['case'] for r in protected if r['scope'] != 'local'}
        result = {'split': i, 'clauses': report['clauses'], 'literal_tests': report['literal_tests']}
        loo = []
        for error in errors:
            reduced, _ = calibration.fit(old, [bound[r['case']]['example'] for r in protected],
                                         [bound[r['case']]['example'] for r in errors if r['case'] != error['case']])
            e = bound[error['case']]['example']
            ok = not reduced.select(e['program'], e['features'])['covered']; loo_rejected += ok
            loo.append({'case': error['case'], 'rejected_without_its_counterexample': ok})
        assert loo == read(out / f'split{i}/leave_one_error_out.json')
        result['leave_one_error_out'] = {'rejected': sum(x['rejected_without_its_counterexample'] for x in loo), 'total': len(loo)}
        for scope, before_rows in cohorts.items():
            records = read(out / f'split{i}/{scope}_predictions.json'); before_by_case = {r['case']: r for r in before_rows}
            assert [r['case'] for r in records] == [r['case'] for r in before_rows]
            for saved in records:
                case = meta[saved['case']]; b = bound[saved['case']]; e = b['example']; before = before_by_case[saved['case']]
                pair = image_identity(case['evidence'])[1]
                record = calibration.features.project(e['program'], b['observation'], pair, b['interpretation'])
                assert record == e['features'] and case['reference'] == saved['reference'] == e['reference']
                before_route = old.select(e['program'], record); assert before_route == before['route']
                values = calibration.features.feature_values(e['program'], record)
                violations = [digest(c) for c in artifact['support_clauses'] if not any(values[t['feature']] == t['value'] for t in c)] if before_route['covered'] else []
                expected_covered = before_route['covered'] and not violations
                assert gate.select_bound(e['program'], b['observation'], pair, b['interpretation']) == saved['route']
                assert saved['route']['covered'] == expected_covered
                if violations:
                    assert saved['route']['reason'] == 'unsupported_feature_combination'
                    assert saved['route']['violated_support_clauses'] == violations
                regular = baseline_prediction(calls, case)
                expected = before_route['prediction'] if expected_covered else regular
                assert saved['regular'] == regular and saved['evidence_gate_tree'] == expected
                if expected_covered:
                    assert saved['served_by'] == 'frozen_tree' and saved['fallback_execution_ref'] is None
                else:
                    assert saved['served_by'] == 'regular_judge'
                    assert saved['fallback_execution_ref'] == calls.requests[-1]['execution_ref']
                if scope == 'local':
                    # Verify the actual raw interface, independent of the saved
                    # route or supplied feature record, and rename the request.
                    raw = judge.judge(case['instruction'], case['evidence'], case_id='renamed-audit-' + str(raw_hits))
                    assert raw['evidence_source'] == 'content_cache' and raw['source'] == 'frozen_tree'
                    assert LABELS.index(raw['judgment']['label']) == saved['reference']
                    assert expected_covered and expected == saved['reference']; raw_hits += 1
                elif saved['case'] in error_ids:
                    assert not expected_covered; rejected += 1
                elif saved['case'] in control_ids:
                    assert expected_covered and expected == saved['reference']; protected_transfers += 1
                else:
                    assert saved['route'] == before_route and saved['evidence_gate_tree'] == before['evidence_gate_tree']
            result[scope] = scores(records)
            result[scope]['new_rejections'] = sum(r['previous_route']['covered'] and not r['route']['covered'] for r in records)
            if scope == 'local':
                result['children'] = {b: scores([r for r in records if r['batch'] == b]) for b in sorted({r['batch'] for r in records})}
                assert all(v['evidence_gate_tree_correct'] == v['total'] == 12 for v in result['children'].values())
                result['preserves_all_original_children'] = True; batches += len(result['children']); local.extend(records)
            else:
                development.extend(records)
        rebuilt_splits.append(result)
    summary = read(out / 'results.json')
    assert summary['splits'] == rebuilt_splits and summary['local'] == scores(local) and summary['development'] == scores(development)
    assert rejected == summary['reviewed_error_slots'] == 22 and protected_transfers == 38 and raw_hits == 144 and batches == 12
    assert summary['new_model_calls'] == summary['reserved_final_predictions'] == 0
    review = read(out / 'error_review.json')
    assert len(review) == 22 and all(r['rejection_conditions'] for r in review)
    checks = {'passed': True, 'reviewed_errors_rejected': rejected, 'correct_transfer_routes_preserved': protected_transfers,
              'raw_local_tree_predictions_correct': raw_hits, 'original_child_batches_preserved': batches,
              'local_and_development_predictions_replayed': len(local) + len(development),
              'clauses_verified': clauses, 'literal_tests_verified': literals,
              'leave_one_error_out_rejections': loo_rejected,
              'no_case_identifier_blacklist': True, 'previous_gate_and_expert_verdicts_unchanged': True,
              'new_model_calls': 0, 'reserved_final_predictions': 0,
              'validation_scope': 'Post-calibration regression verification; the reviewed transfer outcomes are development data.'}
    exact(out / 'verification.json', checks)
    exact(out / 'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*'))
                                                 if p.is_file() and p.name != 'completion_seal.json'},
                                        'auditor_sha256': fingerprint(__file__)})
    print(checks)
    return checks


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    audit(p.parse_args().output_dir.resolve())
