"""Portable M2 fitting, semantic review, and full-union warm starts.

This adds training orchestration without modifying the frozen M2 implementation.
Child trees are relabeled on the complete parent union before competing with the
common grammar. Their predictions are never used as training targets.
"""
from collections import Counter
from copy import deepcopy

from ...decision.artifacts import digest
from .portable_features_v8 import CONTRACT_REF
from .portable_tree_v8 import PortableSemanticTree, metrics
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_review_v8 import violations
from .hierarchy_protocol_v9 import PROFILES, macro_fraction


def _leaf(rows):
    counts = [sum(r['reference'] == k for r in rows) for k in range(3)]
    return {'type': 'leaf', 'prediction': max(range(3), key=lambda k: (counts[k], -k)),
            'support': len(rows), 'counts': counts,
            'source_groups': [r['source_group'] for r in rows],
            'source_batches': dict(sorted(Counter(r['batch'] for r in rows).items()))}


def complexity(tree):
    if 'feature' not in tree:
        return {'nodes': 1, 'rules': 1, 'depth': 0}
    a, b = complexity(tree['true']), complexity(tree['false'])
    return {'nodes': 1 + a['nodes'] + b['nodes'], 'rules': a['rules'] + b['rules'],
            'depth': 1 + max(a['depth'], b['depth'])}


def _refresh(policy, rows):
    policy = deepcopy(policy)
    policy.pop('artifact_ref', None)
    model = PortableSemanticTree(limits=policy['limits'])
    model._artifact = policy
    policy['search']['nodes'] = complexity(policy['tree'])['nodes']
    policy['training']['metrics'] = metrics(
        [d['prediction'] for d in model.predict_records([r['features'] for r in rows])],
        [r['reference'] for r in rows])
    policy['groups'] = model._groups([r['features'] for r in rows], [r['reference'] for r in rows],
                                     [r['source_group'] for r in rows])
    policy['artifact_ref'] = digest(policy)
    PortableSemanticTree.restore(policy)
    return policy


def review(policy, rows):
    """Prune explicit contradictory Yes exceptions, without hiding lost fit.

    M2's original above-90% reviewed policy stays frozen. For smaller/fold/parent
    fits, a contradiction is removed even if no above-90% candidate is possible;
    the resulting fit loss is reported instead of silently weakening the review.
    """
    policy = deepcopy(policy)
    actions = []
    present = [r for r in rows if r['features'] is not None]

    def candidates(node, path=()):
        if 'feature' in node:
            yield path
            yield from candidates(node['true'], path + (True,))
            yield from candidates(node['false'], path + (False,))

    def replace(artifact, path):
        obj = deepcopy(artifact)
        selected = present
        node, parent, key = obj['tree'], None, None
        for value in path:
            selected = [r for r in selected if r['features']['features'][node['feature']] == value]
            parent, key = node, 'true' if value else 'false'
            node = node[key]
        if parent is None:
            obj['tree'] = _leaf(selected)
        else:
            parent[key] = _leaf(selected)
        return obj

    while violations(policy['tree']):
        count = len(violations(policy['tree']))
        options = []
        for path in candidates(policy['tree']):
            candidate = replace(policy, path)
            remaining = len(violations(candidate['tree']))
            if remaining >= count:
                continue
            candidate = _refresh(candidate, rows)
            m = candidate['training']['metrics']
            options.append(((remaining, -macro_fraction(m), -m['correct'],
                             complexity(candidate['tree'])['nodes'], path), candidate, path))
        if not options:
            raise ValueError('Unable to review a contradictory semantic policy')
        _, policy, path = min(options, key=lambda v: v[0])
        actions.append({'collapsed_path': list(path), 'remaining_contradictions': len(violations(policy['tree']))})
    policy['hierarchy_review'] = {'version': 'written-contradiction-review-v9', 'actions': actions,
        'claim': 'Written-path review only; not universal truth guarantees or a runtime output veto.'}
    return _refresh(policy, rows)


def _warm_tree(shape, rows, minimum, shared=False):
    if 'feature' not in shape:
        return _leaf(rows)
    a = [r for r in rows if r['features']['features'][shape['feature']]]
    b = [r for r in rows if not r['features']['features'][shape['feature']]]
    if (min(len(a), len(b)) < minimum
            or shared and min(len({r['batch'] for r in a}), len({r['batch'] for r in b})) < 2):
        return _leaf(rows)
    return {'type': 'split', 'feature': shape['feature'], 'support': len(rows),
            'true': _warm_tree(shape['true'], a, minimum, shared), 'false': _warm_tree(shape['false'], b, minimum, shared)}


def fit(rows, profile, warm_policies=(), *, shared=False):
    rows = sorted(rows, key=lambda r: r['source_group'])
    if (profile not in PROFILES or len({r['source_group'] for r in rows}) != len(rows)
            or any(type(r['reference']) is not int or r['reference'] not in (0, 1, 2)
                   or not isinstance(r['instruction'], str) or not r['instruction'].strip()
                   or any(not isinstance(r[k], str) or not r[k] for k in ('source_group', 'batch')) for r in rows)):
        raise ValueError('Distinct source rows and a declared fit profile required')
    if shared:
        from .shared_parent_v9 import fit_shared
        base = fit_shared(rows, warm_policies, PROFILES[profile])
    else:
        model = PortableSemanticTree(limits=PROFILES[profile]).fit(
            [r['features'] for r in rows], [r['reference'] for r in rows],
            source_groups=[r['source_group'] for r in rows], source_batches=[r['batch'] for r in rows])
        base = model.metadata()
    bank = [('common_grammar', review(base, rows))]
    for child in warm_policies:
        runtime = PortableRuleExecutor(child).metadata()
        candidate = deepcopy(base)
        candidate['tree'] = _warm_tree(runtime['tree'], [r for r in rows if r['features'] is not None],
                                       PROFILES[profile]['min_leaf_sources'], shared)
        candidate = _refresh(candidate, rows)
        bank.append(('child_conditions:' + runtime['artifact_ref'], review(candidate, rows)))

    def rank(item):
        _, artifact = item
        m = artifact['training']['metrics']
        return (-macro_fraction(m), -m['worst_present_class_recall'], -m['correct'],
                complexity(artifact['tree'])['nodes'], digest(PortableRuleExecutor.from_training_policy(artifact).metadata()))

    chosen, policy = min(bank, key=rank)
    runtime = PortableRuleExecutor.from_training_policy(policy).metadata()
    predictions = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
    support = []
    def visit(node):
        if 'feature' not in node:
            group = set(node['source_groups'])
            support.append({'sources': len(group), 'distinct_instructions': len({r['instruction'] for r in rows if r['source_group'] in group}),
                            'originating_batches': len(node['source_batches']), 'prediction': node['prediction']})
        else:
            visit(node['true']); visit(node['false'])
    visit(policy['tree'])
    m = metrics([p['prediction'] for p in predictions], [r['reference'] for r in rows])
    reasons = []
    if any(c['support'] and not c['correct'] for c in m['per_class'].values()):
        reasons.append('supported_label_collapse')
    if any(s['distinct_instructions'] < 2 for s in support):
        reasons.append('insufficient_distinct_instruction_support')
    return {'profile': profile, 'policy': policy, 'runtime': runtime, 'metrics': m,
            'complexity': complexity(runtime['tree']), 'leaf_support': support,
            'specialist_eligible': not reasons, 'eligibility_reasons': reasons,
            'selected_initialization': chosen,
            'warm_start_candidates': [{'initialization': k, 'metrics': p['training']['metrics']} for k, p in bank],
            'feature_contract_ref': CONTRACT_REF}

