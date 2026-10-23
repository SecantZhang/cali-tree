"""Replay local retention, rule compression, original targets and forest coverage."""
import argparse
from pathlib import Path

from critical.core.calibration import local_compression_v18 as local
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.decision.artifacts import digest, save_json
from run.calitree_local_compression_v18 import ROOT, SOURCE, read, fingerprint


def verify(out):
    manifest = read(out / 'manifest.json')
    assert manifest['protocol_ref'] == digest(read(out / 'protocol.json'))
    for group in ('source_hashes', 'code_hashes'):
        for rel, expected in manifest[group].items():
            assert fingerprint(ROOT / rel) == expected, rel
    node_count = merge_count = prediction_count = 0
    for i in (1, 2, 3):
        rows = read(out / f'split{i}/training_data.json'); seeds = read(out / f'split{i}/seeds.json')
        assert rows == read(SOURCE / f'split{i}/training_data.json')
        original = read(SOURCE / f'split{i}/full/original4/seeds.json')
        assert seeds == [min((original['nodes'][k] for k in g['policies']), key=local.rank) for g in original['groups']]
        result = read(out / f'split{i}/result.json'); registry = result['registry']
        by_source = {r['source_group']: r for r in rows}
        original_floors = [local.requirement(s, rows) for s in seeds]
        assert result['original_requirements'] == original_floors
        for node in registry.values():
            cohort = sorted((by_source[s] for s in node['fit_sources']), key=lambda r: r['source_group'])
            PortableSemanticTree.restore(node['policy'])
            actual = local.describe(node['policy'], cohort, node['initialization'])
            for key in ('metrics', 'complexity', 'runtime', 'portable'):
                assert actual[key] == node[key], key
            reqs = [q for q in original_floors if set(q['sources']) <= set(node['fit_sources'])]
            checked = local.gate(node, cohort, reqs, max_rules=node['complexity']['rules'])
            assert checked['status'] == 'accepted', checked
            node_count += 1; prediction_count += len(cohort)
        for event in result['events']:
            if event['status'] != 'accepted':
                continue
            parent = registry[event['parent']]; children = [registry[k] for k in event['children']]
            child_sets = [set(c['fit_sources']) for c in children]
            assert not child_sets[0] & child_sets[1]
            assert set(parent['fit_sources']) == set.union(*child_sets)
            cohort = [r for r in rows if r['source_group'] in set(parent['fit_sources'])]
            requirements = [q for q in result['optimized_requirements'] if set(q['sources']) <= set(parent['fit_sources'])]
            requirements += [local.requirement(c, cohort) for c in children]
            assert local.scopes(cohort, requirements) == event['requirements']
            limit = sum(c['complexity']['rules'] for c in children) - 1
            decision = local.gate(parent, cohort, requirements, max_rules=limit)
            assert decision == event['decision'] and decision['status'] == 'accepted'
            merge_count += 1
        forest = [registry[k] for k in result['forest']]
        assert sum(len(n['fit_sources']) for n in forest) == len(rows)
        assert set().union(*(set(n['fit_sources']) for n in forest)) == set(by_source)
        assert result['summary']['forest_local_correct'] == sum(n['metrics']['correct'] for n in forest)
        assert result['summary']['forest_rules'] == sum(n['complexity']['rules'] for n in forest)
        assert result['summary']['original_rules'] == sum(n['complexity']['rules'] for n in seeds)
        optimized = [next(n for n in registry.values() if not n['children'] and n['mask'] == (1 << j)) for j in range(4)]
        assert result['optimized_requirements'] == [local.requirement(n, rows) for n in optimized]
        for search in result['searches']:
            assert search['states'] <= search['config']['max_states']
            assert search['transitions'] <= search['config']['max_transitions']
            assert not search['global_optimality_claim']
        portable = read(out / f'split{i}/portable_forest.json')
        assert portable['trees'] == [n['runtime'] for n in forest]
        assert portable['complete_root'] == (result['root'] is not None)
        assert portable['root'] == (result['root']['runtime'] if result['root'] else None)
        for runtime in portable['trees']:
            local.PortableRuleExecutor(runtime)
        assert result['new_model_calls'] == result['reserved_test_predictions'] == 0
    audit = {'passed': True, 'nodes_checked': node_count, 'accepted_merges_checked': merge_count,
             'training_predictions_replayed': prediction_count, 'original_targets_preserved': True,
             'each_local_scope_preserved': True, 'portable_feature_only_rules': True,
             'new_model_calls': 0, 'final_set_predictions': 0}
    path = out / 'verification.json'
    if path.exists():
        assert read(path) == audit
    else:
        save_json(path, audit)
    seal = {str(p.relative_to(out)): fingerprint(p) for p in out.rglob('*') if p.is_file() and p.name != 'seal.json'}
    if (out / 'seal.json').exists():
        assert read(out / 'seal.json') == seal
    else:
        save_json(out / 'seal.json', seal)
    print(audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    verify(parser.parse_args().output_dir.resolve())
