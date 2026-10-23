"""Bounded semantic trees, explicit predicate alternatives and parent compression.

Experimental opt-in learner. Frozen v8-v12 fitting and deployment contracts are
unchanged. Targets are always original references; child predictions are never
training labels. No model calls, evaluation records, or dataset loading here.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from itertools import combinations, product

from ...decision.artifacts import digest
from .portable_features_v8 import FEATURES, CONTRACT_REF
from .portable_tree_v8 import VERSION as POLICY_VERSION, LIMITS, PortableSemanticTree, metrics
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_review_v8 import violations
from .union_learning_v10 import validate_rows
from .union_merges_v10 import gate as legacy_gate, predicates
from .union_groups_v10 import original, validate_partition
from .hierarchy_fit_v9 import _leaf, complexity

VERSION = 'regularized-semantic-compression-v13'
ANCHORS = tuple(k for k in FEATURES if k.startswith(('meaning_progress_', 'meaning_endpoint_gap_',
    'meaning_identity_materiality_', 'meaning_collateral_materiality_', 'meaning_evidence_consistency_')))


@dataclass(frozen=True)
class Config:
    max_depth: int = 3
    min_sources: int = 3
    leaf_penalty: float = 1.0
    grammar: str = 'meaning'
    quantifier: str = 'all'
    compression: float = 0.2
    gate_mode: str = 'strict'

    def __post_init__(self):
        if (type(self.max_depth) is not int or not 1 <= self.max_depth <= 6
                or type(self.min_sources) is not int or self.min_sources < 2
                or not 0 <= self.leaf_penalty <= 48
                or self.grammar not in ('meaning', 'global', 'full')
                or self.quantifier not in ('all', 'any')
                or not 0 < self.compression < 1 or self.gate_mode not in ('strict', 'regularized')):
            raise ValueError('Invalid v13 configuration')

    @property
    def ref(self):
        return digest([VERSION, asdict(self)])


def vocabulary(config):
    meaning = [k for k in FEATURES if k.startswith('meaning_') and k != 'meaning_available']
    if config.grammar == 'meaning':
        return meaning
    if config.grammar == 'full':
        return list(FEATURES)
    return meaning + [k for k in FEATURES if any(k.startswith(role + '_all_') for role in (
        'outcome', 'identity', 'preservation', 'intermediate', 'collateral_disappearance', 'collateral_deformation'))]


def semantic_order(feature, quantifier):
    # A declared semantic prior, not an assertion that correlated columns are
    # synonymous. Both quantifier preferences remain separate procedures in CV.
    families = ('meaning_progress_', 'meaning_endpoint_gap_', 'meaning_identity_materiality_',
                'meaning_collateral_materiality_', 'meaning_evidence_consistency_', 'meaning_')
    family = next((i for i, prefix in enumerate(families) if feature.startswith(prefix)), len(families))
    return (family, not feature.endswith('_' + quantifier), feature)


def predict(model, rows):
    return PortableRuleExecutor(model['runtime']).predict_records([r['features'] for r in rows])


def _supported(rows, minimum):
    return len(rows) >= minimum and len({r['instruction'] for r in rows}) >= 2


def _errors(tree):
    if 'feature' not in tree:
        return tree['support'] - max(tree['counts'])
    return _errors(tree['true']) + _errors(tree['false'])


def _prune(tree, rows, penalty):
    """Exact bottom-up errors + leaf-cost pruning of one fixed grown shape."""
    leaf = _leaf(rows)
    if 'feature' not in tree:
        return leaf
    name = tree['feature']
    parts = [[r for r in rows if r['features']['features'][name] == value] for value in (True, False)]
    a, b = [_prune(tree[side], part, penalty) for side, part in zip(('true', 'false'), parts)]
    candidate = {'type': 'split', 'feature': name, 'true': a, 'false': b, 'support': len(rows)}
    leaf_cost = Fraction(_errors(leaf)) + penalty
    branch_cost = Fraction(_errors(candidate)) + penalty * complexity(candidate)['rules']
    return leaf if leaf_cost <= branch_cost else candidate


def _remove_written_contradictions(tree, rows):
    """Collapse the nearest offending branch; retain and measure all fit loss."""
    if 'feature' not in tree:
        return tree
    name = tree['feature']
    parts = [[r for r in rows if r['features']['features'][name] == value] for value in (True, False)]
    for side, part in zip(('true', 'false'), parts):
        tree[side] = _remove_written_contradictions(tree[side], part)
    return _leaf(rows) if violations(tree) else tree


class TreeFits:
    """Per-build content cache, bounded greedy growth, and counted search work.

    Every predicate identity is retained. Only calculation of equal partition
    scores is shared. A different semantic/quantifier preference is a different
    fit, so any/all alternatives cannot disappear via a training-mask hash.
    """
    def __init__(self, max_fits=2048):
        if type(max_fits) is not int or max_fits < 1:
            raise ValueError('Positive fit budget required')
        self.max_fits = max_fits
        self.cache = {}
        self.stats = {'fits': 0, 'cache_hits': 0, 'partition_scores': 0, 'predicate_tests': 0}

    def fit(self, rows, config, *, allowed=None, shape=None):
        rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
        allowed = vocabulary(config) if allowed is None else sorted(set(allowed))
        if not set(allowed) <= set(vocabulary(config)):
            raise ValueError('Undeclared predicate vocabulary')
        if shape is not None and not predicates(shape) <= set(allowed):
            raise ValueError('Warm tree uses a predicate outside its declared vocabulary')
        key = digest([VERSION, rows, asdict(config), sorted(allowed), shape])
        if key in self.cache:
            self.stats['cache_hits'] += 1
            return deepcopy(self.cache[key])
        if self.stats['fits'] >= self.max_fits:
            raise RuntimeError('Declared v13 fit budget exhausted')
        self.stats['fits'] += 1
        selected = [r for r in rows if r['features'] is not None]
        if not _supported(selected, config.min_sources):
            raise ValueError('Insufficient distinct-source/instruction support')
        counters = {'partition_scores': 0, 'predicate_tests': 0}
        alternatives = []

        def grow(cohort, depth, warm=None, path=()):
            leaf = _leaf(cohort)
            if depth == 0 or max(leaf['counts']) == len(cohort):
                return leaf
            if warm is not None:
                if 'feature' not in warm:
                    return leaf
                names = [warm['feature']]
            else:
                names = sorted(allowed, key=lambda k: semantic_order(k, config.quantifier))
            scored = {}; choices = []
            for name in names:
                counters['predicate_tests'] += 1
                mask = tuple(i for i, r in enumerate(cohort) if r['features']['features'][name])
                if mask not in scored:
                    indices = set(mask)
                    parts = [[r for i, r in enumerate(cohort) if (i in indices) == value] for value in (True, False)]
                    if not all(_supported(p, config.min_sources) for p in parts):
                        scored[mask] = None
                    else:
                        counts = [[sum(r['reference'] == k for r in part) for k in (0, 1, 2)] for part in parts]
                        impurity = sum(Fraction(sum(v * v for v in c), len(part)) for c, part in zip(counts, parts))
                        scored[mask] = (impurity, parts)
                        counters['partition_scores'] += 1
                if scored[mask] is not None:
                    impurity, parts = scored[mask]
                    choices.append(((-impurity, semantic_order(name, config.quantifier)), name, mask, parts))
            if not choices:
                return leaf
            _, name, mask, parts = min(choices, key=lambda x: x[0])
            base = Fraction(sum(v * v for v in leaf['counts']), len(cohort))
            if warm is None and scored[mask][0] <= base:
                return leaf
            aliases = [{'feature': other, 'complement': other_mask != mask} for _, other, other_mask, _ in choices
                       if other != name and (other_mask == mask or set(other_mask) == set(range(len(cohort))) - set(mask))]
            alternatives.append({'path': list(path), 'selected': name, 'training_equivalent_alternatives': aliases,
                                 'semantic_equivalence_claim': False})
            a, b = [grow(part, depth - 1, warm[side] if warm is not None else None, path + (side,))
                    for side, part in zip(('true', 'false'), parts)]
            return {'type': 'split', 'feature': name, 'true': a, 'false': b, 'support': len(cohort)}

        grown = grow(selected, config.max_depth, shape)
        tree = _prune(grown, selected, Fraction(str(config.leaf_penalty)))
        tree = _remove_written_contradictions(tree, selected)
        limits = {**LIMITS, 'max_depth': max(2, config.max_depth), 'min_leaf_sources': config.min_sources}
        artifact = {'version': POLICY_VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': limits,
            'tree': tree, 'search': {'version': VERSION, 'config': asdict(config), 'fit_ref': key,
                'allowed_predicates': sorted(allowed), 'alternatives': alternatives, **counters,
                'grown_complexity': complexity(grown), 'pruned_complexity': complexity(tree),
                'objective': 'Greedy impurity growth, exact fixed-shape error-plus-rule-cost pruning; no optimality claim'},
            'training': {'source_groups': [r['source_group'] for r in rows],
                'source_batches': [r['batch'] for r in rows], 'feature_ref': digest([r['features'] for r in rows]),
                'target_ref': digest([r['reference'] for r in rows])},
            'conflicts': {'missing_sources': [r['source_group'] for r in rows if r['features'] is None]}}
        artifact['artifact_ref'] = digest(artifact)
        runtime = PortableRuleExecutor.from_training_policy(artifact).metadata()
        ps = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
        measured = metrics([p['prediction'] for p in ps], [r['reference'] for r in rows])
        artifact.pop('artifact_ref'); artifact['training']['metrics'] = measured; artifact['artifact_ref'] = digest(artifact)
        PortableSemanticTree.restore(artifact)
        result = {'policy': artifact, 'runtime': runtime, 'metrics': measured, 'complexity': complexity(tree),
                  'portable': not violations(tree), 'fit_sources': [r['source_group'] for r in rows],
                  'initialization': 'child_shape' if shape is not None else 'greedy_semantic', 'fit_ref': key}
        self.cache[key] = deepcopy(result)
        for k, value in counters.items():
            self.stats[k] += value
        return result


def rank(model, config):
    m = model['metrics']
    return (Fraction(m['total'] - m['correct']) + Fraction(str(config.leaf_penalty)) * model['complexity']['rules'],
            -m['macro_f1'], model['complexity']['rules'], model['runtime']['artifact_ref'])


def compression_gate(candidate, children, rows, config):
    old = legacy_gate(candidate, children, rows)
    separate = sum(c['complexity']['rules'] for c in children)
    reduction = 1 - candidate['complexity']['rules'] / separate
    reasons = list(old['reasons'])
    if config.gate_mode == 'regularized':
        # Declared experimental change, never reported as passing the old gate:
        # use a complexity-adjusted loss budget, not a 90% fitting target or a
        # discrete per-child error allowance. Whole-procedure CV is still needed.
        reasons = [r for r in reasons if r != 'union_accuracy_not_strictly_above_90_percent'
                   and not r.startswith('child_retention_regression:')]
        before_errors = sum(c['metrics']['total'] - c['metrics']['correct'] for c in children)
        after_errors = candidate['metrics']['total'] - candidate['metrics']['correct']
        if after_errors - before_errors > config.leaf_penalty * (separate - candidate['complexity']['rules']) + 1e-12:
            reasons.append('regularized_loss_regression')
    if reduction + 1e-12 < config.compression:
        reasons.append('insufficient_rule_compression')
    return {'status': 'accepted' if not reasons else 'rejected', 'reasons': reasons,
            'compression': reduction, 'legacy_gate': old, 'gate_mode': config.gate_mode}


def learn(rows, config, *, mode='merge', fits=None):
    """Four-seed, bounded pair search; rejected branches stay in the forest.

    A missing complete root is explicit. This function does not substitute a
    direct model and call it a successful merge.
    """
    if mode not in ('merge', 'direct', 'merge_challenger'):
        raise ValueError('Unknown v13 learning procedure')
    rows = sorted(rows, key=lambda r: r['source_group']); validate_rows(rows)
    fits = fits if fits is not None else TreeFits()
    before = dict(fits.stats)
    if mode == 'direct':
        root = fits.fit(rows, config)
        return {'root': root, 'nodes': [], 'proposals': [], 'complete': True,
                'work': {k: fits.stats[k] - before[k] for k in before}, 'mode': mode}
    groups = original(rows); validate_partition(groups, rows)
    if len(groups) != 4:
        raise ValueError('The v13 experiment requires four original training groups')
    nodes = []; seeds = []; proposals = []; retained = {}
    def node(candidate, children):
        value = deepcopy(candidate)
        value['children'] = [c['node_id'] for c in children]
        value['node_id'] = digest([VERSION, value['fit_ref'], value['children']])
        nodes.append(value)
        return value
    by_source = {r['source_group']: r for r in rows}
    for i, sources in enumerate(groups):
        cohort = [by_source[s] for s in sources]
        # Specialize small children before asking the parent to compress them.
        # Their semantic vocabulary and quantifier prior remain the same.
        seed_config = replace(config, max_depth=6, min_sources=2, leaf_penalty=0)
        seed = node(fits.fit(cohort, seed_config), [])
        seeds.append(seed); retained[1 << i] = [seed]

    def offer_pairs(pairs):
        options = []
        for a, b in pairs:
            pair = (a['node_id'], b['node_id'])
            children = [a, b]; sources = sorted(set(a['fit_sources']) | set(b['fit_sources']))
            cohort = [by_source[s] for s in sources]
            inherited = set().union(*(predicates(c['runtime']['tree']) for c in children))
            # Keep same-mask semantic alternatives named by the child learner.
            for child in children:
                for group in child['policy']['search']['alternatives']:
                    if group['selected'] in inherited:
                        inherited.update(v['feature'] for v in group['training_equivalent_alternatives'])
            allowed = (inherited | set(ANCHORS)) & set(vocabulary(config))
            bank = [fits.fit(cohort, config, allowed=allowed)]
            for child in children:
                bank.append(fits.fit(cohort, config, allowed=allowed, shape=child['runtime']['tree']))
            if mode == 'merge_challenger':
                bank.append(fits.fit(cohort, config))
            unique = {c['runtime']['artifact_ref']: c for c in bank}
            tested = [(c, compression_gate(c, children, cohort, config)) for c in unique.values()]
            accepted = [(c, g) for c, g in tested if g['status'] == 'accepted']
            proposals.append({'children': list(pair), 'sources': sources,
                'evaluations': [{'fit_ref': c['fit_ref'], 'runtime_ref': c['runtime']['artifact_ref'],
                    'metrics': c['metrics'], 'complexity': c['complexity'], 'decision': g} for c, g in tested]})
            for candidate, decision in accepted:
                parent = node(candidate, children); parent['acceptance'] = decision
                options.append(parent)
        unique = {}
        for parent in sorted(options, key=lambda n: (rank(n, config), n['node_id'])):
            unique.setdefault(parent['runtime']['artifact_ref'], parent)
        return list(unique.values())[:2]

    # Six first-level pairs and at most twelve root pairs. Retaining two
    # distinct parent policies avoids making an irreversible greedy pairing.
    for a, b in combinations(range(4), 2):
        retained[(1 << a) | (1 << b)] = offer_pairs([(seeds[a], seeds[b])])
    root_pairs = []
    for partner in (1, 2, 3):
        left = 1 | (1 << partner); right = 15 ^ left
        root_pairs.extend(product(retained[left], retained[right]))
    roots = offer_pairs(root_pairs)
    root = roots[0] if roots else None
    return {'root': root, 'nodes': nodes, 'proposals': proposals, 'complete': root is not None,
            'forest': [root['node_id']] if root else [n['node_id'] for n in seeds],
            'root_candidates': [n['node_id'] for n in roots], 'mode': mode,
            'work': {k: fits.stats[k] - before[k] for k in before}}
