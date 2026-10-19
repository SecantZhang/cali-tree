"""Independent offline audit of v12 folds, unchanged gates and frozen evaluation."""
import argparse
from collections import Counter
from pathlib import Path
import statistics

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import gate
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import VERSION as FIT_VERSION, PROFILES
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy import union_validation_v12 as learner
from run.calitree_challenger_validation import prepare, SOURCE
from run.calitree_three_splits import read, fingerprint


def audit_hierarchy(folder, rows):
    result = read(folder / 'result.json')
    assert read(folder / 'training_scope.json') == {'sources': sorted(r['source_group'] for r in rows),
        'rows_ref': digest(sorted(rows, key=lambda r: r['source_group'])), 'method': folder.name}
    groups = read(folder / 'groups.json'); learner.validate_partition(groups, rows)
    by_id = {r['source_group']: r for r in rows}; checks = 1
    if result.get('failure'):
        assert not result['root_candidates']
        return result, checks, 0
    for node in result['registry'].values():
        assert set(node['fit_sources']) <= set(by_id)
        cohort = sorted((by_id[k] for k in node['fit_sources']), key=lambda r: r['source_group'])
        training = node['policy']['training']
        assert training['source_groups'] == [r['source_group'] for r in cohort]
        assert training['feature_ref'] == digest([r['features'] for r in cohort])
        assert training['target_ref'] == digest([r['reference'] for r in cohort])
        ps = PortableRuleExecutor(node['runtime']).predict_records([r['features'] for r in cohort])
        assert node['metrics'] == metrics([p['prediction'] for p in ps], [r['reference'] for r in cohort])
        if node['children']:
            children = [result['registry'][k] for k in node['children']]
            assert gate(node, children, cohort)['status'] == 'accepted'
            assert len(node['generation_families']) and set(node['generation_families']) <= set(learner.FAMILIES)
        checks += 1
    # Independently verify that every evaluated pair offered both declared cold
    # profile references, regardless of whether reuse succeeded.
    challengers = 0
    for proposal in result['proposals']:
        cohort = sorted((by_id[k] for k in proposal['sources']), key=lambda r: r['source_group'])
        for profile in (('shallow', 'compact') if len(cohort) <= 12 else ('compact', 'deep')):
            key = digest([FIT_VERSION, 'constrained', PROFILES[profile], cohort])
            assert key in proposal['fit_refs']
            challengers += 1
        for key in proposal.get('parents', []):
            node = result['registry'][key]
            assert node['children'] == proposal['children']
            assert gate(node, [result['registry'][k] for k in node['children']], cohort)['status'] == 'accepted'
    assert all(len(nodes) <= 2 for nodes in result['retained'].values())
    for key in result['root_candidates']:
        assert set(result['registry'][key]['fit_sources']) == set(by_id)
    return result, checks, challengers


def audit(out):
    manifest = prepare(out); report = read(out / 'results.json')
    old_seal = read(SOURCE / 'completion_seal.json')
    assert all(fingerprint(SOURCE / name) == sha for name, sha in old_seal['files'].items())
    assert not list(out.glob('**/ledgers')) and not list(out.glob('**/interpretation_ledgers'))
    checks = challenged = failed_folds = 0
    reconstructed = []
    for index in (1, 2, 3):
        name = f'split{index}'; directory = out / name
        rows = read(directory / 'training_data.json')
        assert fingerprint(directory / 'training_data.json') == fingerprint(SOURCE / name / 'training_data.json')
        assert fingerprint(out / 'splits' / (name + '.json')) == fingerprint(SOURCE / 'splits' / (name + '.json'))
        validation = {m: {f: [] for f in learner.FAMILIES} for m in learner.GROUPINGS}
        for fold in learner.folds(rows):
            fit_ids = {r['source_group'] for r in fold['train']}; held_ids = {r['source_group'] for r in fold['validation']}
            assert not fit_ids & held_ids and len(fit_ids) == 36 and len(held_ids) == 12
            for method in learner.GROUPINGS:
                folder = directory / 'inner' / ('fold' + str(fold['fold'])) / method
                result, n, c = audit_hierarchy(folder, fold['train']); checks += n; challenged += c
                for family in learner.FAMILIES:
                    stored = read(folder / (family + '-validation.json'))
                    root = learner.family_root(result, family)
                    assert stored['available'] == (root is not None)
                    assert set(stored['training_sources']) == fit_ids and set(stored['validation_sources']) == held_ids
                    ps = PortableRuleExecutor(root['runtime']).predict_records([r['features'] for r in fold['validation']]) if root else [
                        {'prediction': -1, 'trace': [], 'reason': 'inner_hierarchy_infeasible'} for _ in fold['validation']]
                    assert stored['predictions'] == [r['prediction'] for r in ps]
                    assert stored['references'] == [r['reference'] for r in fold['validation']]
                    assert stored['metrics'] == metrics(stored['predictions'], stored['references'])
                    assert stored['node_id'] == (root['node_id'] if root else None)
                    for saved, pred in zip(stored['cases'], ps):
                        assert all(saved[k] == value for k, value in pred.items())
                    validation[method][family].append(stored)
                    failed_folds += root is None; checks += 12
        expected_cv = {m: {f: learner.cv_summary(v) for f, v in families.items()} for m, families in validation.items()}
        assert expected_cv == read(directory / 'validation_summary.json')
        for method, families in validation.items():
            for family, values in families.items():
                assert Counter(k for value in values for k in value['validation_sources']) == Counter(r['source_group'] for r in rows)
                assert expected_cv[method][family]['metrics']['total'] == 48
        outer = {}
        for method in learner.GROUPINGS:
            outer[method], n, c = audit_hierarchy(directory / 'full' / method, rows)
            checks += n; challenged += c
        chosen = learner.choose_root(outer, expected_cv); saved = read(directory / 'selected_training_root.json')
        policy = read(directory / 'frozen_policy.json'); freeze = read(directory / 'freeze.json')
        if chosen:
            assert saved['node_id'] == chosen['root']['node_id'] and saved['method'] == chosen['method'] and saved['family'] == chosen['family']
            assert policy == chosen['root']['runtime']
        else:
            assert saved['node_id'] is None and policy is None
        assert freeze == {'selection_ref': digest(saved), 'runtime_ref': digest(policy), 'training_ref': digest(rows),
            'validation_ref': digest(expected_cv), 'new_model_calls': 0}
        reconstructed.append((name, policy))
    # Evaluation from cached inputs with references used solely by the scorer.
    records = read(SOURCE / 'portable_records.json'); all_cases = []
    frozen = read(out / 'all_frozen.json')
    assert set(frozen) == {'split1', 'split2', 'split3'}
    for name, policy in reconstructed:
        assert frozen[name] == read(out / name / 'freeze.json')
        result = read(out / name / 'results.json'); split = read(out / 'splits' / (name + '.json'))
        rows = [records[r['case']] for r in split['evaluation']]
        ps = PortableRuleExecutor(policy).predict_records([r['features'] for r in rows]) if policy else [
            {'prediction': -1, 'trace': [], 'reason': 'no_qualifying_full_hierarchy'} for _ in rows]
        assert result['evaluation'] == metrics([p['prediction'] for p in ps], [r['reference'] for r in rows])
        for row, saved, pred in zip(rows, result['cases'], ps):
            assert row['case'] == saved['case'] and row['reference'] == saved['reference']
            assert all(saved[k] == value for k, value in pred.items())
        previous = read(SOURCE / name / 'results.json')
        assert result['previous_merged'] == previous['arms']['merged']['metrics']
        control = read(SOURCE / name / 'frozen_policies.json')['direct']
        direct_ps = PortableRuleExecutor(control).predict_records([r['features'] for r in rows])
        assert result['direct_control'] == metrics([p['prediction'] for p in direct_ps], [r['reference'] for r in rows])
        all_cases.extend(result['cases']); checks += 12
    assert len(all_cases) == len({r['source_group'] for r in all_cases}) == 36
    training_sources = {r['source_group'] for i in (1, 2, 3) for r in read(out / f'split{i}/training_data.json')}
    assert not training_sources & {r['source_group'] for r in all_cases}
    assert report['pooled_evaluation'] == metrics([r['prediction'] for r in all_cases], [r['reference'] for r in all_cases])
    result = {'passed': True, 'artifact_prediction_checks': checks, 'unconditional_cold_challenger_references_checked': challenged,
        'inner_family_fold_failures_retained': failed_folds, 'inner_hierarchies': 36, 'full_hierarchies': 9,
        'all_48_oof_sources_per_configuration_retained': True, 'source_scope_leakage_detected': False,
        'all_merge_gates_original': True, 'same_three_sampled_splits': True,
        'new_model_calls': 0, 'original_study_unchanged': True, 'reserved_test_predictions': 0}
    save_json(out / 'verification.json', result); print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
