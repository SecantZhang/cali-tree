"""Independent lineage, local-fit, reuse, and no-router audit of union merging."""
import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import FEATURES
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES
from critical.core.calibration.semantic_hierarchy.union_groups_v10 import semantic, validate_partition
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load
from run.calitree_union_merge import ROOT, M0, M2, PREVIOUS, read, fingerprint, load_data
from run.calitree_union_reuse import RUNS, CONTROL, selection_key


def classify(tree, record):
    if record is None:
        return -1
    used_meaning = []
    def collect(n):
        if 'feature' in n:
            if n['feature'].startswith('meaning_') and n['feature'] != 'meaning_available':
                used_meaning.append(n['feature'])
            collect(n['true']); collect(n['false'])
    collect(tree)
    if used_meaning and not record['features']['meaning_available']:
        return -1
    while 'feature' in tree:
        tree = tree['true' if record['features'][tree['feature']] else 'false']
    return tree['prediction']


def independent_metrics(rows, predictions):
    labels = [r['reference'] for r in rows]
    assert len(rows) == len(predictions) and len({r['source_group'] for r in rows}) == len(rows)
    per_class = {}; fractions = []
    for k, name in enumerate(('no', 'partial', 'yes')):
        n, p = labels.count(k), predictions.count(k)
        correct = sum(a == b == k for a, b in zip(labels, predictions))
        f = Fraction(2 * correct, n + p) if n + p else Fraction(0)
        per_class[name] = {'support': n, 'predicted': p, 'correct': correct,
                           'recall': correct / n if n else None, 'f1': float(f)}
        fractions.append(f)
    correct = sum(a == b for a, b in zip(labels, predictions))
    return {'correct': correct, 'total': len(rows), 'accuracy': correct / len(rows),
            'macro_f1': float(sum(fractions) / 3), 'per_class': per_class, 'unresolved': predictions.count(-1)}


def assert_metrics(saved, rows, ps):
    m = independent_metrics(rows, ps)
    for name in ('correct', 'total', 'unresolved', 'per_class'):
        assert saved[name] == m[name], name
    assert abs(saved['accuracy'] - m['accuracy']) < 1e-12
    assert abs(saved['macro_f1'] - m['macro_f1']) < 1e-12
    return m


def used_predicates(tree):
    if 'feature' not in tree:
        return set()
    return {tree['feature']} | used_predicates(tree['true']) | used_predicates(tree['false'])


def validate_model(node, all_rows):
    sources = node['fit_sources']; by_source = {r['source_group']: r for r in all_rows}
    assert len(sources) == len(set(sources)) and set(sources) <= set(by_source)
    selected = sorted((by_source[s] for s in sources), key=lambda r: r['source_group'])
    policy = node['policy']; PortableSemanticTree.restore(policy)
    assert policy['training']['source_groups'] == [r['source_group'] for r in selected]
    assert policy['training']['feature_ref'] == digest([r['features'] for r in selected])
    assert policy['training']['target_ref'] == digest([r['reference'] for r in selected])
    assert policy['training']['source_batches'] == [r['batch'] for r in selected]
    assert PortableRuleExecutor.from_training_policy(policy).metadata() == node['runtime']
    seen = set(); leaf_support = []
    def visit(tree, part, forbidden):
        if 'feature' in tree:
            name = tree['feature']; assert name in FEATURES
            assert '_count_ge_' not in name and not name.endswith('_majority')
            for value in (True, False):
                visit(tree['true' if value else 'false'],
                      [r for r in part if r['features']['features'][name] == value],
                      forbidden or value and name in CONTRADICTS_YES)
        else:
            assert not (tree['prediction'] == 2 and forbidden)
            actual = {r['source_group'] for r in part}
            assert actual == set(tree['source_groups']) and len(actual) == tree['support'] >= 2
            assert len({r['instruction'] for r in part}) >= 2
            assert [sum(r['reference'] == k for r in part) for k in range(3)] == tree['counts']
            assert tree['prediction'] == max(range(3), key=lambda k: (tree['counts'][k], -k))
            assert dict(Counter(r['batch'] for r in part)) == tree['source_batches']
            assert not seen & actual; seen.update(actual); leaf_support.append(len(actual))
    visit(policy['tree'], [r for r in selected if r['features'] is not None], False)
    missing = {r['source_group'] for r in selected if r['features'] is None}
    assert set(policy['conflicts']['missing_sources']) == missing
    assert seen | missing == set(sources)
    ps = [classify(node['runtime']['tree'], r['features']) for r in selected]
    assert ps == [r['prediction'] for r in PortableRuleExecutor(node['runtime']).predict_records([r['features'] for r in selected])]
    assert_metrics(node['metrics'], selected, ps)
    encoded = json.dumps(node['runtime'])
    assert all(r['source_group'] not in encoded and r['instruction'] not in encoded for r in all_rows)
    return selected, ps


def audit_run(out, name, rows, groups, *, reuse):
    result = read(out / 'runs' / name / 'result.json'); registry = read(out / 'runs' / name / 'registry.json')
    assert registry == result['registry'] and result['m4_used'] is False
    validate_partition(groups, rows)
    by_source = {r['source_group']: r for r in rows}
    checked_nodes, checked_parents, checked_reuse = 0, 0, 0
    for key, node in registry.items():
        assert node['node_id'] == key
        selected, predictions = validate_model(node, rows); checked_nodes += 1
        expected = {s for i, g in enumerate(groups) if node['mask'] & (1 << i) for s in g}
        assert set(node['fit_sources']) == expected
        if not node['children']:
            assert node['mask'].bit_count() == 1 and node['height'] == 0
            continue
        checked_parents += 1
        assert len(node['children']) == 2 and len(set(node['children'])) == 2
        children = [registry[k] for k in node['children']]
        assert not set(children[0]['fit_sources']) & set(children[1]['fit_sources'])
        assert set(node['fit_sources']) == set(children[0]['fit_sources']) | set(children[1]['fit_sources'])
        assert node['height'] == 1 + max(c['height'] for c in children) <= 3
        m = independent_metrics(selected, predictions)
        assert 10 * m['correct'] > 9 * m['total']
        assert all(c['support'] < 2 or c['correct'] > 0 for c in m['per_class'].values())
        for child in children:
            cases = [by_source[s] for s in child['fit_sources']]
            before = sum(classify(child['runtime']['tree'], r['features']) == r['reference'] for r in cases)
            after = sum(classify(node['runtime']['tree'], r['features']) == r['reference'] for r in cases)
            assert after >= before - max(1, len(cases) // 10)
        if reuse:
            checked_reuse += 1
            inherited = set().union(*(used_predicates(c['runtime']['tree']) for c in children))
            used = used_predicates(node['runtime']['tree']); info = node['reuse']
            assert set(info['child_predicates']) == inherited
            assert set(info['used_predicates']) == used
            assert set(info['new_used_predicates']) == used - inherited
            assert info['parent_union_only']
            if info['kind'] == 'child_only':
                assert used <= inherited
            elif info['kind'] == 'bounded_refinement':
                assert len(used - inherited) <= 4
                assert used - inherited <= set(info['searched_new_predicates'])
            else:
                assert info['kind'] == 'full_grammar_repair'
    for p in result['proposals']:
        children = [registry[k] for k in p['children']]
        assert set(p['sources']) == set(children[0]['fit_sources']) | set(children[1]['fit_sources'])
        assert not set(children[0]['fit_sources']) & set(children[1]['fit_sources'])
        for cell, child, other in zip(p['diagnostic']['transfer'], children, children[::-1]):
            cases = [by_source[s] for s in cell['sources']]
            assert set(cell['sources']) == set(other['fit_sources']) and not set(cell['sources']) & set(child['fit_sources'])
            ps = [classify(child['runtime']['tree'], r['features']) for r in cases]
            assert_metrics(cell['metrics'], cases, ps)
        if p['status'] == 'accepted':
            assert p['parent'] in registry and registry[p['parent']]['children'] == p['children']
            assert p['decision']['status'] == 'accepted'
        else:
            assert p['status'] == 'rejected'
            assert all(e['decision']['status'] == 'rejected' and e['decision']['reasons'] for e in p['evaluations'])
    for key in result['root_candidates']:
        assert set(registry[key]['fit_sources']) == set(by_source)
    if result['root']:
        assert result['root'] == registry[result['root']['node_id']]
        assert len(result['selected_merge_order']) == len(groups) - 1
    return {'run': name, 'checked_models': checked_nodes, 'checked_parents': checked_parents,
            'checked_reuse_lineages': checked_reuse, 'checked_pair_proposals': len(result['proposals']),
            'complete_root': bool(result['root']), 'm4_used': False}


def audit(out):
    data = read(out / 'data.json'); assert data == load_data()
    manifest = read(out / 'manifest.json')
    assert digest(read(out / 'protocol.json')) == manifest['protocol_ref']
    assert digest(data) == manifest['data_ref']
    assert digest(read(out / 'groups.json')) == manifest['groups_ref']
    for rel, h in manifest['source_hashes'].items():
        assert fingerprint(ROOT / rel) == h, rel
    groups = read(out / 'groups.json'); rows = data['train']
    assert semantic([{**r, 'reference': (r['reference'] + 1) % 3} for r in reversed(rows)]) == groups['semantic']
    run_audits = [audit_run(out, name, rows, groups[group], reuse=True) for name, group in RUNS.items()]
    from run.calitree_union_merge import RUNS as CONTROL_RUNS
    controls = [audit_run(CONTROL, name, rows, groups[group], reuse=False) for name, (group, _) in CONTROL_RUNS.items()]
    report = read(out / 'results.json'); selection = read(out / 'selected_training_root.json')
    all_results = {name: read(out / 'runs' / name / 'result.json') for name in RUNS}
    options = [(name, r['registry'][k]) for name, r in all_results.items() for k in r['root_candidates']]
    chosen, root = min(options, key=lambda p: (*selection_key(p[0], {'root': p[1]}), p[1]['node_id']))
    assert report['selected_run'] == selection['run'] == chosen
    assert selection['node_id'] == root['node_id'] and read(out / 'deployment_policy.json') == root['runtime']
    assert set(root['fit_sources']) == {r['source_group'] for r in rows}
    assert root['reuse']['kind'] == 'child_only' and not root['reuse']['new_used_predicates']
    expected_order = []
    def collect(node):
        for child in node['children']:
            collect(all_results[chosen]['registry'][child])
        if node['children']:
            expected_order.append(node['node_id'])
    collect(root)
    assert selection['selected_merge_order'] == expected_order
    assert len(expected_order) == len(groups[RUNS[chosen]]) - 1
    train_predictions = [classify(root['runtime']['tree'], r['features']) for r in rows]
    dev_predictions = [classify(root['runtime']['tree'], r['features']) for r in data['validation']]
    assert_metrics(report['training'], rows, train_predictions)
    assert_metrics(report['development'], data['validation'], dev_predictions)
    assert report['selection_used_development'] is False and report['m4_used'] is False
    assert report['new_model_calls'] == report['reserved_test_predictions'] == 0
    package = load(ROOT / 'examples/calitree_union_reuse_v11')
    assert package.artifact['policy'] == root['runtime']
    assert [d['prediction'] for d in package.predict_records([r['features'] for r in rows])] == train_predictions
    assert not (M0 / 'predictions.json').exists() and not list(M0.glob('ledgers/**/jobs/*.json'))
    return {'passed': True, 'reuse_runs': run_audits, 'control_runs': controls,
            'selected_run': chosen, 'selected_root': root['node_id'], 'selected_merges': len(selection['selected_merge_order']),
            'training': independent_metrics(rows, train_predictions), 'development': independent_metrics(data['validation'], dev_predictions),
            'root_only_uses_child_predicates': True, 'semantic_grouping_label_blind': True,
            'all_48_sources_retained': True, 'inference_router_present': False,
            'package_verified': True, 'new_model_calls': 0, 'reserved_test_predictions': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); out = a.output_dir.resolve(); result = audit(out)
    save_json(out / 'audit.json', result)
    print({k: v for k, v in result.items() if k not in ('reuse_runs', 'control_runs')})
