"""Independent source-lineage, metric, and frozen-execution checks for M3--M7."""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import product
import math
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import FEATURES
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import violations
from critical.core.calibration.semantic_hierarchy.hierarchy_runtime_v9 import HierarchyExecutor
from critical.core.calibration.semantic_hierarchy.hierarchy_scopes_v9 import matches
from critical.core.calibration.semantic_hierarchy.hierarchy_protocol_v9 import VERSION
from critical.core.calibration.semantic_hierarchy.hierarchy_protocol_v9 import MERGE_GATES, SEARCH
from critical.core.calibration.semantic_hierarchy.hierarchy_similarity_v9 import seed_bank, propose
from critical.core.calibration.semantic_hierarchy.hierarchy_merge_v9 import replacement
from run.calitree_semantic_hierarchy import ROOT, M0, M2, read, fingerprint, load_data, verify_m2, fold_assignment


def independent_metrics(rows, decisions):
    labels = [r['reference'] for r in rows]
    predictions = [d['prediction'] if isinstance(d, dict) else d for d in decisions]
    assert len(rows) == len(predictions) and len({r['source_group'] for r in rows}) == len(rows)
    classes = {}
    f1s = []
    for k, name in enumerate(('no', 'partial', 'yes')):
        n = sum(y == k for y in labels); chosen = sum(p == k for p in predictions)
        tp = sum(y == p == k for y, p in zip(labels, predictions))
        f1 = Fraction(2 * tp, n + chosen) if n + chosen else Fraction(0)
        classes[name] = {'support': n, 'predicted': chosen, 'correct': tp,
                         'recall': tp / n if n else None, 'f1': float(f1)}
        f1s.append(f1)
    return {'correct': sum(y == p for y, p in zip(labels, predictions)), 'total': len(rows),
            'macro_f1': float(sum(f1s) / 3), 'per_class': classes, 'unresolved': sum(p < 0 for p in predictions)}


def assert_metrics(saved, rows, decisions):
    expected = independent_metrics(rows, decisions)
    for k in ('correct', 'total', 'unresolved'):
        assert saved[k] == expected[k], ('metric', k)
    assert abs(saved['macro_f1'] - expected['macro_f1']) < 1e-12
    assert saved['per_class'] == expected['per_class']
    assert abs(saved['accuracy'] - expected['correct'] / expected['total']) < 1e-12


def validate_training(candidate, rows):
    by_source = {r['source_group']: r for r in rows}
    sources = candidate['fit_sources']
    assert len(set(sources)) == len(sources) and set(sources) <= set(by_source)
    policy = candidate['policy']; PortableSemanticTree.restore(policy)
    ordered = sorted((by_source[s] for s in sources), key=lambda r: r['source_group'])
    assert policy['training']['source_groups'] == [r['source_group'] for r in ordered]
    assert policy['training']['feature_ref'] == digest([r['features'] for r in ordered])
    assert policy['training']['target_ref'] == digest([r['reference'] for r in ordered])
    assert policy['training']['source_batches'] == [r['batch'] for r in ordered]
    assert PortableRuleExecutor.from_training_policy(policy).metadata() == candidate['runtime']
    assert not violations(policy['tree'])
    observed = set()
    def walk(node, selected):
        if 'feature' in node:
            assert node['feature'] in FEATURES
            for value in (True, False):
                walk(node['true' if value else 'false'],
                     [r for r in selected if r['features']['features'][node['feature']] == value])
        else:
            actual = {r['source_group'] for r in selected}
            assert actual == set(node['source_groups']) and len(actual) == node['support'] >= 2
            assert len({r['instruction'] for r in selected}) >= 2
            assert [sum(r['reference'] == k for r in selected) for k in range(3)] == node['counts']
            assert dict(sorted(Counter(r['batch'] for r in selected).items())) == node['source_batches']
            assert not observed & actual
            observed.update(actual)
    walk(policy['tree'], [r for r in ordered if r['features'] is not None])
    assert observed | set(policy['conflicts']['missing_sources']) == set(sources)
    predictions = PortableRuleExecutor(candidate['runtime']).predict_records([r['features'] for r in ordered])
    assert_metrics(candidate['metrics'], ordered, predictions)


def audit_baseline(out):
    verify_m2()
    manifest = read(out / 'manifest.json'); data = read(out / 'data.json')
    assert manifest['version'] == VERSION and digest(read(out / 'protocol.json')) == manifest['protocol_ref']
    assert digest(data) == manifest['data_ref'] == digest(load_data())
    for rel, expected in manifest['source_hashes'].items():
        assert fingerprint(ROOT / rel) == expected, rel
    folds = read(out / 'folds.json'); assert folds == fold_assignment(data['train'])
    cached = [read(p) for p in (out / 'fits').glob('*.json')]
    results = read(out / 'baseline/results.json')
    audits, by_source = [], {}
    for name in ('fold0', 'fold1', 'fold2', 'fold3', 'full'):
        context = read(out / 'baseline' / (name + '_context.json'))
        if name == 'full':
            fitting, validation = data['train'], data['validation']
            assert context['pooled'] == read(M2 / 'deployment_policy.json')
        else:
            f = int(name[-1]); fitting = [r for r in data['train'] if folds[r['source_group']] != f]
            validation = [r for r in data['train'] if folds[r['source_group']] == f]
        fitting_sources = {r['source_group'] for r in fitting}
        assert set(context['fit_sources']) == fitting_sources
        assert not fitting_sources & {r['source_group'] for r in validation}
        for candidate in context['local_registry']:
            validate_training(candidate, fitting)
        for inner in context['inner_pooled_oof']:
            assert set(inner['fit_sources']) <= fitting_sources
            assert set(inner['validation_sources']) <= fitting_sources
            assert not set(inner['fit_sources']) & set(inner['validation_sources'])
            matching = [x for x in cached if x['result']['runtime']['artifact_ref'] == inner['policy_ref']
                        and set(x['fit_sources']) == set(inner['fit_sources'])]
            assert matching
            selected = [next(r for r in fitting if r['source_group'] == s) for s in inner['validation_sources']]
            runtime = PortableRuleExecutor(matching[0]['result']['runtime'])
            assert runtime.predict_records([r['features'] for r in selected]) == inner['predictions']
        for route in context['selected_routes']:
            candidate = context['candidates'][route['node_id']]
            assert candidate['specialist_eligible']
            assert not set(candidate['fit_sources']) & set(route['validation_sources'])
            assert set(route['validation_sources']) <= fitting_sources
            assert min(c['correct'] for c in route['expert_metrics']['per_class'].values()) > 0
        executor = HierarchyExecutor(context['bundle'])
        decisions = executor.predict_records([r['features'] for r in validation], [r['scope'] for r in validation])
        pooled = PortableRuleExecutor(context['pooled']).predict_records([r['features'] for r in validation])
        saved = read(out / 'baseline' / (name + '_result.json')) if name != 'full' else results['development']
        assert_metrics(saved['routed_metrics'], validation, decisions)
        assert_metrics(saved['pooled_metrics'], validation, pooled)
        assert [d['prediction'] for d in decisions] == [d['prediction'] for d in saved['cases']]
        assert HierarchyExecutor(executor.export()).predict_records([r['features'] for r in validation], [r['scope'] for r in validation]) == decisions
        fit_ds = executor.predict_records([r['features'] for r in fitting], [r['scope'] for r in fitting])
        fit_ps = PortableRuleExecutor(context['pooled']).predict_records([r['features'] for r in fitting])
        a, b = independent_metrics(fitting, fit_ds), independent_metrics(fitting, fit_ps)
        assert a['correct'] >= b['correct'] and a['macro_f1'] >= b['macro_f1'] - 1e-12
        assert all(a['per_class'][k]['correct'] >= b['per_class'][k]['correct'] for k in a['per_class'])
        if name != 'full':
            by_source.update({r['source_group']: d for r, d in zip(validation, decisions)})
        audits.append({'context': name, 'fit_sources': len(fitting), 'validation_sources': len(validation),
                       'active_routes': len(context['bundle']['routes']), 'out_of_source': True})
    assert_metrics(results['routed_oof'], data['train'], [by_source[r['source_group']] for r in data['train']])
    assert results['training']['pooled_metrics']['correct'] == 44
    assert results['training']['routed_metrics']['correct'] >= 44
    local_oof = out / 'baseline/local_candidate_oof.json'
    if local_oof.exists():
        for entry in read(local_oof):
            cases = []
            for row in entry['cases']:
                source = next(r for r in data['train'] if r['source_group'] == row['source_group'])
                fold = folds[source['source_group']]
                candidate = next(c for c in read(out / 'baseline' / f'fold{fold}_context.json')['local_registry']
                                 if c['node_id'] == entry['node_id'])
                assert source['source_group'] not in candidate['fit_sources']
                decision = PortableRuleExecutor(candidate['runtime']).predict_records([source['features']])[0]
                assert decision['prediction'] == row['prediction']
                cases.append(source)
            assert_metrics(entry['metrics'], cases, entry['cases'])
    assert not (M0 / 'predictions.json').exists() and not list(M0.glob('ledgers/**/jobs/*.json'))
    return {'version': VERSION, 'M3': 'pass', 'M4': 'pass', 'contexts': audits,
            'shared_representation_ref': manifest['data_ref'], 'reference_label_isolation': True,
            'routing_effectiveness': 'Reported separately; a failed isolated-scope router was retained as v9.1.',
            'new_model_calls': 0, 'final_test_predictions': 0}


def route_alternatives(out):
    """Exhaustive diagnostic within the fixed qualified-scope priority order.

    This does not change the selected system or tune a final evaluation. It
    checks whether keeping only one scope per expert concealed a stable route.
    """
    from critical.core.calibration.semantic_hierarchy.hierarchy_protocol_v9 import macro_fraction
    context = read(out / 'baseline/full_context.json'); rows = read(out / 'data.json')['train']
    proposals = []
    for entry in context['scope_diagnostics']:
        for r in entry.get('supported_scopes', []):
            m, b, e = r['routed_metrics'], r['pooled_oof_metrics'], r['expert_metrics']
            if (any(not c['correct'] for c in e['per_class'].values()) or macro_fraction(m) <= macro_fraction(b)
                    or any(m['per_class'][k]['correct'] < b['per_class'][k]['correct'] for k in b['per_class'])
                    or m['unresolved'] > b['unresolved']):
                continue
            proposals.append(r)
    proposals.sort(key=lambda r: (-len(r['scope'][0]), -(macro_fraction(r['routed_metrics']) - macro_fraction(r['pooled_oof_metrics'])),
                                 -len(r['validation_sources']), digest([r['scope'], r['node_id']])))
    groups = {k: [None] + [i for i, r in enumerate(proposals) if r['node_id'] == k]
              for k in sorted({r['node_id'] for r in proposals})}
    total = math.prod(len(v) for v in groups.values())
    if total > 100000:
        return {'status': 'diagnostic_budget_exceeded', 'combinations': total, 'changed_selection': False}
    records = [r['features'] for r in rows]
    pool = PortableRuleExecutor(context['pooled']).predict_records(records)
    values = {k: PortableRuleExecutor(context['candidates'][k]['runtime']).predict_records(records) for k in groups}
    covered = [[j for j, r in enumerate(rows) if matches(r['scope'], q['scope'])] for q in proposals]
    base = independent_metrics(rows, pool); stable = []
    for choices in product(*groups.values()):
        selected = sorted(i for i in choices if i is not None)
        predictions = [r['prediction'] for r in pool]
        for i in reversed(selected):
            for j in covered[i]:
                p = values[proposals[i]['node_id']][j]['prediction']
                predictions[j] = p if p >= 0 else pool[j]['prediction']
        m = independent_metrics(rows, predictions)
        if (m['correct'] >= base['correct'] and m['macro_f1'] >= base['macro_f1'] - 1e-12
                and all(m['per_class'][k]['correct'] >= base['per_class'][k]['correct'] for k in base['per_class'])
                and m['unresolved'] <= base['unresolved']):
            stable.append({'routes': selected, 'metrics': m})
    return {'status': 'complete', 'qualified_scope_alternatives': len(proposals),
            'combinations_evaluated': total, 'stable_combinations': stable,
            'changed_selection': False,
            'scope': 'At most one of every individually qualified scope per expert, fixed validation-priority order. Not all possible rule grammars or arbitrary route permutations.'}


def audit_hierarchy(out):
    baseline = audit_baseline(out)
    data = read(out / 'data.json'); rows = data['train']; folds = read(out / 'folds.json')
    full_context = read(out / 'baseline/full_context.json')
    bank = seed_bank(full_context, rows)
    fold_contexts = {f: read(out / 'baseline' / f'fold{f}_context.json') for f in range(4)}
    fitting = {f: [r for r in rows if folds[r['source_group']] != f] for f in range(4)}
    fold_banks = {f: seed_bank(c, fitting[f], include_duplicates=True) for f, c in fold_contexts.items()}
    current = full_context['bundle']; fold_current = {f: c['bundle'] for f, c in fold_contexts.items()}
    proposed, ineligible = propose(set(bank), bank, rows, set())
    initial = read(out / 'proposals/initial.json')
    assert proposed == initial['candidates'] and ineligible == initial['rejected_pairs']
    transfer_cells = 0
    for proposal in initial['candidates']:
        for cell in proposal['compatibility']['mutual_transfer']:
            selected = [next(r for r in rows if r['source_group'] == s) for s in cell['sources']]
            assert not set(cell['sources']) & set(bank[cell['from']]['fit_sources'])
            if selected:
                decisions = PortableRuleExecutor(bank[cell['from']]['runtime']).predict_records([r['features'] for r in selected])
                assert_metrics(cell['metrics'], selected, decisions)
                transfer_cells += 1
    history = read(out / 'hierarchy/history.json')['steps']; audited = []
    assert len(history) <= SEARCH['max_parent_proposals']
    original_gates = read(M0 / 'study_protocol.json')['merge_gates']
    assert all(original_gates[k] == v for k, v in MERGE_GATES.items())

    def evaluate(bundle, selected):
        return HierarchyExecutor(bundle).predict_records([r['features'] for r in selected], [r['scope'] for r in selected])
    def oof(bundles):
        values = {}
        for f in range(4):
            selected = [r for r in rows if folds[r['source_group']] == f]
            values.update({r['source_group']: d for r, d in zip(selected, evaluate(bundles[f], selected))})
        return [values[r['source_group']] for r in rows]
    for step in history:
        assert step['state_before_ref'] == current['bundle_ref']
        parent = step['parent']; children = parent['children']
        expected_sources = set().union(*(set(bank[c]['fit_sources']) for c in children))
        assert set(parent['fit_sources']) == expected_sources == set(step['union_manifest']['full_deduplicated_union'])
        assert set(step['union_manifest']['missing_evidence_sources_retained']) == {
            r['source_group'] for r in rows if r['source_group'] in expected_sources and r['features'] is None}
        validate_training(parent, rows)
        def cross_batch(node):
            if 'feature' in node:
                cross_batch(node['true']); cross_batch(node['false'])
            else:
                assert len(node['source_batches']) >= 2
        cross_batch(parent['policy']['tree'])
        assert parent['depth'] <= 3 and parent['depth'] == 1 + max(bank[c]['depth'] for c in children)
        actual_after = replacement(current, parent, bank)
        assert actual_after == step['full_candidate_bundle']
        fold_after = {}
        for f in range(4):
            saved = step['fold_parents'].get(str(f))
            if saved is None:
                assert any(x['fold'] == f for x in step['missing_folds'])
                fold_after[f] = fold_current[f]
                continue
            validate_training(saved, fitting[f]); cross_batch(saved['policy']['tree'])
            expected = set().union(*(set(fold_banks[f][c]['fit_sources']) for c in children))
            held = {r['source_group'] for r in rows if folds[r['source_group']] == f}
            assert set(saved['fit_sources']) == expected and not expected & held
            fold_after[f] = replacement(fold_current[f], saved, fold_banks[f])
            assert fold_after[f] == step['fold_candidate_bundles'][str(f)]
        before_ps, after_ps = oof(fold_current), oof(fold_after)
        assert before_ps == step['before_oof'] and after_ps == step['after_oof']
        assert_metrics(step['decision']['before'], rows, before_ps)
        assert_metrics(step['decision']['after'], rows, after_ps)
        training_ps = evaluate(actual_after, rows)
        assert_metrics(step['training_metrics'], rows, training_ps)
        m, bm = independent_metrics(rows, after_ps), independent_metrics(rows, before_ps)
        status = step['decision']['status']
        if status == 'accepted':
            assert not step['missing_folds']
            assert independent_metrics(rows, training_ps)['correct'] > .9 * len(rows)
            assert m['correct'] >= bm['correct'] - 1 and m['macro_f1'] >= bm['macro_f1'] - 1e-12
            assert m['per_class']['partial']['correct'] >= bm['per_class']['partial']['correct']
            assert m['unresolved'] <= bm['unresolved']
            for name in ('no', 'yes'):
                assert m['per_class'][name]['correct'] >= bm['per_class'][name]['correct'] - 1
            for protected in step['decision']['protected_scopes'].values():
                assert protected['before']['total'] >= 8
                assert protected['after']['correct'] >= protected['before']['correct'] - 1
            assert step['decision']['measured_improvement'] or step['decision']['lossless_compression']
            current = actual_after; bank[parent['node_id']] = parent; fold_current = fold_after
            for f in range(4):
                fold_banks[f][parent['node_id']] = step['fold_parents'][str(f)]
        elif status == 'rejected':
            assert step['decision']['reasons']
            # Independently verify an empirical, local-fit, or support failure.
            assert (m['macro_f1'] < bm['macro_f1'] - 1e-12
                    or m['correct'] < bm['correct'] - 1
                    or m['per_class']['partial']['correct'] < bm['per_class']['partial']['correct']
                    or m['unresolved'] > bm['unresolved']
                    or independent_metrics(rows, training_ps)['correct'] <= .9 * len(rows)
                    or not parent['specialist_eligible']
                    or 'no_improvement_or_lossless_compression' in step['decision']['reasons']
                    or any(k.endswith('_regression') or k.startswith('protected_scope_regression') for k in step['decision']['reasons']))
        else:
            assert status == 'insufficient' and step['decision']['insufficient_evidence']
        audited.append({'proposal': step['index'], 'union_sources': len(expected_sources),
                        'folds_independently_verified': len(step['fold_parents']), 'status': status})
    final = read(out / 'hierarchy/frozen_bundle.json'); assert final == current
    summary = read(out / 'hierarchy/results.json')
    assert summary['bundle_ref'] == final['bundle_ref']
    assert summary['final_oof'] == oof(fold_current)
    assert_metrics(summary['final_oof_metrics'], rows, oof(fold_current))
    train_ps = evaluate(final, rows); dev_ps = evaluate(final, data['validation'])
    assert_metrics(summary['training_metrics'], rows, train_ps)
    assert_metrics(summary['development_metrics'], data['validation'], dev_ps)
    assert summary['training_metrics']['correct'] >= 44
    encoded = __import__('json').dumps(final, sort_keys=True)
    assert all(r['source_group'] not in encoded and r['instruction'] not in encoded for r in rows + data['validation'])
    assert HierarchyExecutor(deepcopy(final)).export() == final
    frontier = set(summary['frontier']); registry = read(out / 'hierarchy/node_registry.json')
    assert registry == bank
    if summary['stop_reason'] == 'no_eligible_unevaluated_pair':
        tried = {s['proposal']['pair_ref'] for s in history if s['state_before_ref'] == final['bundle_ref']}
        remaining, _ = propose(frontier, bank, rows, tried)
        assert not remaining
    else:
        assert summary['stop_reason'] == 'parent_proposal_budget_exhausted' and len(history) == 24
    return {'version': VERSION, 'M3_M4_prerequisite': baseline, 'M5': 'pass', 'M6': 'pass', 'M7': 'pass',
            'independent_source_excluding_transfer_cells': transfer_cells,
            'candidates_independently_audited': audited, 'bundle_ref': final['bundle_ref'],
            'training': independent_metrics(rows, train_ps), 'oof': independent_metrics(rows, oof(fold_current)),
            'development': independent_metrics(data['validation'], dev_ps), 'stop_verified': summary['stop_reason'],
            'runtime_contains_no_training_inputs': True, 'restore_trace_parity': True,
            'new_model_calls': 0, 'reserved_test_predictions': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--stage', choices=['baseline', 'hierarchy', 'routes'], default='hierarchy')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.stage == 'baseline':
        result, path = audit_baseline(out), out / 'baseline/audit.json'
    elif a.stage == 'routes':
        result, path = route_alternatives(out), out / 'baseline/route_alternative_audit.json'
    else:
        result, path = audit_hierarchy(out), out / 'hierarchy/audit.json'
    save_json(path, result)
    print({k: v for k, v in result.items() if k not in ('candidates_independently_audited', 'M3_M4_prerequisite', 'stable_combinations')})


if __name__ == '__main__':
    main()

