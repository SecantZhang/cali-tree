"""Always-challenger unions and training-only validation of learning procedures.

The v10 gate is imported verbatim. Two retained slots cover reused/refined and
full-grammar generation families; neither family bypasses any acceptance gate.
Cross-validation rebuilds the whole hierarchy inside each fit fold. Its scores
estimate grouping/family procedures, not individual full-data trees.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
import statistics

from ...decision.artifacts import digest
from .union_learning_v10 import UnionFits
from .union_reuse_v11 import ReuseFits
from .union_merges_v10 import gate, rank, proposal, predicates, _node, LIMITS
from .union_groups_v10 import original, split_balanced, semantic, distance, validate_partition
from .portable_tree_v8 import metrics
from .portable_runtime_v8 import PortableRuleExecutor

VERSION = 'always-challenger-validated-unions-v12'
FAMILIES = ('reuse', 'full_grammar')
GROUPINGS = ('original4', 'split8', 'semantic8')
CV = {'folds': 4, 'seed': 20261018,
      'selection_unit': 'Grouping and root-generation family; entire hierarchy refitted within each fold',
      'missing_root': 'All validation sources predict Unresolved; no omitted folds',
      'ranking': 'Pooled OOF macro-F1, worst-class recall, lower fold-score dispersion, training rank, reuse tie-break, stable identity'}


def coalesce(candidates):
    unique = {}
    for c in sorted(candidates, key=lambda n: (rank(n), n['initialization'])):
        key = c['runtime']['artifact_ref']
        if key not in unique:
            unique[key] = deepcopy(c)
        else:
            target = unique[key]
            target['generation_families'] = sorted(set(target['generation_families']) | set(c['generation_families']))
            for family, alternative in c['generation_alternatives'].items():
                target['generation_alternatives'].setdefault(family, deepcopy(alternative))
    return list(unique.values())


class ChallengerFits(ReuseFits):
    def candidates(self, rows, engine, children=()):
        if engine != 'reuse':
            raise ValueError('The v12 learner uses the declared reuse engine')
        if not children:
            values, refs = UnionFits.candidates(self, rows, 'constrained')
            for c in values:
                c['generation_families'] = ['seed']
                c['generation_alternatives'] = {}
            return values, refs
        values, refs = ReuseFits.candidates(self, rows, 'reuse', children)
        bank = []
        inherited = set().union(*(predicates(c['runtime']['tree']) for c in children))
        for value in values:
            c = deepcopy(value)
            family = 'full_grammar' if c['reuse']['kind'] == 'full_grammar_repair' else 'reuse'
            c['generation_families'] = [family]
            c['generation_alternatives'] = {family: {'initialization': c['initialization'], 'reuse': deepcopy(c['reuse'])}}
            bank.append(c)
        # Unconditional challengers, even when a restricted vocabulary passed.
        profiles = ('shallow', 'compact') if len(rows) <= 12 else ('compact', 'deep')
        for profile in profiles:
            fit = self.cold(rows, 'constrained', profile); refs.append(fit['fit_ref'])
            if fit['result'] is None:
                continue
            c = deepcopy(fit['result']); used = predicates(c['runtime']['tree'])
            c['reuse'] = {'version': VERSION, 'kind': 'full_grammar_challenger',
                'child_predicates': sorted(inherited), 'used_predicates': sorted(used),
                'new_used_predicates': sorted(used - inherited), 'parent_union_only': True,
                'profile': profile, 'always_offered': True}
            c['generation_families'] = ['full_grammar']
            c['generation_alternatives'] = {'full_grammar': {'initialization': c['initialization'], 'reuse': deepcopy(c['reuse'])}}
            bank.append(c)
        return coalesce(bank), sorted(set(refs))


def quality(node):
    return (*rank(node), node.get('node_id', ''), node['initialization'])


def retain(candidates, count=2):
    """Keep family coverage within the existing two-slot bound, then quality."""
    if count != LIMITS['retained_policies_per_union']:
        raise ValueError('The declared beam size remains two')
    ordered = sorted(candidates, key=quality)
    # A different lineage can qualify the same runtime under a different recipe.
    unique = {}
    for n in ordered:
        unique.setdefault((n['runtime']['artifact_ref'], tuple(sorted(n['generation_families']))), n)
    ordered = list(unique.values()); chosen = []
    for family in FAMILIES:
        best = next((n for n in ordered if family in n['generation_families']), None)
        if best is not None and all(best is not old for old in chosen):
            chosen.append(best)
    for node in ordered:
        if len(chosen) >= count:
            break
        if all(node is not old for old in chosen):
            chosen.append(node)
    return sorted(chosen, key=quality)[:count]


def folds(rows):
    if len(rows) != 48 or len({r['source_group'] for r in rows}) != 48:
        raise ValueError('Four-fold selection requires the complete 48-source training set')
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row['batch'], row['reference'])].append(row)
    if len(buckets) != 12 or any(len(v) != 4 for v in buckets.values()):
        raise ValueError('Expected four sources per original batch/reference stratum')
    validation = [[] for _ in range(CV['folds'])]
    for key, selected in sorted(buckets.items()):
        for i, row in enumerate(sorted(selected, key=lambda r: digest([VERSION, CV['seed'], key, r['source_group']]))):
            validation[i].append(row)
    result = []
    for i, held in enumerate(validation):
        ids = {r['source_group'] for r in held}
        training = [r for r in rows if r['source_group'] not in ids]
        assert len(training) == 36 and len(held) == 12
        result.append({'fold': i, 'train': training, 'validation': held})
    assert Counter(r['source_group'] for f in result for r in f['validation']) == Counter(r['source_group'] for r in rows)
    return result


def balanced_inner(rows):
    result = []
    for batch in sorted({r['batch'] for r in rows}):
        selected = [r for r in rows if r['batch'] == batch]; capacity = [(len(selected) + 1) // 2, len(selected) // 2]
        groups = [[], []]; counts = [Counter(), Counter()]
        for label in (0, 1, 2):
            for row in sorted((r for r in selected if r['reference'] == label), key=lambda r: r['source_group']):
                slot = min((i for i in (0, 1) if len(groups[i]) < capacity[i]), key=lambda i: (counts[i][label], len(groups[i]), i))
                groups[slot].append(row['source_group']); counts[slot][label] += 1
        result.extend(sorted(g) for g in groups)
    return result


def semantic_inner(rows):
    """Original distance/center/swap rule with eight capacities of four/five."""
    rows = sorted(rows, key=lambda r: r['source_group']); n, k = len(rows), 8
    capacities = [n // k + (i < n % k) for i in range(k)]
    costs = [[distance(a['features'], b['features']) for b in rows] for a in rows]
    present = [i for i, r in enumerate(rows) if r['features'] is not None]
    if len(present) < k:
        raise ValueError('Insufficient observed sources for inner semantic groups')
    centers = [min(present, key=lambda i: (sum(costs[i]), i))]
    while len(centers) < k:
        centers.append(max((i for i in present if i not in centers), key=lambda i: (min(costs[i][j] for j in centers), -i)))
    groups = [[c] for c in centers]
    remaining = [i for i in range(n) if i not in centers]
    remaining.sort(key=lambda i: (-sorted(costs[i][c] for c in centers)[1] + min(costs[i][c] for c in centers), i))
    for i in remaining:
        slot = min((j for j in range(k) if len(groups[j]) < capacities[j]), key=lambda j: (costs[i][centers[j]], j))
        groups[slot].append(i)
    for _ in range(64):
        choices = []
        for a in range(k):
            for b in range(a + 1, k):
                for i in groups[a]:
                    for j in groups[b]:
                        before = sum(costs[i][v] for v in groups[a] if v != i) + sum(costs[j][v] for v in groups[b] if v != j)
                        after = sum(costs[j][v] for v in groups[a] if v != i) + sum(costs[i][v] for v in groups[b] if v != j)
                        if after < before:
                            choices.append((after - before, a, b, i, j))
        if not choices:
            break
        _, a, b, i, j = min(choices)
        groups[a].remove(i); groups[b].remove(j); groups[a].append(j); groups[b].append(i)
    return sorted((sorted(rows[i]['source_group'] for i in g) for g in groups), key=digest)


def grouping(rows, method):
    if method == 'original4':
        groups = original(rows)
    elif method == 'split8':
        groups = split_balanced(rows) if len(rows) == 48 else balanced_inner(rows)
    elif method == 'semantic8':
        groups = semantic(rows) if len(rows) == 48 else semantic_inner(rows)
    else:
        raise ValueError('Unknown declared grouping')
    validate_partition(groups, rows)
    if len(groups) not in (4, 8):
        raise ValueError('Four or eight groups are required')
    return groups


def family_root(result, family):
    choices = [result['registry'][k] for k in result['root_candidates'] if family in result['registry'][k]['generation_families']]
    return min(choices, key=quality, default=None)


def cv_summary(fold_results):
    """Every source/fold is retained, including absent qualifying roots."""
    predictions = [p for f in fold_results for p in f['predictions']]
    refs = [p for f in fold_results for p in f['references']]
    return {'metrics': metrics(predictions, refs), 'fold_macro_f1': [f['metrics']['macro_f1'] for f in fold_results],
        'fold_macro_f1_std': statistics.pstdev(f['metrics']['macro_f1'] for f in fold_results),
        'feasible_folds': sum(f['available'] for f in fold_results), 'folds': len(fold_results),
        'failed_folds': [f['fold'] for f in fold_results if not f['available']]}


def choose_root(results, validation):
    choices = []
    for method, result in results.items():
        for family in FAMILIES:
            root = family_root(result, family)
            if root is None:
                continue
            cv = validation[method][family]; m = cv['metrics']
            key = (-m['macro_f1'], -m['worst_present_class_recall'], cv['fold_macro_f1_std'],
                   *rank(root)[:-1], 0 if family == 'reuse' else 1, root['runtime']['artifact_ref'],
                   root['node_id'], method, family)
            choices.append((key, method, family, root))
    if not choices:
        return None
    _, method, family, root = min(choices, key=lambda value: value[0])
    return {'method': method, 'family': family, 'root': root, 'validation': validation[method][family],
        'validation_informative': any(v['metrics']['correct'] for m in validation.values() for v in m.values())}


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
                          'evaluations': [{'policy_ref': c['runtime']['artifact_ref'], 'initialization': c['initialization'], 'generation_families': c['generation_families'],
                                           'decision': g} for c, g in evaluations]}
                if viable:
                    retained_candidates = retain([c for c, g in viable])
                    nodes = []
                    for candidate in retained_candidates:
                        node = _node(candidate, mask, [left, right], selected)
                        if node['height'] > LIMITS['max_hierarchy_depth']:
                            raise ValueError('Union hierarchy exceeded depth budget')
                        registry[node['node_id']] = node; accepted.append(node); nodes.append(node)
                    record.update(status='accepted', parent=nodes[0]['node_id'],
                        parents=[n['node_id'] for n in nodes],
                        decision=next(g for c, g in viable if c['runtime']['artifact_ref'] == nodes[0]['runtime']['artifact_ref']))
                else:
                    record.update(status='rejected', parent=None, parents=[])
                proposals.append(record); emit('proposals/' + str(record['index']), record)
            retained[mask] = retain(accepted)
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

