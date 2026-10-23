"""Macro-F1 pruning of the frozen bounded semantic grower (experimental v15).

Only pruning changes relative to v14. A confusion-count frontier makes the
non-additive macro-F1 objective exact over the supported fixed-shape prunings.
Majority labels, source support, written consistency and merge gates are retained.
The module lives outside the frozen hierarchy directory so old study manifests
remain reproducible when their source inventories are verified.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

from ..decision.artifacts import digest
from .semantic_hierarchy import regularized_tree_v13 as base
from .semantic_hierarchy.supported_pruning_v14 import grown_tree
from .semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES, violations
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from .semantic_hierarchy.portable_tree_v8 import PortableSemanticTree

VERSION = 'macro-f1-semantic-pruning-v15'


def _counts(rows, label, available):
    chosen = [r for r in rows if r['features']['features']['meaning_available'] == available]
    correct = tuple(sum(r['reference'] == k and label == k for r in chosen) for k in range(3))
    predicted = tuple(len(chosen) if label == k else 0 for k in range(3))
    return correct + predicted


def _strip(tree):
    if 'feature' not in tree:
        return {'prediction': tree['prediction']}
    return {'feature': tree['feature'], 'true': _strip(tree['true']), 'false': _strip(tree['false'])}


def prune_frontier(tree, rows, penalty, *, target_support=None, max_states=4096, max_transitions=200000):
    """Select regularized macro-F1 using sufficient statistics, never labels from outside rows.

    A state includes correct/predicted counts separately for available and missing
    interpretations. This reproduces the portable runtime's global interpretation
    requirement, including when pruning removes the last semantic predicate.
    Objective-equivalent states share work, not a claim of semantic equivalence.
    Exceeding a declared bound fails explicitly; no heuristic truncation is hidden.
    """
    if not rows or penalty < 0 or max_states < 1 or max_transitions < 1:
        raise ValueError('Valid pruning rows, penalty and bounds required')
    support = tuple(sum(r['reference'] == k for r in rows) for k in range(3)) if target_support is None else tuple(target_support)
    observed = tuple(sum(r['reference'] == k for r in rows) for k in range(3))
    if len(support) != 3 or any(type(n) is not int or n < observed[k] for k, n in enumerate(support)):
        raise ValueError('Target support must retain every observed reference')
    total = sum(support); cost = Fraction(str(penalty)) / total
    visited = transitions = peak = 0

    def solve(node, cohort, forbids_yes=False):
        nonlocal visited, transitions, peak
        visited += 1
        leaf = base._leaf(cohort); options = {}
        if not (forbids_yes and leaf['prediction'] == 2):
            key = (False,) + _counts(cohort, leaf['prediction'], True) + _counts(cohort, leaf['prediction'], False)
            options[key] = (1, leaf)
        if 'feature' in node:
            feature = node['feature']
            parts = [[r for r in cohort if r['features']['features'][feature] == value] for value in (True, False)]
            left = solve(node['true'], parts[0], forbids_yes or feature in CONTRADICTS_YES)
            right = solve(node['false'], parts[1], forbids_yes)
            for ak, (an, at) in left.items():
                for bk, (bn, bt) in right.items():
                    transitions += 1
                    if transitions > max_transitions:
                        raise RuntimeError('Declared macro-pruning transition budget exhausted')
                    requires = ak[0] or bk[0] or feature.startswith('meaning_') and feature != 'meaning_available'
                    key = (bool(requires),) + tuple(a + b for a, b in zip(ak[1:], bk[1:]))
                    candidate = {'type': 'split', 'feature': feature, 'support': len(cohort), 'true': at, 'false': bt}
                    value = (an + bn, candidate)
                    if key not in options or (value[0], digest(_strip(value[1]))) < (options[key][0], digest(_strip(options[key][1]))):
                        options[key] = value
                    if len(options) > max_states:
                        raise RuntimeError('Declared macro-pruning state budget exhausted')
        peak = max(peak, len(options))
        return options

    options = solve(tree, rows)
    required = sum(1 << k for k, n in enumerate(support) if n >= 2)
    ranked = []
    for state, (rules, candidate) in options.items():
        counts = state[1:7] if state[0] else tuple(a + b for a, b in zip(state[1:7], state[7:13]))
        correct, predicted = counts[:3], counts[3:]
        macro = sum((Fraction(2 * correct[k], support[k] + predicted[k]) if support[k] + predicted[k] else Fraction(0)) for k in range(3)) / 3
        recalls = [Fraction(correct[k], support[k]) for k in range(3) if support[k]]
        coverage = sum(1 << k for k in range(3) if correct[k])
        key = (-(coverage & required).bit_count(), -macro + cost * rules, -min(recalls), -sum(correct), rules, digest(_strip(candidate)))
        ranked.append((key, candidate, {'class_mask': coverage, 'correct': list(correct), 'predicted': list(predicted),
            'macro_f1': float(macro), 'rules': rules, 'objective': float(-macro + cost * rules)}))
    _, selected, measured = min(ranked, key=lambda row: row[0])
    return selected, {'version': VERSION, 'target_support': list(support), 'states_visited': visited,
        'combination_transitions': transitions, 'peak_states': peak, 'root_states': len(options),
        'max_states': max_states, 'max_transitions': max_transitions, 'budget_exhausted': False,
        'required_class_mask': required, 'all_supported_classes_preserved': measured['class_mask'] & required == required,
        'selected': measured, 'objective': 'Preserve supported classes when possible; maximize macro-F1 minus penalty*rules/total sources.',
        'equivalence': 'Only objective sufficient statistics are coalesced; no semantic-equivalence claim.'}


class MacroFits(base.TreeFits):
    def __init__(self, max_fits=128):
        super().__init__(max_fits)
        self.macro_cache = {}
        self.stats.update(pruning_states=0, pruning_transitions=0)

    def fit(self, rows, config, *, allowed=None, shape=None):
        rows = sorted(rows, key=lambda r: r['source_group'])
        draft = super().fit(rows, replace(config, leaf_penalty=0), allowed=allowed, shape=shape)
        key = digest([VERSION, draft['fit_ref'], config.leaf_penalty])
        if key in self.macro_cache:
            return deepcopy(self.macro_cache[key])
        selected = [r for r in rows if r['features'] is not None]
        tree, report = prune_frontier(grown_tree(draft, rows), selected, config.leaf_penalty,
            target_support=[sum(r['reference'] == k for r in rows) for k in range(3)])
        assert not violations(tree)
        policy = deepcopy(draft['policy']); policy.pop('artifact_ref'); policy['tree'] = tree
        policy['search'].update(version=VERSION, fit_ref=key, pruning=report, pruned_complexity=base.complexity(tree),
            objective='Fixed-shape macro-F1 minus rule cost, subject to supported-class coverage and written consistency')
        policy['search']['config']['leaf_penalty'] = config.leaf_penalty
        policy['artifact_ref'] = digest(policy)
        runtime = PortableRuleExecutor.from_training_policy(policy).metadata()
        predictions = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
        measured = base.metrics([p['prediction'] for p in predictions], [r['reference'] for r in rows])
        if abs(measured['macro_f1'] - report['selected']['macro_f1']) > 1e-12:
            raise AssertionError('Pruning statistics disagree with actual portable inference')
        policy.pop('artifact_ref'); policy['training']['metrics'] = measured; policy['artifact_ref'] = digest(policy)
        PortableSemanticTree.restore(policy)
        result = {**draft, 'policy': policy, 'runtime': runtime, 'metrics': measured, 'complexity': base.complexity(tree), 'fit_ref': key}
        self.stats['pruning_states'] += report['states_visited']
        self.stats['pruning_transitions'] += report['combination_transitions']
        self.macro_cache[key] = deepcopy(result)
        return result


def learn(rows, config, *, mode='merge', fits=None):
    return base.learn(rows, config, mode=mode, fits=fits if fits is not None else MacroFits())
