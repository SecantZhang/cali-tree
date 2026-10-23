"""Local-fit-first tree compression, with bounded search and lossless merge gates.

References remain the targets. Child accuracy is a constraint, never a target
substitute or a penalty that can be traded for a smaller tree. Failed merges
retain their children; a partial forest has no implicit source-ID router.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations

from ..decision.artifacts import digest
from .semantic_hierarchy.portable_features_v8 import FEATURES, CONTRACT_REF
from .semantic_hierarchy.portable_tree_v8 import VERSION as TREE_VERSION, LIMITS, conflict_report
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from .semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES, violations
from .semantic_hierarchy.hierarchy_fit_v9 import _leaf, _refresh, complexity
from .semantic_hierarchy.union_learning_v10 import validate_rows, describe

VERSION = 'local-accuracy-compression-v18'


@dataclass(frozen=True)
class Config:
    max_depth: int = 6
    split_candidates: int = 16
    max_states: int = 20000
    max_transitions: int = 200000
    max_frontier: int = 256

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ValueError('Positive integer search bounds required')


def predict(model, rows):
    return [p['prediction'] for p in PortableRuleExecutor(model['runtime']).predict_records([r['features'] for r in rows])]


def correct(model, rows):
    return sum(p == r['reference'] for p, r in zip(predict(model, rows), rows))


def rank(model):
    return (-model['metrics']['correct'], model['complexity']['rules'],
            model['complexity']['depth'], model['runtime']['artifact_ref'])


def requirement(model, rows):
    selected = [r for r in rows if r['source_group'] in set(model['policy']['training']['source_groups'])]
    return {'sources': sorted(r['source_group'] for r in selected), 'correct': correct(model, selected)}


def scopes(rows, requirements):
    sources = {r['source_group'] for r in rows}
    result = {}
    for req in requirements:
        selected = tuple(sorted(req['sources']))
        if (not selected or len(set(selected)) != len(selected) or not set(selected) <= sources
                or type(req['correct']) is not int or not 0 <= req['correct'] <= len(selected)):
            raise ValueError('Invalid local accuracy requirement')
        result[selected] = max(result.get(selected, 0), req['correct'])
    if set().union(*(set(k) for k in result)) != sources:
        raise ValueError('Accuracy requirements must cover every training source')
    return [{'sources': list(k), 'correct': v} for k, v in sorted(result.items())]


def gate(model, rows, requirements, *, max_rules):
    """Replay actual runtime accuracy, including abstentions, on every local scope."""
    validate_rows(rows); requirements = scopes(rows, requirements)
    reasons = []
    ordered = sorted(rows, key=lambda r: r['source_group'])
    training = model['policy']['training']
    if (training['feature_ref'] != digest([r['features'] for r in ordered])
            or training['target_ref'] != digest([r['reference'] for r in ordered])):
        reasons.append('changed_training_evidence_or_references')
    if set(model['policy']['training']['source_groups']) != {r['source_group'] for r in rows}:
        reasons.append('incomplete_training_union')
    refreshed = describe(model['policy'], rows, model['initialization'])
    if refreshed['runtime'] != model['runtime']:
        reasons.append('runtime_policy_mismatch')
    if not refreshed['portable'] or violations(model['policy']['tree']):
        reasons.append('unsupported_or_contradictory_rule')
    def check_support(tree, cohort):
        if 'feature' not in tree:
            return bool(cohort) and tree == _leaf(cohort)
        return (tree['support'] == len(cohort)
                and all(check_support(tree[key], [r for r in cohort if r['features']['features'][tree['feature']] == value])
                        for key, value in (('true', True), ('false', False))))
    if not check_support(model['policy']['tree'], [r for r in ordered if r['features'] is not None]):
        reasons.append('changed_leaf_support_or_original_targets')
    retention = []
    for req in requirements:
        selected = [r for r in rows if r['source_group'] in set(req['sources'])]
        after = correct(model, selected)
        retention.append({**req, 'after': after})
        if after < req['correct']:
            reasons.append('local_accuracy_regression')
    rules = complexity(model['runtime']['tree'])['rules']
    if rules > max_rules:
        reasons.append('rule_budget_exceeded')
    return {'status': 'accepted' if not reasons else 'rejected', 'reasons': sorted(set(reasons)),
            'retention': retention, 'rules': rules, 'max_rules': max_rules,
            'metrics': refreshed['metrics'], 'max_additional_local_errors': 0}


def equality_certificate(rows, requirements):
    """Necessary feasibility check for deterministic predictors over these features.

    This optimistic check allows arbitrary labels per distinct feature record,
    ignoring depth/support/majority restrictions. Infeasibility is conclusive;
    feasibility does not promise a supported tree exists.
    """
    requirements = scopes(rows, requirements)
    sets = [set(q['sources']) for q in requirements]
    budgets = tuple(len(q['sources']) - q['correct'] for q in requirements)
    buckets = {}
    for r in rows:
        key = digest(r['features']['features']) if r['features'] is not None else None
        buckets.setdefault(key, []).append(r)
    frontier = {tuple(0 for _ in sets)}; conflicts = []
    for key, bucket in sorted(buckets.items(), key=lambda item: str(item[0])):
        if key is not None and len({r['reference'] for r in bucket}) == 1:
            continue
        conflicts.append({'cases': [r.get('case', r['source_group']) for r in bucket],
                          'labels': [r['reference'] for r in bucket], 'missing_evidence': key is None})
        additions = {tuple(sum(r['source_group'] in s and r['reference'] != k for r in bucket) for s in sets)
                     for k in ((-1,) if key is None else (0, 1, 2))}
        next_frontier = {tuple(a + b for a, b in zip(old, add)) for old in frontier for add in additions}
        frontier = {v for v in next_frontier if all(a <= b for a, b in zip(v, budgets))}
        frontier = {v for v in frontier if not any(w != v and all(a <= b for a, b in zip(w, v)) for w in frontier)}
    return {'feasible': bool(frontier), 'conflicts': conflicts,
            'scope': 'Necessary feature-equality check only; no supported-tree optimality claim.'}


class _BudgetReached(Exception):
    pass


def fit(rows, requirements, *, max_rules, config=Config(), preferred=()):
    """Pareto search over local error vectors and rule counts; never spends fit.

    Each memo state retains distinct error allocations across local scopes.
    Equality of training partitions is only a search equivalence. All aliases
    remain in the report and are reconsidered on each new training union.
    """
    rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
    requirements = scopes(rows, requirements)
    if type(max_rules) is not int or max_rules < 1:
        raise ValueError('Positive rule budget required')
    report = {'version': VERSION, 'config': asdict(config), 'requirements': requirements,
              'max_rules': max_rules, 'states': 0, 'transitions': 0, 'budget_exhausted': False,
              'global_optimality_claim': False, 'new_model_calls': 0}
    report['equality_certificate'] = equality_certificate(rows, requirements)
    if not report['equality_certificate']['feasible']:
        report['stop'] = 'feature_equality_proves_infeasible'; return None, report
    if any(r['features'] is None or not r['features']['features']['meaning_available'] for r in rows):
        report['stop'] = 'new_search_requires_complete_evidence_keep_incumbents'; return None, report
    n = len(rows); full = (1 << n) - 1
    # Component zero measures total errors; remaining components enforce local floors.
    scope_masks = [full] + [sum(1 << i for i, r in enumerate(rows) if r['source_group'] in set(q['sources'])) for q in requirements]
    budgets = [n] + [len(q['sources']) - q['correct'] for q in requirements]
    targets = [sum(1 << i for i, r in enumerate(rows) if r['reference'] == k) for k in range(3)]
    instruction_masks = {}
    for i, r in enumerate(rows):
        instruction_masks[r['instruction']] = instruction_masks.get(r['instruction'], 0) | (1 << i)
    preferred = set(preferred)
    if not preferred <= set(FEATURES):
        raise ValueError('Only declared reusable predicates may be preferred')
    unique = {}; aliases = {}
    for name in sorted(FEATURES, key=lambda k: (k not in preferred, not k.startswith('meaning_'), k)):
        mask = sum(1 << i for i, r in enumerate(rows) if r['features']['features'][name])
        if not mask or mask == full:
            continue
        key = (mask if name in CONTRADICTS_YES else min(mask, full ^ mask), name in CONTRADICTS_YES)
        unique.setdefault(key, (name, mask)); aliases.setdefault(key, []).append(name)
    report['partition_aliases'] = [{'representative': unique[k][0], 'alternatives': v} for k, v in aliases.items()]

    def supported(mask):
        return mask.bit_count() >= 2 and sum(bool(mask & m) for m in instruction_masks.values()) >= 2

    def add(bank, errors, rules, shape):
        if rules > max_rules or any(e > b for e, b in zip(errors, budgets)):
            return
        if errors in bank and bank[errors][0] <= rules:
            return
        if any(v[0] <= rules and all(a <= b for a, b in zip(k, errors)) for k, v in bank.items()):
            return
        for k in list(bank):
            if rules <= bank[k][0] and all(a <= b for a, b in zip(errors, k)):
                del bank[k]
        if len(bank) >= config.max_frontier and errors not in bank:
            raise _BudgetReached
        bank[errors] = (rules, shape)

    root_bank = {}

    @lru_cache(None)
    def solve(mask, depth, forbids_yes):
        if report['states'] >= config.max_states:
            raise _BudgetReached
        report['states'] += 1
        bank = root_bank if mask == full and depth == config.max_depth else {}
        if not supported(mask):
            return bank
        counts = [(mask & t).bit_count() for t in targets]
        label = max(range(3), key=lambda k: (counts[k], -k))
        wrong = mask & (full ^ targets[label])
        if not (forbids_yes and label == 2):
            add(bank, tuple((wrong & s).bit_count() for s in scope_masks), 1, ('leaf', mask))
        if not wrong or depth == 0 or mask.bit_count() < 4:
            return bank
        options = {}
        for name, pmask in unique.values():
            a, b = mask & pmask, mask & (full ^ pmask)
            if not supported(a) or not supported(b):
                continue
            ca, cb = [[(part & t).bit_count() for t in targets] for part in (a, b)]
            key = (a if name in CONTRADICTS_YES else min(a, b), name in CONTRADICTS_YES)
            order = (sum(ca) - max(ca) + sum(cb) - max(cb),
                     -sum(v*v/sum(ca) for v in ca) - sum(v*v/sum(cb) for v in cb),
                     name not in preferred, not name.startswith('meaning_'), name)
            if key not in options or order < options[key][0]:
                options[key] = (order, name, a, b)
        for _, name, a, b in sorted(options.values())[:config.split_candidates]:
            left = solve(a, depth - 1, forbids_yes or name in CONTRADICTS_YES)
            if not left:
                continue
            right = solve(b, depth - 1, forbids_yes)
            for ae, (an, at) in left.items():
                for be, (bn, bt) in right.items():
                    if report['transitions'] >= config.max_transitions:
                        raise _BudgetReached
                    report['transitions'] += 1
                    add(bank, tuple(x+y for x, y in zip(ae, be)), an+bn, ('split', name, at, bt))
        return bank

    try:
        solve(full, config.max_depth, False)
    except _BudgetReached:
        report['budget_exhausted'] = True
    report['stop'] = 'bounded_search_completed' if not report['budget_exhausted'] else 'search_budget_reached'
    report['root_options'] = len(root_bank)
    if not root_bank:
        return None, report
    errors, (rules, shape) = min(root_bank.items(), key=lambda item: (item[0][0], item[1][0], item[0]))

    def materialize(node):
        if node[0] == 'leaf':
            return _leaf([r for i, r in enumerate(rows) if node[1] & (1 << i)])
        a, b = materialize(node[2]), materialize(node[3])
        return {'type': 'split', 'feature': node[1], 'true': a, 'false': b, 'support': a['support'] + b['support']}

    tree = materialize(shape)
    report['selected_errors'] = list(errors); report['selected_rules'] = rules
    policy = {'version': TREE_VERSION, 'feature_contract_ref': CONTRACT_REF,
              'limits': {**LIMITS, 'max_depth': config.max_depth, 'group_depth': min(2, config.max_depth),
                         'max_search_states': config.max_states, 'split_candidates': config.split_candidates},
              'tree': tree, 'search': {**report, 'nodes': complexity(tree)['nodes'],
              'objective': 'No local accuracy regressions; minimize total errors, then terminal rules.'},
              'training': {'source_groups': [r['source_group'] for r in rows],
                           'source_batches': [r['batch'] for r in rows],
                           'feature_ref': digest([r['features'] for r in rows]),
                           'target_ref': digest([r['reference'] for r in rows])},
              'conflicts': conflict_report([r['features'] for r in rows], [r['reference'] for r in rows], [r['source_group'] for r in rows])}
    model = describe(_refresh(policy, rows), rows, VERSION)
    if gate(model, rows, requirements, max_rules=max_rules)['status'] != 'accepted':
        raise AssertionError('Search statistics disagree with runtime local accuracy')
    return model, report


def learn(rows, seeds, *, cached=(), config=Config()):
    """Optimize four existing children, then six pairs and three root partitions.

    Every merge must remove at least one terminal rule and preserve accuracy on
    its immediate children AND all original descendants. Rejected pairs retain
    their children. Candidate caches must have exactly the current fitting scope.
    """
    validate_rows(rows)
    if len(seeds) != 4:
        raise ValueError('Four initial children required for this bounded schedule')
    seed_sources = [set(s['policy']['training']['source_groups']) for s in seeds]
    if (set().union(*seed_sources) != {r['source_group'] for r in rows}
            or sum(map(len, seed_sources)) != len(rows)):
        raise ValueError('Children must partition the training union')
    registry = {}; retained = {}; events = []; searches = []
    original = [requirement(s, rows) for s in seeds]

    def select(cohort, reqs, limit, incumbents, preferred):
        scope = {r['source_group'] for r in cohort}
        bank = [describe(m['policy'], cohort, m['initialization']) for m in list(incumbents) + list(cached)
                if set(m['policy']['training']['source_groups']) == scope
                and m['policy']['training']['feature_ref'] == digest([r['features'] for r in sorted(cohort, key=lambda r: r['source_group'])])
                and m['policy']['training']['target_ref'] == digest([r['reference'] for r in sorted(cohort, key=lambda r: r['source_group'])])]
        # Tighten accuracy first. Only a perfect incumbent may tighten the rule
        # budget: a smaller imperfect incumbent must not block an accuracy gain.
        passing = [m for m in bank if gate(m, cohort, reqs, max_rules=limit)['status'] == 'accepted']
        search_reqs = list(reqs)
        if passing:
            best = min(passing, key=rank)
            search_reqs.append(requirement(best, cohort))
            if best['metrics']['correct'] == len(cohort):
                limit = min(limit, best['complexity']['rules'])
        model, report = fit(cohort, search_reqs, max_rules=limit, config=config, preferred=preferred)
        searches.append({'sources': sorted(scope), **report})
        if model:
            passing.append(model)
        return min(passing, key=rank) if passing else None

    def node(model, mask, children, cohort):
        value = deepcopy(model); value.update(mask=mask, children=[c['node_id'] for c in children],
                                              fit_sources=sorted(r['source_group'] for r in cohort))
        value['node_id'] = digest([VERSION, mask, value['children'], model['runtime']['artifact_ref']])
        registry[value['node_id']] = value
        return value

    def cohort(mask):
        source_set = set().union(*(seed_sources[i] for i in range(4) if mask & (1 << i)))
        return sorted((r for r in rows if r['source_group'] in source_set), key=lambda r: r['source_group'])

    for i, seed in enumerate(seeds):
        part = cohort(1 << i)
        chosen = select(part, [original[i]], seed['complexity']['rules'], [seed], seed['runtime']['predicate_descriptions'])
        if chosen is None:
            raise ValueError('Initial child does not satisfy portability/local-fit contract')
        retained[1 << i] = node(chosen, 1 << i, [], part)
    optimized = [requirement(retained[1 << i], rows) for i in range(4)]

    def merge(a, b):
        left, right = retained[a], retained[b]; mask = a | b; part = cohort(mask)
        reqs = [optimized[i] for i in range(4) if mask & (1 << i)] + [requirement(c, part) for c in (left, right)]
        before_rules = sum(c['complexity']['rules'] for c in (left, right))
        chosen = select(part, reqs, before_rules - 1, [],
                        set(left['runtime']['predicate_descriptions']) | set(right['runtime']['predicate_descriptions']))
        event = {'mask': mask, 'children': [left['node_id'], right['node_id']], 'requirements': scopes(part, reqs),
                 'separate_rules': before_rules, 'status': 'rejected', 'parent': None}
        if chosen is not None:
            decision = gate(chosen, part, reqs, max_rules=before_rules-1)
            if decision['status'] != 'accepted':
                raise AssertionError('Lossy merge escaped local gate')
            parent = node(chosen, mask, [left, right], part)
            event.update(status='accepted', parent=parent['node_id'], decision=decision)
            if mask not in retained or rank(parent) < rank(retained[mask]):
                retained[mask] = parent
        events.append(event)

    for i, j in combinations(range(4), 2):
        merge(1 << i, 1 << j)
    for a, b in ((3, 12), (5, 10), (9, 6)):
        if a in retained and b in retained:
            merge(a, b)
    # Best disjoint covering forest. Its reported fit is scope-local, not a
    # prediction metric for a deployable router over unseen examples.
    def covers(mask):
        if not mask:
            yield []; return
        first = mask & -mask
        for k in sorted(retained):
            if k & first and k & mask == k:
                for tail in covers(mask ^ k):
                    yield [retained[k]] + tail
    forest = min(covers(15), key=lambda ns: (-sum(n['metrics']['correct'] for n in ns),
                                            sum(n['complexity']['rules'] for n in ns), len(ns)))
    return {'version': VERSION, 'config': asdict(config), 'root': retained.get(15),
            'forest': [n['node_id'] for n in forest], 'registry': registry, 'events': events, 'searches': searches,
            'original_requirements': original, 'optimized_requirements': optimized,
            'summary': {'original_correct': sum(q['correct'] for q in original),
                        'optimized_child_correct': sum(q['correct'] for q in optimized),
                        'forest_local_correct': sum(n['metrics']['correct'] for n in forest),
                        'total': len(rows), 'original_rules': sum(s['complexity']['rules'] for s in seeds),
                        'optimized_child_rules': sum(retained[1 << i]['complexity']['rules'] for i in range(4)),
                        'forest_rules': sum(n['complexity']['rules'] for n in forest), 'forest_size': len(forest),
                        'accepted_merges': sum(e['status'] == 'accepted' for e in events),
                        'searches': len(searches), 'states': sum(s['states'] for s in searches),
                        'budget_exhausted_searches': sum(s['budget_exhausted'] for s in searches)},
            'new_model_calls': 0, 'reserved_test_predictions': 0,
            'forest_routing': 'None. Local scope scores are training diagnostics, not combined inference.'}
