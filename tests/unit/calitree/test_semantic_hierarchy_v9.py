from copy import deepcopy

import pytest

from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.calibration.semantic_hierarchy.hierarchy_fit_v9 import fit
from critical.core.calibration.semantic_hierarchy.hierarchy_runtime_v9 import HierarchyExecutor, export_bundle
from critical.core.calibration.semantic_hierarchy.hierarchy_scopes_v9 import FLAGS, matches, union, validate_values
from critical.core.calibration.semantic_hierarchy.hierarchy_protocol_v9 import sealed, score
from critical.core.calibration.semantic_hierarchy.hierarchy_merge_v9 import decide, parent_node, active_complexity
from critical.core.calibration.semantic_hierarchy.hierarchy_training_v9 import Fits
from critical.core.calibration.semantic_hierarchy.hierarchy_builder_v9 import build
from critical.core.calibration.semantic_hierarchy.hierarchy_similarity_v9 import compatibility
from critical.core.calibration.semantic_hierarchy.hierarchy_export_v9 import export as export_package, load as load_package


def rows(n=24, batch='a'):
    return [{'case': f'{batch}-{i}', 'source_group': f'{batch}-source-{i}', 'batch': batch,
             'reference': i % 3, 'instruction': f'Instruction fixture {batch} {i}',
             'features': synthetic_record(meaning_available=True,
                 meaning_progress_requested_endpoint_all=i % 3 == 2,
                 meaning_progress_toward_requested_goal_all=i % 3 == 1),
             'scope': {k: k == 'requires_spatial_relation' for k in FLAGS}} for i in range(n)]


def bundle():
    fitted = fit(rows(), 'local_shallow')
    return export_bundle(fitted['runtime'], {'leaf': {'policy': fitted['runtime'], 'children': [], 'depth': 0}},
                         [{'node_id': 'leaf', 'scope': [[{'flag': 'requires_spatial_relation', 'value': True}]]}], {})


def test_source_supported_portable_candidates_and_warm_start_full_union():
    a, b = rows(12, 'a'), rows(12, 'b')
    child = fit(a, 'local_shallow')
    parent = fit(a + b, 'pooled', [child['runtime']])
    assert parent['metrics']['correct'] == 24
    assert parent['specialist_eligible']
    assert len(parent['warm_start_candidates']) == 2
    assert set(parent['policy']['training']['source_groups']) == {r['source_group'] for r in a + b}
    assert all(s['sources'] >= 2 and s['distinct_instructions'] >= 2 for s in parent['leaf_support'])


def test_routing_accepts_no_reference_batch_or_case_fields():
    for key in ('reference', 'batch', 'case', 'source_group', 'meaning_progress_requested_endpoint_all'):
        scope = deepcopy(rows(3)[0]['scope']); scope[key] = True
        with pytest.raises(ValueError):
            validate_values(scope)
    b = bundle(); b['routes'][0]['scope'][0][0]['flag'] = 'reference'
    b['bundle_ref'] = digest({k: v for k, v in b.items() if k != 'bundle_ref'})
    with pytest.raises(ValueError):
        HierarchyExecutor(b)

    b = bundle()
    node = deepcopy(b['nodes']['leaf']); scope = deepcopy(b['routes'][0]['scope'])
    b['nodes'] = {str(i): deepcopy(node) for i in range(9)}
    b['routes'] = [{'node_id': str(i), 'scope': deepcopy(scope)} for i in range(9)]
    b['bundle_ref'] = digest({k: v for k, v in b.items() if k != 'bundle_ref'})
    with pytest.raises(ValueError):
        HierarchyExecutor(b)


def test_actual_routing_and_export_restore_trace_parity():
    executor = HierarchyExecutor(bundle()); data = rows(12)
    records, scopes = [r['features'] for r in data], [r['scope'] for r in data]
    first = executor.predict_records(records, scopes)
    assert [d['prediction'] for d in first] == [r['reference'] for r in data]
    assert all(d['served_node'] == 'leaf' and d['policy_evaluations'] == 1 for d in first)
    assert HierarchyExecutor(executor.export()).predict_records(records, scopes) == first
    # Replacing labels and IDs cannot enter this inference signature.
    for r in data:
        r.update(reference=2, case='renamed', source_group='renamed', batch='renamed')
    assert executor.predict_records([r['features'] for r in data], [r['scope'] for r in data]) == first


def test_unknown_scope_and_missing_evidence_use_declared_fallback():
    executor = HierarchyExecutor(bundle()); data = rows(3)
    scope = {k: False for k in FLAGS}
    d = executor.predict_records([data[0]['features']], [scope])[0]
    assert d['served_node'] == 'pooled' and d['prediction'] == 0
    missing = executor.predict_records([None], [data[0]['scope']])[0]
    assert missing['prediction'] == -1 and missing['policy_evaluations'] == 2
    assert score(data, [-1, 1, 2])['total'] == 3


def test_hierarchy_rejects_cycles_and_wrong_depth_even_when_rehashed():
    b = bundle(); b['nodes']['leaf']['children'] = ['leaf']
    b['bundle_ref'] = digest({k: v for k, v in b.items() if k != 'bundle_ref'})
    with pytest.raises(ValueError):
        HierarchyExecutor(b)
    b = bundle(); b['nodes']['leaf']['depth'] = 1
    b['bundle_ref'] = digest({k: v for k, v in b.items() if k != 'bundle_ref'})
    with pytest.raises(ValueError):
        HierarchyExecutor(b)


def test_semantic_scope_union_does_not_add_signature_lookup_or_case_routes():
    a = [[{'flag': 'requires_spatial_relation', 'value': True}]]
    b = [[{'flag': 'requires_spatial_relation', 'value': True}, {'flag': 'requires_presence', 'value': False}]]
    assert union([a, b]) == a
    assert matches(rows(3)[0]['scope'], a)
    with pytest.raises(ValueError):
        matches(rows(3)[0]['scope'], [[{'flag': 'source_group', 'value': True}]])


def test_merge_gate_protects_partial_and_uses_full_denominator():
    data = rows(24)
    before = [r['reference'] for r in data]
    after = list(before); after[1] = 2
    c = {'active_policy_nodes': 20, 'router_tests': 2}
    d = decide(data, before, after, {'all': list(range(24))}, c, {**c, 'active_policy_nodes': 10})
    assert d['status'] == 'rejected'
    assert 'partial_recall_regression' in d['reasons'] and d['after']['total'] == 24
    with pytest.raises(ValueError):
        decide(data, before, after[:-1], {}, c, c)


def test_merge_gate_accepts_only_valid_improvement_or_lossless_compression():
    data = rows(24); correct = [r['reference'] for r in data]
    before = [0] * 24
    c = {'active_policy_nodes': 20, 'router_tests': 2}
    assert decide(data, before, correct, {'all': range(24)}, c, c)['status'] == 'accepted'
    assert decide(data, correct, correct, {'all': range(24)}, c, c)['status'] == 'rejected'
    smaller = {**c, 'active_policy_nodes': 10}
    assert decide(data, correct, correct, {'all': range(24)}, c, smaller)['lossless_compression']
    insufficient = decide(data[:12], correct[:12], correct[:12], {'all': range(12)}, c, smaller)
    assert insufficient['status'] == 'insufficient'


def test_scope_regression_cannot_hide_behind_global_improvement():
    data = rows(48); correct = [r['reference'] for r in data]
    before, after = list(correct), list(correct)
    for i in (24, 27, 30, 33):
        before[i] = 1
    for i in (0, 3):
        after[i] = 1
    c = {'active_policy_nodes': 20, 'router_tests': 2}
    d = decide(data, before, after, {'protected_family': range(8)}, c, c)
    assert d['after']['correct'] > d['before']['correct']
    assert d['status'] == 'rejected' and 'protected_scope_regression:protected_family' in d['reasons']


def test_shared_mistakes_do_not_become_a_positive_agreement_score():
    data = rows(12, 'a') + rows(12, 'b') + rows(12, 'c')
    candidates = []
    for b in ('a', 'b'):
        part = [r for r in data if r['batch'] == b]
        candidates.append({**fit(part, 'local_shallow'), 'node_id': b,
                           'fit_sources': [r['source_group'] for r in part]})
    original = compatibility(*candidates, data)
    changed = [{**r, 'reference': (r['reference'] + 1) % 3} if r['batch'] == 'c' else r for r in data]
    wrong = compatibility(*candidates, changed)
    assert wrong['outside_both_probes']['counts']['agree_on_mistake'] == 12
    assert wrong['outside_both_probes']['counts'].get('both_correct', 0) == 0
    assert wrong['rank'] == original['rank']


def test_shared_parent_keeps_missing_failures_in_union_and_denominator(tmp_path):
    data = rows(12, 'a') + rows(12, 'b')
    data[0]['features'] = None
    fits = Fits(tmp_path)
    bank = {}
    for b in ('a', 'b'):
        selected = [r for r in data if r['batch'] == b]
        fitted = fit(selected, 'local_shallow')
        bank[b] = {**fitted, 'node_id': b, 'fit_sources': [r['source_group'] for r in selected],
                   'scope': [[{'flag': 'requires_spatial_relation', 'value': True}]], 'children': [], 'depth': 0}
    parent, manifest = parent_node(['a', 'b'], bank, data, fits)
    assert set(parent['fit_sources']) == {r['source_group'] for r in data}
    assert manifest['missing_evidence_sources_retained'] == [data[0]['source_group']]
    assert parent['metrics']['total'] == 24 and parent['metrics']['unresolved'] == 1
    assert all(s['originating_batches'] == 2 for s in parent['leaf_support'])


def test_inference_does_not_fit_or_access_training_labels(monkeypatch):
    b = bundle(); executor = HierarchyExecutor(b); data = rows(3)
    from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree
    def forbidden(*args, **kwargs):
        raise AssertionError('Inference attempted fitting')
    monkeypatch.setattr(PortableSemanticTree, 'fit', forbidden)
    assert [r['prediction'] for r in executor.predict_records(
        [r['features'] for r in data], [r['scope'] for r in data])] == [0, 1, 2]


def test_frozen_package_preserves_prompt_hashes_and_rejects_changed_contracts(tmp_path):
    original = bundle(); manifest = export_package(tmp_path, original)
    assert load_package(tmp_path).export() == original
    assert not manifest['training_records_included']
    (tmp_path / 'interpret.txt').write_text('changed meaning')
    with pytest.raises(ValueError):
        load_package(tmp_path)


def test_prediction_cli_rejects_labels_before_loading_a_policy(tmp_path):
    from run.calitree_semantic_hierarchy_predict import predict
    with pytest.raises(ValueError, match='labels'):
        predict(tmp_path / 'missing.json', {'reference': 1})


def hierarchy_fixture(tmp_path):
    """Synthetic logical test, deliberately starting with redundant weak routes.

    Different batch-correlated semantic shortcuts are jointly replaceable by
    the same reusable physical rule. These are not AURORA accuracy observations.
    """
    fields = ['same_instance_essential', 'recognizable_counterpart_sufficient',
              'replacement_authorized', 'not_relevant']
    identities = ['same_instance', 'recognizable_transformed_counterpart', 'replacement_or_loss', 'uncertain']
    data, assignment = [], {}
    for j, b in enumerate(('a', 'b', 'c', 'd')):
        for i in range(12):
            feature = synthetic_record(meaning_available=True, outcome_all_true_all=i % 3 == 2,
                                       intermediate_all_true_any=i % 3 == 1)
            feature['features']['meaning_retention_need_' + fields[j] + '_all'] = i % 3 == 2
            feature['features']['meaning_identity_evidence_' + identities[j] + '_all'] = i % 3 == 1
            r = {'case': f'{b}-{i}', 'source_group': f'{b}-source-{i:02}', 'batch': b,
                 'reference': i % 3, 'instruction': f'Logical operation {b} {i}', 'features': feature,
                 'scope': {k: k == 'requires_spatial_relation' for k in FLAGS}}
            data.append(r); assignment[r['source_group']] = i // 3
    weak = fit([{**r, 'reference': 0} for r in data], 'local_shallow')['runtime']
    def context(selected):
        bank = {}
        for b in ('a', 'b', 'c', 'd'):
            part = [r for r in selected if r['batch'] == b]
            fitted = fit(part, 'local_shallow')
            bank[b] = {**fitted, 'node_id': b, 'fit_sources': [r['source_group'] for r in part],
                       'fit_cases': [r['case'] for r in part], 'originating_batches': [b], 'children': [], 'depth': 0}
        routes = [{'node_id': b, 'scope': [[{'flag': 'requires_spatial_relation', 'value': True}]]} for b in bank]
        nodes = {b: {'policy': v['runtime'], 'children': [], 'depth': 0} for b, v in bank.items()}
        return {'candidates': bank, 'local_registry': list(bank.values()),
                'bundle': export_bundle(weak, nodes, routes, {})}
    full = context(data)
    contexts = {f: context([r for r in data if assignment[r['source_group']] != f]) for f in range(4)}
    return data, assignment, full, contexts


def test_bounded_builder_really_iterates_and_restores_a_multilevel_hierarchy(tmp_path):
    data, assignment, full, contexts = hierarchy_fixture(tmp_path)
    emitted = {}
    result = build(data, assignment, full, contexts, Fits(tmp_path), lambda key, value: emitted.update({key: value}))
    assert result['acceptance_counts'].get('accepted', 0) >= 2
    assert max(n['depth'] for n in result['bundle']['nodes'].values()) >= 2
    assert result['final_oof_metrics']['correct'] == 48
    executor = HierarchyExecutor(result['bundle'])
    assert [p['prediction'] for p in executor.predict_records(
        [r['features'] for r in data], [r['scope'] for r in data])] == [r['reference'] for r in data]
    assert result['proposal_count'] <= 24 and emitted
    replay = build(data, assignment, full, contexts, Fits(tmp_path, replay=True), lambda *_: None)
    assert replay['bundle'] == result['bundle'] and replay['history'] == result['history']

