"""M6 full-union parent fitting and guarded replacement of actual routing."""
from copy import deepcopy

from ...decision.artifacts import digest
from .hierarchy_protocol_v9 import MERGE_GATES, macro_fraction, score
from .hierarchy_scopes_v9 import union, matches
from .hierarchy_runtime_v9 import export_bundle, HierarchyExecutor
from .hierarchy_fit_v9 import complexity


def parent_node(children, bank, rows, fits):
    seeds = [bank[c] for c in children]
    sources = set().union(*(set(c['fit_sources']) for c in seeds))
    selected = sorted((r for r in rows if r['source_group'] in sources), key=lambda r: r['source_group'])
    if {r['source_group'] for r in selected} != sources:
        raise ValueError('Parent lost a descendant fitting source')
    if any(c['scope'] is None for c in seeds):
        return None, {'status': 'insufficient', 'reason': 'child_scope_not_supported_in_this_fit'}
    fitted = fits.get(selected, 'pooled', [c['runtime'] for c in seeds], shared=True)
    node_id = 'parent-' + digest(sorted(children))[:16]
    node = {**fitted, 'node_id': node_id, 'fit_sources': [r['source_group'] for r in selected],
            'fit_cases': [r['case'] for r in selected],
            'originating_batches': sorted({r['batch'] for r in selected}),
            'children': sorted(children), 'depth': 1 + max(c['depth'] for c in seeds),
            'scope': union([c['scope'] for c in seeds])}
    if any(s['originating_batches'] < 2 for s in node['leaf_support']):
        raise ValueError('A claimed shared parent rule lacks cross-batch support')
    union_manifest = {'status': 'fitted', 'node_id': node_id, 'children': sorted(children),
        'child_source_sets': {c['node_id']: c['fit_sources'] for c in seeds},
        'full_deduplicated_union': node['fit_sources'],
        'missing_evidence_sources_retained': [r['source_group'] for r in selected if r['features'] is None],
        'reference_ref': digest([r['reference'] for r in selected]),
        'warm_policy_refs': [c['runtime']['artifact_ref'] for c in seeds],
        'targets': 'Original dataset reference labels, never child predictions.'}
    return node, union_manifest


def replacement(before, node, bank):
    if node is None:
        return deepcopy(before)
    bank = {**bank, node['node_id']: node}
    descendants = set()
    def descend(name):
        if name in descendants:
            return
        descendants.add(name)
        for c in bank[name]['children']:
            descend(c)
    for c in node['children']:
        descend(c)
    routes = deepcopy(before['routes'])
    indices = [i for i, r in enumerate(routes) if r['node_id'] in descendants]
    position = min(indices) if indices else 0
    routes = [r for r in routes if r['node_id'] not in descendants]
    routes.insert(min(position, len(routes)), {'node_id': node['node_id'], 'scope': node['scope']})
    nodes = {}
    def include(name):
        if name in nodes:
            return
        value = bank[name]
        nodes[name] = {'policy': value['runtime'], 'children': value['children'], 'depth': value['depth']}
        for c in value['children']:
            include(c)
    for r in routes:
        include(r['node_id'])
    return export_bundle(before['pooled'], nodes, routes, before['extraction'])


def active_complexity(bundle):
    policies = {bundle['pooled']['artifact_ref']: bundle['pooled']}
    for route in bundle['routes']:
        policy = bundle['nodes'][route['node_id']]['policy']
        policies[policy['artifact_ref']] = policy
    return {'active_policy_nodes': sum(complexity(p['tree'])['nodes'] for p in policies.values()),
            'active_rules': sum(complexity(p['tree'])['rules'] for p in policies.values()),
            'router_tests': sum(len(c) for r in bundle['routes'] for c in r['scope']),
            'stored_policy_nodes': sum(complexity(v['policy']['tree'])['nodes'] for v in bundle['nodes'].values())
                                   + complexity(bundle['pooled']['tree'])['nodes']}


def decide(rows, before, after, scopes, complexity_before, complexity_after, *, structural_errors=()):
    """M0 gates on identical, full-denominator actual routed predictions."""
    if len(before) != len(rows) or len(after) != len(rows):
        raise ValueError('A merge comparison dropped validation cases')
    bm, am = score(rows, before), score(rows, after)
    failures = list(structural_errors); insufficient = []
    if any(c['support'] < MERGE_GATES['min_validation_sources_per_label'] for c in bm['per_class'].values()):
        insufficient.append('fewer_than_eight_validation_sources_per_label')
    protected = {}
    for name, indices in scopes.items():
        indices = list(indices)
        if len(indices) < MERGE_GATES['min_validation_sources_per_scope']:
            insufficient.append('insufficient_protected_scope:' + name)
            continue
        subset = [rows[i] for i in indices]
        b, a = score(subset, [before[i] for i in indices]), score(subset, [after[i] for i in indices])
        protected[name] = {'before': b, 'after': a}
        if a['correct'] < b['correct'] - MERGE_GATES['max_additional_errors_other_class_or_scope']:
            failures.append('protected_scope_regression:' + name)
    if macro_fraction(am) < macro_fraction(bm):
        failures.append('macro_f1_regression')
    if am['correct'] < bm['correct'] - MERGE_GATES['max_additional_errors_total']:
        failures.append('accuracy_regression')
    if am['per_class']['partial']['correct'] < bm['per_class']['partial']['correct']:
        failures.append('partial_recall_regression')
    for k in ('no', 'yes'):
        if am['per_class'][k]['correct'] < bm['per_class'][k]['correct'] - MERGE_GATES['max_additional_errors_other_class_or_scope']:
            failures.append(k + '_recall_regression')
    if am['unresolved'] > bm['unresolved']:
        failures.append('coverage_regression')
    improved = (macro_fraction(am) > macro_fraction(bm) or am['correct'] > bm['correct']
                or am['unresolved'] < bm['unresolved'])
    lossless = (am['correct'] >= bm['correct'] and macro_fraction(am) >= macro_fraction(bm)
                and all(am['per_class'][k]['correct'] >= bm['per_class'][k]['correct'] for k in bm['per_class']))
    # Both rules and routing tests count. Inactive archived children are reported
    # as storage, not falsely counted as executed inference work.
    cb = complexity_before['active_policy_nodes'] + complexity_before['router_tests']
    ca = complexity_after['active_policy_nodes'] + complexity_after['router_tests']
    compressed = lossless and ca < cb
    if not improved and not compressed:
        failures.append('no_improvement_or_lossless_compression')
    status = 'rejected' if failures else 'insufficient' if insufficient else 'accepted'
    return {'status': status, 'reasons': failures, 'insufficient_evidence': insufficient,
            'before': bm, 'after': am, 'protected_scopes': protected,
            'complexity_before': complexity_before, 'complexity_after': complexity_after,
            'measured_improvement': improved, 'lossless_compression': compressed}


def predictions(bundle, rows):
    return HierarchyExecutor(bundle).predict_records([r['features'] for r in rows], [r['scope'] for r in rows])

