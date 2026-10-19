"""M5--M7 on exact descendant unions, without M4 or an inference router.

The scheduler searches balanced binary training hierarchies over four or eight
seed groups. Set masks exist only in this bounded training search. A completed
root exports one ordinary portable semantic policy, with no membership lookup.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product

from ...decision.artifacts import digest
from .portable_tree_v8 import metrics
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_review_v8 import violations
from .union_groups_v10 import validate_partition

VERSION = 'router-free-union-merges-v10'
LIMITS = {'max_seed_groups': 8, 'max_hierarchy_depth': 3, 'retained_policies_per_union': 2,
          'max_parent_evaluations': 1536, 'accuracy_floor_numerator': 9, 'accuracy_floor_denominator': 10,
          'max_cold_fits_per_run': 256}


def predict(model, rows):
    return PortableRuleExecutor(model['runtime']).predict_records([r['features'] for r in rows])


def predicates(tree):
    if 'feature' not in tree:
        return set()
    return {tree['feature']} | predicates(tree['true']) | predicates(tree['false'])


def macro_fraction(m):
    return sum((Fraction(2 * c['correct'], c['support'] + c['predicted'])
                if c['support'] + c['predicted'] else Fraction(0)) for c in m['per_class'].values()) / 3


def rank(model):
    m = model['metrics']
    return (-m['correct'], -macro_fraction(m), -m['worst_present_class_recall'],
            model['complexity']['nodes'], model['complexity']['depth'], model['runtime']['artifact_ref'])


def proposal(left, right, by_source):
    parts = [[by_source[s] for s in n['fit_sources']] for n in (left, right)]
    transfer = []
    for a, b, selected in ((left, right, parts[1]), (right, left, parts[0])):
        ps = predict(a, selected)
        transfer.append({'from': a['node_id'], 'to': b['node_id'],
                         'sources': [r['source_group'] for r in selected],
                         'metrics': metrics([p['prediction'] for p in ps], [r['reference'] for r in selected])})
    sets = [predicates(n['runtime']['tree']) for n in (left, right)]
    overlap = Fraction(len(sets[0] & sets[1]), len(sets[0] | sets[1])) if sets[0] | sets[1] else Fraction(0)
    roles = [{k for r in selected if r['features'] is not None for k, v in r['features']['features'].items()
              if k.startswith('requires_') and v} for selected in parts]
    role_overlap = Fraction(len(roles[0] & roles[1]), len(roles[0] | roles[1])) if roles[0] | roles[1] else Fraction(0)
    score = overlap + role_overlap + sum(macro_fraction(v['metrics']) for v in transfer) / 2
    union = parts[0] + parts[1]
    ps = [predict(n, union) for n in (left, right)]
    behavior = Counter()
    for i, r in enumerate(union):
        a, b = [p[i]['prediction'] for p in ps]; y = r['reference']
        behavior['both_correct' if a == b == y else 'left_only_correct' if a == y else 'right_only_correct' if b == y else 'both_wrong'] += 1
        if a == b != y:
            behavior['agree_on_mistake'] += 1
    return {'children': [left['node_id'], right['node_id']], 'transfer': transfer,
            'predicate_overlap': float(overlap), 'operation_overlap': float(role_overlap),
            'shared_predicates': sorted(sets[0] & sets[1]), 'training_behavior': dict(behavior),
            'score_numerator': score.numerator, 'score_denominator': score.denominator,
            'scope': 'Pair training sources only. Shared mistakes are recorded, never a positive agreement score.'}


def gate(candidate, children, rows):
    ps = predict(candidate, rows); m = metrics([p['prediction'] for p in ps], [r['reference'] for r in rows])
    failures = []
    if not candidate['portable'] or violations(candidate['policy']['tree']):
        failures.append('unsupported_or_explicitly_contradictory_rule')
    if 10 * m['correct'] <= 9 * len(rows):
        failures.append('union_accuracy_not_strictly_above_90_percent')
    for name, c in m['per_class'].items():
        if c['support'] >= 2 and not c['correct']:
            failures.append('supported_class_collapse:' + name)
    source_set = {r['source_group'] for r in rows}
    expected = set().union(*(set(c['fit_sources']) for c in children))
    if source_set != expected or set(candidate['policy']['training']['source_groups']) != expected:
        failures.append('incomplete_descendant_union')
    by_source = {r['source_group']: p for r, p in zip(rows, ps)}
    retention = []
    for child in children:
        selected = [r for r in rows if r['source_group'] in set(child['fit_sources'])]
        before = metrics([p['prediction'] for p in predict(child, selected)], [r['reference'] for r in selected])
        after = metrics([by_source[r['source_group']]['prediction'] for r in selected], [r['reference'] for r in selected])
        budget = max(1, len(selected) // 10)
        if after['correct'] < before['correct'] - budget:
            failures.append('child_retention_regression:' + child['node_id'])
        retention.append({'child': child['node_id'], 'before': before, 'after': after,
                          'max_additional_errors': budget})
    shared_leaves = []
    for leaf in _leaves(candidate['policy']['tree']):
        support = set(leaf['source_groups'])
        shared_leaves.append(sum(bool(support & set(c['fit_sources'])) for c in children) == 2)
    return {'status': 'accepted' if not failures else 'rejected', 'reasons': failures,
            'metrics': m, 'child_retention': retention, 'shared_terminal_rules': sum(shared_leaves),
            'total_terminal_rules': len(shared_leaves),
            'parent_nodes': candidate['complexity']['nodes'],
            'separate_child_nodes': sum(c['complexity']['nodes'] for c in children),
            'comparison_scope': 'The exact deduplicated descendant union; no unrelated cases or external routing.'}


def _leaves(tree):
    if 'feature' not in tree:
        yield tree
    else:
        yield from _leaves(tree['true']); yield from _leaves(tree['false'])


def _node(candidate, mask, children, rows):
    value = {**deepcopy(candidate), 'mask': mask, 'children': [c['node_id'] for c in children],
             'fit_sources': sorted(r['source_group'] for r in rows),
             'height': 1 + max(c['height'] for c in children) if children else 0}
    value['node_id'] = ('parent-' if children else 'seed-') + digest([
        mask, value['children'], candidate['runtime']['artifact_ref']])[:20]
    return value


def learn(rows, groups, engine, fits, emit):
    validate_partition(groups, rows)
    if len(groups) not in (4, 8):
        raise ValueError('This sealed balanced search supports four or eight training groups')
    by_source = {r['source_group']: r for r in rows}
    registry, retained, seed_reports = {}, {}, []
    for i, sources in enumerate(groups):
        selected = sorted((by_source[s] for s in sources), key=lambda r: r['source_group'])
        candidates, fit_refs = fits.candidates(selected, engine)
        ordered = sorted(candidates, key=rank)[:LIMITS['retained_policies_per_union']]
        if not ordered:
            raise ValueError('No portable initial policy; cannot silently drop a training group')
        nodes = [_node(c, 1 << i, [], selected) for c in ordered]
        retained[1 << i] = nodes
        for node in nodes:
            registry[node['node_id']] = node
        seed_reports.append({'seed': i, 'sources': sources, 'class_counts': dict(Counter(r['reference'] for r in selected)),
            'policies': [n['node_id'] for n in nodes], 'fit_refs': fit_refs,
            'accuracy_floor_used_for_initialization': False,
            'note': 'All seed sources, including missing evidence, remain available. Only accepted parents must pass union gates.'})
    emit('seeds', {'groups': seed_reports, 'nodes': registry})
    proposals, levels = [], []
    for size in (2, 4, 8):
        if size > len(groups):
            continue
        level = []
        for bits in combinations(range(len(groups)), size):
            mask = sum(1 << i for i in bits)
            combinations_for_union = []
            for a_bits in combinations(bits[1:], size // 2 - 1):
                left_mask = (1 << bits[0]) | sum(1 << i for i in a_bits)
                right_mask = mask ^ left_mask
                for left, right in product(retained.get(left_mask, []), retained.get(right_mask, [])):
                    diagnostic = proposal(left, right, by_source)
                    combinations_for_union.append((diagnostic, left, right))
            if not combinations_for_union:
                level.append({'mask': mask, 'status': 'no_qualified_child_partition'})
                continue
            combinations_for_union.sort(key=lambda x: (-Fraction(x[0]['score_numerator'], x[0]['score_denominator']),
                                                       x[1]['node_id'], x[2]['node_id']))
            selected_sources = sorted({s for i in bits for s in groups[i]})
            selected = [by_source[s] for s in selected_sources]
            accepted = []
            for diagnostic, left, right in combinations_for_union:
                if len(proposals) >= LIMITS['max_parent_evaluations']:
                    raise ValueError('Declared union proposal budget exhausted; no complete result')
                candidates, fit_refs = fits.candidates(selected, engine, [left, right])
                evaluations = [(c, gate(c, [left, right], selected)) for c in candidates]
                viable = [(c, g) for c, g in evaluations if g['status'] == 'accepted']
                record = {'index': len(proposals), 'mask': mask, 'seed_bits': list(bits),
                          'children': [left['node_id'], right['node_id']], 'sources': selected_sources,
                          'diagnostic': diagnostic, 'fit_refs': fit_refs,
                          'evaluations': [{'policy_ref': c['runtime']['artifact_ref'], 'initialization': c['initialization'],
                                           'decision': g} for c, g in evaluations]}
                if viable:
                    candidate, decision = min(viable, key=lambda x: rank(x[0]))
                    node = _node(candidate, mask, [left, right], selected)
                    if node['height'] > LIMITS['max_hierarchy_depth']:
                        raise ValueError('Union hierarchy exceeded depth budget')
                    record.update(status='accepted', parent=node['node_id'], decision=decision)
                    registry[node['node_id']] = node; accepted.append(node)
                else:
                    record.update(status='rejected', parent=None)
                proposals.append(record); emit('proposals/' + str(record['index']), record)
            unique = {}
            for node in sorted(accepted, key=rank):
                unique.setdefault(node['runtime']['artifact_ref'], node)
            retained[mask] = list(unique.values())[:LIMITS['retained_policies_per_union']]
            level.append({'mask': mask, 'status': 'qualified' if retained[mask] else 'no_parent_passed',
                          'sources': len(selected), 'retained': [n['node_id'] for n in retained[mask]]})
            print({'stage': 'union_merge', 'engine': engine, 'seed_groups': size, 'sources': len(selected),
                   'qualified_parents': len(retained[mask]),
                   'best_correct': retained[mask][0]['metrics']['correct'] if retained[mask] else None,
                   'proposals_so_far': len(proposals)}, flush=True)
        levels.append({'seed_groups': size, 'unions': level})
        emit('level' + str(size), levels[-1])
    full_mask = (1 << len(groups)) - 1
    roots = retained.get(full_mask, [])
    root = min(roots, key=rank) if roots else None
    history = []
    def collect(node):
        for child in node['children']:
            collect(registry[child])
        if node['children']:
            history.append(node['node_id'])
    if root:
        collect(root)
        if set(root['fit_sources']) != set(by_source) or len(history) != len(groups) - 1:
            raise ValueError('Completed union root has incomplete hierarchy lineage')
    return {'version': VERSION, 'engine': engine, 'root': root,
            'root_candidates': [r['node_id'] for r in roots], 'registry': registry,
            'retained': {str(k): [n['node_id'] for n in v] for k, v in retained.items()},
            'proposals': proposals, 'levels': levels, 'selected_merge_order': history,
            'proposal_count': len(proposals), 'accepted_proposals': sum(p['status'] == 'accepted' for p in proposals),
            'selected_merge_count': len(history), 'm4_used': False,
            'stop': 'complete_root' if root else 'no_complete_qualified_balanced_hierarchy',
            'new_model_calls': 0, 'reserved_test_predictions': 0}

