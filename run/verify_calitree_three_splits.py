"""Offline audit of the three fixed Luna replications; no calls or fitting."""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import digest
from critical.core.decision.semantic_interpretation_v5 import make_input
from critical.core.decision.bound_evidence_v2 import image_identity, derive_record
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import gate, rank
from run.calitree_union_reuse import selection_key
from run.calitree_three_splits import prepare, read, exact, IDENTITY


def audit_input_bindings(cases, splits):
    by_case = {r['case']: r for r in cases}
    for split in splits:
        for part in ('train', 'evaluation'):
            for row in split[part]:
                original = by_case[row['case']]
                if any(row[k] != original[k] for k in ('id', 'instruction', 'reference', 'group', 'image_hashes')):
                    raise ValueError('Exact selected input was conflated with a source-pixel sibling')


def audit(out):
    manifest = prepare(out); report = read(out / 'results.json'); count = 0
    audit_input_bindings(manifest['cases'], [read(out / 'splits' / ('split' + str(i) + '.json')) for i in (1, 2, 3)])
    raw = {r['case']: r for r in read(out / 'extraction/observations.json')}
    meanings = {r['case']: r for r in read(out / 'interpretations.json')}
    records = read(out / 'portable_records.json')
    model_jobs = list(out.glob('extraction/ledgers/*/*/jobs/*.json')) + list(out.glob('interpretation_ledgers/*/jobs/*.json'))
    models, outcomes = Counter(), Counter()
    for path in model_jobs:
        job = read(path); budget = read(path.parent.parent / 'budget.json')
        assert budget['limits']['identity'] == IDENTITY
        allowance = 2 if manifest.get('compiler_revision') and path.parent.parent.name == 'compile' else 1
        assert 1 <= budget['calls'] <= allowance
        assert len(list(path.parent.glob('*.json'))) == budget['calls']
        outcomes[job['outcome']] += 1
        if job.get('response'):
            models[job['response']['model']] += 1
            assert job['response']['model'] == 'gpt-6-luna'
        count += 1
    assert len(model_jobs) <= (4 if manifest.get('compiler_revision') else 3) * manifest['unique_inputs']
    if manifest.get('compiler_revision'):
        from run.calitree_three_splits_compiler_v3 import audit_compiler
        assert audit_compiler(out, manifest, list(raw.values()))['passed']
    if (out / 'input_identity_revision.json').exists():
        revision = read(out / 'input_identity_revision.json')
        assert len(model_jobs) <= revision['combined_attempt_ceiling'] <= revision['original_call_budget']
    for case in manifest['cases']:
        observed, meaning = raw[case['case']], meanings[case['case']]
        if observed['record']:
            pair = image_identity(case['evidence'])[1]
            assert observed['record'] == derive_record(observed['compilation']['program'], observed['observation']['observation'], pair)
            assert records[case['case']]['features'] == project(observed['compilation']['program'],
                observed['observation']['observation'], pair, meaning['interpretation'])
            semantic_jobs = [read(p) for p in (out / 'interpretation_ledgers' / case['case'] / 'jobs').glob('*.json')]
            assert len(semantic_jobs) == 1
            assert semantic_jobs[0]['payload'] == make_input(observed['compilation']['program'], observed['observation']['observation'], pair)
        else:
            assert records[case['case']]['features'] is None
        count += 1
    all_evaluation = set()
    for name in ('split1', 'split2', 'split3'):
        directory = out / name; split = read(out / 'splits' / (name + '.json'))
        result = read(directory / 'results.json'); train = read(directory / 'training_data.json')
        assert len(train) == 48
        assert {r['source_group'] for r in train} == {r['group'] for r in split['train']}
        assert all(r['features'] == records[r['case']]['features'] for r in train)
        eval_set = {r['group'] for r in split['evaluation']}
        assert not all_evaluation & eval_set
        all_evaluation |= eval_set
        by_source = {r['source_group']: r for r in train}
        alternatives = []
        for run_name in ('original4_reuse', 'split8_reuse', 'semantic8_reuse'):
            p = directory / run_name / 'result.json'
            if not p.exists():
                assert (directory / run_name / 'failure.json').exists()
                continue
            run = read(p)
            for node in run['registry'].values():
                assert set(node['fit_sources']) <= set(by_source)
                assert set(node['policy']['training']['source_groups']) == set(node['fit_sources'])
                cohort = [by_source[k] for k in node['fit_sources']]
                predictions = PortableRuleExecutor(node['runtime']).predict_records([r['features'] for r in cohort])
                assert metrics([p['prediction'] for p in predictions], [r['reference'] for r in cohort]) == node['metrics']
                if node['children']:
                    children = [run['registry'][k] for k in node['children']]
                    assert gate(node, children, cohort)['status'] == 'accepted'
                count += 1
            alternatives.extend((run_name, run['registry'][k]) for k in run['root_candidates'])
        chosen = min(alternatives, key=lambda pair: (*selection_key(pair[0], {'root': pair[1]}), pair[1]['node_id'])) if alternatives else None
        assert (chosen[1]['node_id'] if chosen else None) == result['selection']['node_id']
        policies = read(directory / 'frozen_policies.json')
        assert digest(policies) == result['selection']['frozen_policies_ref']
        assert policies['merged'] == (chosen[1]['runtime'] if chosen else None)
        direct_candidates = [read(p)['result'] for p in (directory / 'direct_control/fits').glob('*.json')]
        direct = min((v for v in direct_candidates if v and v['portable']), key=rank, default=None)
        assert policies['direct'] == (direct['runtime'] if direct else None)
        for arm, policy in policies.items():
            cohort = result['arms'][arm]['cases']
            assert len(cohort) == 12 and {r['source_group'] for r in cohort} == eval_set
            pred = PortableRuleExecutor(policy).predict_records([records[r['case']]['features'] for r in cohort]) if policy else [
                {'prediction': -1, 'trace': [], 'reason': 'no_qualifying_complete_policy'} for r in cohort]
            for row, replay in zip(cohort, pred):
                assert all(row[k] == v for k, v in replay.items())
                assert row['reference'] == records[row['case']]['reference']
                count += 1
            assert result['arms'][arm]['metrics'] == metrics([p['prediction'] for p in pred], [r['reference'] for r in cohort])
    assert len(all_evaluation) == 36
    for arm, expected in report['pooled_evaluation'].items():
        rows = [r for s in report['replications'] for r in s['arms'][arm]['cases']]
        assert expected == metrics([r['prediction'] for r in rows], [r['reference'] for r in rows])
    result = {'passed': True, 'offline_artifact_and_prediction_checks': count, 'model_jobs': len(model_jobs),
        'returned_models': dict(models), 'outcomes': dict(outcomes), 'evaluation_sources': 36,
        'new_api_calls_in_verification': 0, 'new_fits_in_verification': 0, 'reserved_test_predictions': 0,
        'all_three_sampled_splits_unchanged_after_model_switch': read(out / 'model_change.json')['all_three_sampled_splits_unchanged']}
    exact(out / 'verification.json', result); print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
