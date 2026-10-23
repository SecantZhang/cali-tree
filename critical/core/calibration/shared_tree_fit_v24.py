"""Bounded parent fitting that prefers compact, correctly shared terminal rules.

Frozen v18 safety and artifact contracts remain unchanged. This v24 search
retains sharing-aware alternatives inside each local-error frontier, rather than
only applying a sharing tie-break after the useful alternatives were discarded.
"""
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache

from .local_compression_v18 import (
    FEATURES, CONTRACT_REF, TREE_VERSION, LIMITS, CONTRADICTS_YES,
    digest, validate_rows, scopes, equality_certificate, _BudgetReached,
    _leaf, _refresh, complexity, conflict_report, describe, gate, PortableRuleExecutor,
)

VERSION = 'shared-pair-parent-fit-v24'


@dataclass(frozen=True)
class Config:
    max_depth: int = 8
    split_candidates: int = 24
    max_states: int = 80000
    max_transitions: int = 500000
    max_frontier: int = 256
    quantifier: str = 'all'
    prefer_shared: bool = True

    def __post_init__(self):
        if (any(type(getattr(self, k)) is not int or getattr(self, k) < 1 for k in
                ('max_depth', 'split_candidates', 'max_states', 'max_transitions', 'max_frontier'))
                or self.quantifier not in ('all', 'any') or type(self.prefer_shared) is not bool):
            raise ValueError('Invalid shared parent search configuration')


def sharing(model, rows):
    executor = PortableRuleExecutor(model['runtime']); leaves = {}
    for row, pred in zip(rows, executor.predict_records([r['features'] for r in rows])):
        if pred['prediction'] < 0:
            continue
        key = tuple((v['feature'], v['value']) for v in pred['trace'])
        leaf = leaves.setdefault(key, {'sources': 0, 'correct_by_batch': Counter()})
        leaf['sources'] += 1
        if pred['prediction'] == row['reference']:
            leaf['correct_by_batch'][row['batch']] += 1
    details = [{'path': [{'feature': k, 'value': v} for k, v in path], 'sources': leaf['sources'],
                'correct_by_batch': dict(sorted(leaf['correct_by_batch'].items()))} for path, leaf in sorted(leaves.items())]
    return {'shared_correct': sum(sum(d['correct_by_batch'].values()) for d in details if len(d['correct_by_batch']) >= 2),
            'cross_batch_support': sum(sum(d['correct_by_batch'].values()) - max(d['correct_by_batch'].values(), default=0) for d in details),
            'shared_rules': sum(len(d['correct_by_batch']) >= 2 for d in details), 'leaves': details,
            'definition': 'Credit only correctly predicted sources from at least two original batches in the same terminal rule.'}


def rank(model):
    s = model['sharing']
    return (-model['metrics']['correct'], model['complexity']['rules'], -s['shared_correct'],
            -s['cross_batch_support'], model['complexity']['depth'], model['runtime']['artifact_ref'])


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
    batch_masks = [sum(1 << i for i, r in enumerate(rows) if r['batch'] == b) for b in sorted({r['batch'] for r in rows})]
    instruction_masks = {}
    for i, r in enumerate(rows):
        instruction_masks[r['instruction']] = instruction_masks.get(r['instruction'], 0) | (1 << i)
    preferred = set(preferred)
    if not preferred <= set(FEATURES):
        raise ValueError('Only declared reusable predicates may be preferred')
    unique = {}; aliases = {}
    for name in sorted(FEATURES, key=lambda k: (not k.startswith('meaning_'), not k.endswith('_' + config.quantifier), k not in preferred, k)):
        mask = sum(1 << i for i, r in enumerate(rows) if r['features']['features'][name])
        if not mask or mask == full:
            continue
        key = (mask if name in CONTRADICTS_YES else min(mask, full ^ mask), name in CONTRADICTS_YES)
        unique.setdefault(key, (name, mask)); aliases.setdefault(key, []).append(name)
    report['partition_aliases'] = [{'representative': unique[k][0], 'alternatives': v} for k, v in aliases.items()]

    def supported(mask):
        return mask.bit_count() >= 2 and sum(bool(mask & m) for m in instruction_masks.values()) >= 2

    def quality(value):
        rules, shared, balance, depth, _ = value
        return (rules, -shared if config.prefer_shared else 0, -balance if config.prefer_shared else 0, depth)

    def add(bank, errors, value):
        if value[0] > max_rules or any(e > b for e, b in zip(errors, budgets)):
            return
        if errors in bank and quality(bank[errors]) <= quality(value):
            return
        if any(quality(v) <= quality(value) and all(a <= b for a, b in zip(k, errors)) for k, v in bank.items()):
            return
        for k in list(bank):
            if quality(value) <= quality(bank[k]) and all(a <= b for a, b in zip(errors, k)):
                del bank[k]
        if len(bank) >= config.max_frontier and errors not in bank:
            raise _BudgetReached
        bank[errors] = value

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
            correct_mask = mask & targets[label]
            by_batch = [(correct_mask & b).bit_count() for b in batch_masks]
            shared = sum(by_batch) if sum(v > 0 for v in by_batch) >= 2 else 0
            balance = sum(by_batch) - max(by_batch)
            add(bank, tuple((wrong & s).bit_count() for s in scope_masks), (1, shared, balance, 0, ('leaf', mask)))
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
            for ae, (an, ash, abal, ad, at) in left.items():
                for be, (bn, bsh, bbal, bd, bt) in right.items():
                    if report['transitions'] >= config.max_transitions:
                        raise _BudgetReached
                    report['transitions'] += 1
                    add(bank, tuple(x+y for x, y in zip(ae, be)), (an+bn, ash+bsh, abal+bbal, 1+max(ad,bd), ('split', name, at, bt)))
        return bank

    try:
        solve(full, config.max_depth, False)
    except _BudgetReached:
        report['budget_exhausted'] = True
    report['stop'] = 'bounded_search_completed' if not report['budget_exhausted'] else 'search_budget_reached'
    report['root_options'] = len(root_bank)
    if not root_bank:
        return None, report
    errors, value = min(root_bank.items(), key=lambda item: (item[0][0], quality(item[1]), item[0]))
    rules, shared, balance, depth, shape = value

    def materialize(node):
        if node[0] == 'leaf':
            return _leaf([r for i, r in enumerate(rows) if node[1] & (1 << i)])
        a, b = materialize(node[2]), materialize(node[3])
        return {'type': 'split', 'feature': node[1], 'true': a, 'false': b, 'support': a['support'] + b['support']}

    tree = materialize(shape)
    report['selected_errors'] = list(errors); report['selected_rules'] = rules
    report['selected_shared_correct'] = shared; report['selected_cross_batch_support'] = balance
    policy = {'version': TREE_VERSION, 'feature_contract_ref': CONTRACT_REF,
              'limits': {**LIMITS, 'max_depth': config.max_depth, 'group_depth': min(2, config.max_depth),
                         'max_search_states': config.max_states, 'split_candidates': config.split_candidates},
              'tree': tree, 'search': {**report, 'nodes': complexity(tree)['nodes'],
              'objective': 'No local regressions; total errors, rules, correctly shared support, balanced batch support, then depth.'},
              'training': {'source_groups': [r['source_group'] for r in rows],
                           'source_batches': [r['batch'] for r in rows],
                           'feature_ref': digest([r['features'] for r in rows]),
                           'target_ref': digest([r['reference'] for r in rows])},
              'conflicts': conflict_report([r['features'] for r in rows], [r['reference'] for r in rows], [r['source_group'] for r in rows])}
    model = describe(_refresh(policy, rows), rows, VERSION)
    if gate(model, rows, requirements, max_rules=max_rules)['status'] != 'accepted':
        raise AssertionError('Search statistics disagree with runtime local accuracy')
    model['sharing'] = sharing(model, rows)
    if model['sharing']['shared_correct'] != shared or model['sharing']['cross_batch_support'] != balance:
        raise AssertionError('Sharing statistics differ from runtime routing')
    return model, report

