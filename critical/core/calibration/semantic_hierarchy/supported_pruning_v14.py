"""Class-preserving pruning of v13's bounded, semantically explicit child trees.

The grower, source scopes, semantic vocabulary, merge search and acceptance gates
are unchanged. A small dynamic program keeps alternatives by correctly served
class set, instead of greedily erasing a rare class to save one rule. Original
majority-label semantics and written-contradiction constraints are preserved.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

from ...decision.artifacts import digest
from . import regularized_tree_v13 as base
from .portable_review_v8 import CONTRADICTS_YES, violations
from .portable_runtime_v8 import PortableRuleExecutor
from .portable_tree_v8 import PortableSemanticTree

VERSION = 'supported-semantic-pruning-v14'


def prune_frontier(tree, rows, penalty):
    """Best fixed-shape pruning for each class-coverage mask (at most eight).

    A class contributes only if the retained majority leaf correctly recognizes
    at least one original reference of that class. This is a fitting guard, not
    a generalization claim. Missing evidence cannot manufacture class support.
    """
    cost = Fraction(str(penalty)); states = 0

    def solve(node, cohort, forbids_yes=False):
        nonlocal states
        states += 1
        leaf = base._leaf(cohort)
        options = {}
        if not (forbids_yes and leaf['prediction'] == 2):
            errors = leaf['support'] - max(leaf['counts'])
            options[1 << leaf['prediction']] = (Fraction(errors) + cost, errors, 1, leaf)
        if 'feature' in node:
            feature = node['feature']
            parts = [[r for r in cohort if r['features']['features'][feature] == value] for value in (True, False)]
            a = solve(node['true'], parts[0], forbids_yes or feature in CONTRADICTS_YES)
            b = solve(node['false'], parts[1], forbids_yes)
            for amask, av in a.items():
                for bmask, bv in b.items():
                    mask = amask | bmask
                    candidate = (av[0] + bv[0], av[1] + bv[1], av[2] + bv[2],
                        {'type': 'split', 'feature': feature, 'support': len(cohort), 'true': av[3], 'false': bv[3]})
                    if mask not in options or candidate[:3] < options[mask][:3]:
                        options[mask] = candidate
        return options

    options = solve(tree, rows)
    required = sum(1 << k for k in (0, 1, 2) if sum(r['reference'] == k for r in rows) >= 2)
    eligible = {mask: value for mask, value in options.items() if mask & required == required}
    if not eligible:
        # Preserve the best achievable coverage and disclose infeasibility. The
        # parent gate still rejects supported-class collapse; no guard is waived.
        best = max((mask & required).bit_count() for mask in options)
        eligible = {mask: value for mask, value in options.items() if (mask & required).bit_count() == best}
    mask, value = min(eligible.items(), key=lambda p: (*p[1][:3], p[0]))
    return value[3], {'version': VERSION, 'states': states, 'required_class_mask': required,
        'selected_class_mask': mask, 'all_supported_classes_preserved': mask & required == required,
        'frontier': [{'class_mask': m, 'errors': v[1], 'rules': v[2], 'objective': float(v[0])}
                     for m, v in sorted(options.items())]}


def grown_tree(model, rows):
    """Reconstruct the recorded grower, including branches v13 pruned away."""
    choices = {tuple(g['path']): g['selected'] for g in model['policy']['search']['alternatives']}

    def restore(path, selected):
        if path not in choices:
            return base._leaf(selected)
        feature = choices[path]
        parts = [[r for r in selected if r['features']['features'][feature] == value] for value in (True, False)]
        if not all(parts):
            raise ValueError('Recorded growth path is not bound to its fitting cohort')
        return {'type': 'split', 'feature': feature, 'support': len(selected),
            'true': restore(path + ('true',), parts[0]), 'false': restore(path + ('false',), parts[1])}
    return restore((), [r for r in rows if r['features'] is not None])


class SupportedFits(base.TreeFits):
    def __init__(self, max_fits=128):
        super().__init__(max_fits)
        self.supported_cache = {}
        self.stats['pruning_states'] = 0

    def fit(self, rows, config, *, allowed=None, shape=None):
        rows = sorted(rows, key=lambda r: r['source_group'])
        # The base caches growth independently of the pruning penalty. Its
        # alias records retain the complete grown shape even after pruning.
        draft = super().fit(rows, replace(config, leaf_penalty=0), allowed=allowed, shape=shape)
        key = digest([VERSION, draft['fit_ref'], config.leaf_penalty])
        if key in self.supported_cache:
            return deepcopy(self.supported_cache[key])
        selected = [r for r in rows if r['features'] is not None]
        tree, report = prune_frontier(grown_tree(draft, rows), selected, config.leaf_penalty)
        assert not violations(tree)
        policy = deepcopy(draft['policy']); policy.pop('artifact_ref')
        policy['tree'] = tree
        policy['search'].update(version=VERSION, fit_ref=key, pruning=report,
            pruned_complexity=base.complexity(tree),
            objective='Fixed-shape error-plus-rule-cost optimum subject to supported-class coverage and written consistency')
        policy['search']['config']['leaf_penalty'] = config.leaf_penalty
        policy['artifact_ref'] = digest(policy)
        runtime = PortableRuleExecutor.from_training_policy(policy).metadata()
        ps = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
        measured = base.metrics([p['prediction'] for p in ps], [r['reference'] for r in rows])
        policy.pop('artifact_ref'); policy['training']['metrics'] = measured; policy['artifact_ref'] = digest(policy)
        PortableSemanticTree.restore(policy)
        result = {**draft, 'policy': policy, 'runtime': runtime, 'metrics': measured,
                  'complexity': base.complexity(tree), 'fit_ref': key}
        self.stats['pruning_states'] += report['states']
        self.supported_cache[key] = deepcopy(result)
        return result


def learn(rows, config, *, mode='merge', fits=None):
    return base.learn(rows, config, mode=mode, fits=fits if fits is not None else SupportedFits())
