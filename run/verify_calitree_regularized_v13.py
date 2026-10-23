"""Replay v13 source scopes, predicates, compression gates and nested scores.

No fits or model calls. Audits saved caches directly instead of using the runner
to regenerate missing artifacts. Missing artifacts are failures.
"""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy import regularized_tree_v13 as learner
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from run.calitree_regularized_v13 import read, fingerprint, ROOT, PROFILES, MODES, outer_folds, inner_folds, summarize


def audit(out):
    manifest = read(out / 'manifest.json')
    assert manifest['artifact_ref'] == digest({k: v for k, v in manifest.items() if k != 'artifact_ref'})
    assert manifest['protocol_ref'] == digest(read(out / 'protocol.json'))
    for group in ('source_hashes', 'code_hashes'):
        for rel, expected in manifest[group].items():
            assert fingerprint(ROOT / rel) == expected, rel
    datasets = [read(out / f'split{i}/training_data.json') for i in (1, 2, 3)]
    for i, rows in enumerate(datasets, 1):
        rel = f'logs/exps/261018-union-challenger-validation-v12/split{i}/training_data.json'
        assert fingerprint(out / f'split{i}/training_data.json') == manifest['source_hashes'][rel]
    runs = {}; nodes_checked = aliases_checked = merges_checked = 0
    work = {'fits': 0, 'cache_hits': 0, 'partition_scores': 0, 'predicate_tests': 0}
    for path in sorted((out / 'procedure_cache').glob('*.json.gz')):
        value = json.loads(gzip.decompress(path.read_bytes()))
        assert value['content_ref'] == digest({k: v for k, v in value.items() if k != 'content_ref'})
        sources = set(value['source_groups']); rows = None
        for full in datasets:
            subset = sorted((r for r in full if r['source_group'] in sources), key=lambda r: r['source_group'])
            if digest(subset) == value['rows_ref']:
                rows = subset; break
        assert rows is not None, 'Unbound procedure training rows'
        assert value['fit_ref'] == digest([manifest['artifact_ref'], rows, value['profile'], value['mode']])
        assert path.name == value['fit_ref'] + '.json.gz'
        config = PROFILES[value['profile']]; result = value['result']
        assert result['complete'] == (result['root'] is not None)
        assert result['work']['fits'] <= 128 and len(result['proposals']) <= 18
        for k in work:
            work[k] += result['work'][k]
        registry = {n['node_id']: n for n in result['nodes']}
        candidates = list(registry.values()) if registry else [result['root']]
        by_id = {r['source_group']: r for r in rows}
        for model in candidates:
            cohort = [by_id[s] for s in model['fit_sources']]
            policy = model['policy']; PortableSemanticTree.restore(policy)
            assert PortableRuleExecutor.from_training_policy(policy).metadata() == model['runtime']
            assert policy['training']['feature_ref'] == digest([r['features'] for r in cohort])
            assert policy['training']['target_ref'] == digest([r['reference'] for r in cohort])
            predictions = learner.predict(model, cohort)
            assert model['metrics'] == learner.metrics([p['prediction'] for p in predictions], [r['reference'] for r in cohort])
            assert policy['training']['metrics'] == model['metrics']
            assert model['complexity'] == learner.complexity(model['runtime']['tree'])
            if model.get('children'):
                children = [registry[k] for k in model['children']]
                assert not set(children[0]['fit_sources']) & set(children[1]['fit_sources'])
                assert set(model['fit_sources']) == set().union(*(set(c['fit_sources']) for c in children))
                decision = learner.compression_gate(model, children, cohort, config)
                assert model['acceptance'] == decision and decision['status'] == 'accepted'
                merges_checked += 1
            groups = {tuple(g['path']): g for g in policy['search']['alternatives']}
            for route, group in groups.items():
                selected = [r for r in cohort if r['features'] is not None]
                for depth, side in enumerate(route):
                    feature = groups[route[:depth]]['selected']
                    selected = [r for r in selected if r['features']['features'][feature] == (side == 'true')]
                for alternative in group['training_equivalent_alternatives']:
                    assert group['semantic_equivalence_claim'] is False
                    assert all((r['features']['features'][group['selected']] != r['features']['features'][alternative['feature']])
                               == alternative['complement'] for r in selected)
                    aliases_checked += 1
            nodes_checked += 1
        if result['root'] is not None:
            assert set(result['root']['fit_sources']) == sources
        runs[value['fit_ref']] = value

    def verify_score(saved, train, held, profile, mode):
        key = digest([manifest['artifact_ref'], sorted(train, key=lambda r: r['source_group']), profile, mode])
        assert saved['fit_ref'] == key
        value = runs[key]
        assert set(value['source_groups']) == {r['source_group'] for r in train}
        assert not set(value['source_groups']) & {r['source_group'] for r in held}
        assert saved['training_sources'] == value['source_groups']
        assert saved['validation_sources'] == [r['source_group'] for r in held]
        root = value['result']['root']
        ps = learner.predict(root, held) if root else [{'prediction': -1, 'reason': 'no_qualifying_root', 'trace': []} for _ in held]
        assert saved['available'] == (root is not None)
        assert saved['rules'] == (root['complexity']['rules'] if root else None)
        expected = [{'source_group': r['source_group'], 'reference': r['reference'], **p} for r, p in zip(held, ps)]
        assert saved['cases'] == expected
        assert saved['metrics'] == learner.metrics([p['prediction'] for p in ps], [r['reference'] for r in held])

    def verify_selection(saved, plan, mode):
        assert set(saved['candidates']) == set(PROFILES)
        for profile, v in saved['candidates'].items():
            assert len(v['scores']) == len(plan)
            for score, fold in zip(v['scores'], plan):
                verify_score(score, fold['train'], fold['validation'], profile, mode)
            assert v['summary'] == summarize(v['scores'])
        def key(profile):
            s = saved['candidates'][profile]['summary']; m = s['metrics']
            return (-m['macro_f1'], -m['worst_present_class_recall'], s['macro_f1_std'],
                    s['mean_rules'] if s['mean_rules'] is not None else float('inf'), profile)
        assert saved['selected'] == min(PROFILES, key=key)
        return saved['selected']

    pooled = {mode: [] for mode in MODES}; score_checks = 0
    for i, rows in enumerate(datasets, 1):
        folder = out / f'split{i}'; plan = outer_folds(rows); scores = {mode: [] for mode in MODES}
        for fold in plan:
            for mode in MODES:
                d = folder / f'outer/{fold["fold"]}/{mode}'
                chosen = verify_selection(read(d / 'selection.json'), inner_folds(fold['train']), mode)
                saved = read(d / 'score.json')
                verify_score(saved, fold['train'], fold['validation'], chosen, mode)
                scores[mode].append(saved); score_checks += len(saved['cases'])
        report = read(folder / 'results.json')
        for mode in MODES:
            assert report['nested'][mode] == summarize(scores[mode])
            pooled[mode].extend(scores[mode])
            selection = read(folder / mode / 'selection.json')
            chosen = verify_selection(selection, plan, mode)
            freeze = read(folder / mode / 'freeze.json')
            key = digest([manifest['artifact_ref'], sorted(rows, key=lambda r: r['source_group']), chosen, mode])
            assert freeze['profile'] == chosen and freeze['fit_ref'] == key
            root = runs[key]['result']['root']; runtime = root['runtime'] if root else None
            assert read(folder / mode / 'policy.json') == runtime
            assert freeze['training_ref'] == digest(rows) and freeze['runtime_ref'] == digest(runtime)
            assert freeze['selection_ref'] == digest(selection['candidates'])
            assert freeze == report['selected'][mode]
    result = read(out / 'results.json')
    assert result['pooled_nested'] == {m: summarize(v) for m, v in pooled.items()}
    assert result['procedure_fits'] == len(runs) <= 1000
    assert result['new_model_calls'] == result['historical_evaluation_predictions'] == result['reserved_test_predictions'] == 0
    output = {'passed': True, 'procedure_runs': len(runs), 'node_checks': nodes_checked,
        'semantic_alternatives_verified': aliases_checked, 'compressed_accepted_merges': merges_checked,
        'nested_score_checks': score_checks, 'new_fits': 0, 'new_model_calls': 0,
        'reserved_test_predictions': 0, 'work_over_all_selection_and_refit_runs': work}
    save_json(out / 'verification.json', output); print(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
