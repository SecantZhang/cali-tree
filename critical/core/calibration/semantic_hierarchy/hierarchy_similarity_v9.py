"""M5: explainable proposal ranking, never merge authorization."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations

from ...decision.artifacts import digest
from .portable_runtime_v8 import PortableRuleExecutor
from .hierarchy_scopes_v9 import proposals, matches
from .hierarchy_protocol_v9 import ROUTING, SEARCH, score, macro_fraction


def supported_scope(candidate, rows, context):
    route = next((r for r in context['bundle']['routes'] if r['node_id'] == candidate['node_id']), None)
    if route:
        return deepcopy(route['scope'])
    fitting = set(candidate['fit_sources']); options = []
    for scope, covered in proposals([r['scope'] for r in rows]):
        inside = [i for i in covered if rows[i]['source_group'] in fitting]
        outside = [i for i in covered if rows[i]['source_group'] not in fitting]
        counts = Counter(rows[i]['reference'] for i in outside)
        if (len(inside) < ROUTING['min_fit_sources'] or len(outside) < ROUTING['min_validation_sources']
                or min(counts[k] for k in range(3)) < ROUTING['min_validation_per_class']
                or len({rows[i]['batch'] for i in outside}) < ROUTING['min_validation_batches']):
            continue
        # This proposes applicability; expert correctness does not make it a
        # validated route. M6 must validate the complete candidate replacement.
        options.append(((-len(inside), len(scope[0]), -len(outside), digest(scope)), scope))
    return deepcopy(min(options, key=lambda v: v[0])[1]) if options else None


def seed_bank(context, rows, *, include_duplicates=False):
    source = context['local_registry'] if include_duplicates else context['candidates'].values()
    bank = {}
    for value in source:
        candidate = deepcopy(value)
        candidate['scope'] = supported_scope(candidate, rows, context)
        bank[candidate['node_id']] = candidate
    return bank


def predicate_set(tree):
    if 'feature' not in tree:
        return set()
    return {tree['feature']} | predicate_set(tree['true']) | predicate_set(tree['false'])


def _jaccard(a, b):
    return Fraction(len(a & b), len(a | b)) if a | b else Fraction(0)


def compatibility(left, right, rows):
    sources = [set(c['fit_sources']) for c in (left, right)]
    predictions = [PortableRuleExecutor(c['runtime']).predict_records([r['features'] for r in rows])
                   for c in (left, right)]
    transfer = []
    for i in (0, 1):
        indices = [j for j, r in enumerate(rows) if r['source_group'] in sources[1 - i]
                   and r['source_group'] not in sources[i]]
        subset = [rows[j] for j in indices]
        transfer.append({'from': (left, right)[i]['node_id'], 'to': (left, right)[1 - i]['node_id'],
                         'sources': [r['source_group'] for r in subset],
                         'metrics': score(subset, [predictions[i][j] for j in indices]) if subset else None})
    probe_indices = [i for i, r in enumerate(rows) if r['source_group'] not in sources[0] | sources[1]]
    behavior = Counter(); per_class = {k: Counter() for k in ('no', 'partial', 'yes')}
    for i in probe_indices:
        y = rows[i]['reference']; a, b = (p[i]['prediction'] for p in predictions)
        key = 'both_correct' if a == b == y else 'left_only_correct' if a == y else 'right_only_correct' if b == y else 'both_wrong'
        behavior[key] += 1; per_class[('no', 'partial', 'yes')[y]][key] += 1
        if a == b and a != y:
            behavior['agree_on_mistake'] += 1
        if a != b:
            behavior['disagree'] += 1
    predicates = [predicate_set(c['runtime']['tree']) for c in (left, right)]
    roles = []
    for source in sources:
        roles.append({flag for r in rows if r['source_group'] in source and r['scope'] is not None
                      for flag, value in r['scope'].items() if value})
    structural = _jaccard(predicates[0], predicates[1])
    role_overlap = _jaccard(roles[0], roles[1])
    mutual = sum(macro_fraction(t['metrics']) if t['metrics'] else Fraction(0) for t in transfer) / 2
    complementary = Fraction(behavior['left_only_correct'] + behavior['right_only_correct'], len(probe_indices)) if probe_indices else Fraction(0)
    rank = structural + role_overlap + mutual + complementary
    return {'predicate_overlap': {'intersection': sorted(predicates[0] & predicates[1]),
                                  'union': sorted(predicates[0] | predicates[1]), 'jaccard': float(structural)},
            'instruction_role_overlap': {'intersection': sorted(roles[0] & roles[1]),
                                         'union': sorted(roles[0] | roles[1]), 'jaccard': float(role_overlap)},
            'mutual_transfer': transfer,
            'outside_both_probes': {'source_groups': [rows[i]['source_group'] for i in probe_indices],
                                   'counts': dict(behavior), 'per_class': {k: dict(v) for k, v in per_class.items()}},
            'rank': {'numerator': rank.numerator, 'denominator': rank.denominator,
                     'formula': 'predicate Jaccard + instruction-role Jaccard + mutual macro-F1 + complementary-error fraction'},
            'warning': 'Agreement on mistakes is recorded separately and never counted as compatibility success.'}


def propose(frontier, bank, rows, tried):
    candidates, rejected = [], []
    for pair in combinations(sorted(frontier), 2):
        left, right = (bank[k] for k in pair)
        key = digest(pair)
        reason = None
        if key in tried:
            reason = 'already_evaluated_in_current_state'
        elif max(left['depth'], right['depth']) >= SEARCH['max_hierarchy_depth']:
            reason = 'hierarchy_depth_budget'
        elif not left['specialist_eligible'] or not right['specialist_eligible']:
            reason = 'supported_label_collapse_or_instruction_support'
        elif left['scope'] is None or right['scope'] is None:
            reason = 'no_measurable_instruction_scope'
        elif set(left['fit_sources']) & set(right['fit_sources']):
            reason = 'overlapping_alternative_lineages'
        elif len(set(left['originating_batches']) | set(right['originating_batches'])) < 2:
            reason = 'no_cross_batch_parent_support'
        if reason:
            rejected.append({'children': list(pair), 'pair_ref': key, 'reason': reason})
            continue
        diagnostic = compatibility(left, right, rows)
        candidates.append({'children': list(pair), 'pair_ref': key,
            'union_sources': sorted(set(left['fit_sources']) | set(right['fit_sources'])),
            'compatibility': diagnostic,
            'proposal_only': 'These may be unpromoted local candidates. A parent is compared against the actual pooled/routed system, never an assumed child vote.'})
    candidates.sort(key=lambda p: (-Fraction(p['compatibility']['rank']['numerator'], p['compatibility']['rank']['denominator']),
                                   -len(p['union_sources']), p['pair_ref']))
    return candidates, rejected

