"""Semantic candidate scheduling; parent fitting and runtime routing stay frozen.

Profiles use correct local training support, structural task contracts, shallow
predicate families and predictions. No development probes enter pair ranking.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations

from . import pairwise_merge_v24 as base
from .pairwise_merge_v24 import (
    Config, asdict, replace, local, learner, digest, expert_artifacts, complexity,
    proposal_rank, requirements, routing_regressions, rebuild_gate, route_support,
)
from ..optimization.prompt.calitree.task_coverage import task_scope

VERSION = 'semantic-pair-scheduling-v25'


def task_tokens(program):
    scope = task_scope(program)
    return tuple(sorted(f'outcome:{kind}:{state}' for kind, state in scope['outcomes']))


def predicate_profile(tree, depth=0):
    """Top two split levels, weighting the root more than its children."""
    counts = Counter()
    if depth >= 2 or 'feature' not in tree:
        return counts
    name = tree['feature']
    for suffix in ('_all', '_any'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    if name != 'meaning_available' and not name.startswith('requires_'):
        counts[name] += Fraction(1, 2 ** depth)
    for branch in ('true', 'false'):
        counts.update(predicate_profile(tree[branch], depth + 1))
    return counts


def normalized(counts):
    total = sum(counts.values())
    return {k: Fraction(v, total) for k, v in counts.items()} if total else {}


def overlap(left, right):
    keys = set(left) | set(right)
    denominator = sum(max(left.get(k, 0), right.get(k, 0)) for k in keys)
    return sum(min(left.get(k, 0), right.get(k, 0)) for k in keys) / denominator if denominator else Fraction(0)


def profiles(models, rows, programs):
    """Build supported task distributions from each child's own local scope."""
    local.validate_rows(rows)
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Every local row requires a compiled instruction')
    for row in rows:
        if programs[row['source_group']]['instruction'] != row['instruction']:
            raise ValueError('Compiled instruction mismatch')
    result = {}
    for ref, model in sorted(models.items()):
        sources = set(model['policy']['training']['source_groups'])
        selected = [r for r in rows if r['source_group'] in sources]
        if {r['source_group'] for r in selected} != sources:
            raise ValueError('Expert scope outside profile pool')
        executor = local.PortableRuleExecutor(model['runtime'])
        predictions = executor.predict_records([r['features'] for r in selected])
        counts = Counter(); supported = 0
        for row, decision in zip(selected, predictions):
            if decision['prediction'] == row['reference']:
                counts.update(task_tokens(programs[row['source_group']]))
                supported += 1
        result[ref] = {'tasks': normalized(counts),
                       'predicates': normalized(predicate_profile(model['runtime']['tree'])),
                       'supported_rows': supported}
    return result


def ordered_pairs(models, rows, programs, ordering='semantic'):
    if ordering not in ('semantic', 'artifact_id'):
        raise ValueError('Unknown pair ordering')
    ps = profiles(models, rows, programs)
    decisions = {ref: local.PortableRuleExecutor(m['runtime']).predict_records([r['features'] for r in rows])
                 for ref, m in models.items()}
    pairs = []
    for refs in combinations(sorted(models), 2):
        a, b = (ps[ref] for ref in refs)
        common = set(a['tasks']) & set(b['tasks'])
        union = set().union(*(set(models[ref]['policy']['training']['source_groups']) for ref in refs))
        eligible = [i for i, row in enumerate(rows) if row['source_group'] in union
                    and common.intersection(task_tokens(programs[row['source_group']]))]
        agreed = sum(decisions[refs[0]][i]['prediction'] == decisions[refs[1]][i]['prediction'] for i in eligible)
        agreement = Fraction(agreed, len(eligible)) if eligible else Fraction(0)
        similarity = overlap(a['tasks'], b['tasks'])
        predicates = overlap(a['predicates'], b['predicates'])
        pairs.append(((-similarity, -agreement, -predicates, refs) if ordering == 'semantic' else (refs,),
                      {'children': list(refs), 'task_overlap': float(similarity),
                       'agreement': float(agreement), 'agreement_support': len(eligible),
                       'shallow_predicate_overlap': float(predicates)}))
    ordered = [entry for _, entry in sorted(pairs)]
    exported = {ref: {'supported_rows': p['supported_rows'],
                     'tasks': {k: float(v) for k, v in sorted(p['tasks'].items())},
                     'predicates': {k: float(v) for k, v in sorted(p['predicates'].items())}}
                for ref, p in ps.items()}
    return ordered, exported


def parent_candidates(children, rows, fit_config, cache, counters, config, fitter=learner.fit):
    source_set = set().union(*(set(c['policy']['training']['source_groups']) for c in children))
    selected = sorted((r for r in rows if r['source_group'] in source_set), key=lambda r: r['source_group'])
    reqs = requirements(children, selected)
    max_rules = sum(c['complexity']['rules'] for c in children) - 1
    bank = []; fits = []
    # A parent-shaped existing expert can subsume a contained child if all
    # per-child and original-batch floors still hold on the exact union.
    for child in children:
        if set(child['policy']['training']['source_groups']) == source_set:
            candidate = local.describe(child['policy'], selected, 'existing_union_expert')
            candidate['sharing'] = learner.sharing(candidate, selected); bank.append(candidate)
    preferred = set().union(*(set(c['runtime']['predicate_descriptions']) for c in children))
    for quantifier in ('all', 'any'):
        profile = replace(fit_config, quantifier=quantifier)
        key = digest([VERSION, selected, reqs, max_rules, asdict(profile), sorted(preferred)])
        if key not in cache:
            if counters['pair_fits'] >= config.max_pair_fits:
                fits.append({'fit_ref': key, 'skipped': 'pair_fit_budget'}); continue
            value, report = fitter(selected, reqs, max_rules=max_rules, config=profile, preferred=preferred)
            cache[key] = (deepcopy(value), deepcopy(report)); counters['pair_fits'] += 1
        else:
            counters['pair_fit_cache_hits'] += 1
        candidate, report = deepcopy(cache[key]); fits.append({'fit_ref': key, 'report': report})
        if candidate is not None:
            bank.append(candidate)
    unique = {}
    for candidate in sorted(bank, key=learner.rank):
        decision = local.gate(candidate, selected, reqs, max_rules=max_rules)
        if decision['status'] != 'accepted':
            continue
        candidate['fit_sources'] = sorted(source_set)
        candidate['preserved_requirements'] = reqs
        candidate['pairwise_lineage'] = {'children': [c['runtime']['artifact_ref'] for c in children],
                                         'child_retention': decision, 'original_targets': True}
        unique.setdefault(candidate['runtime']['artifact_ref'], candidate)
    return list(unique.values())[:config.max_parent_candidates], fits


def develop(models, rows, programs, frozen_gate, probes, *, config=Config(), fit_config=learner.Config(), emit=None, ordering='semantic', fitter=learner.fit):
    """Bounded pairwise rounds; publish a parent only after full routing checks."""
    local.validate_rows(rows)
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Every local row requires its compiled instruction')
    bank = {m['runtime']['artifact_ref']: deepcopy(m) for m in models}
    if set(bank) != set(expert_artifacts(frozen_gate)):
        raise ValueError('Starting models must be exactly the deployed expert bank')
    for ref, model in bank.items():
        if model['runtime'] != expert_artifacts(frozen_gate)[ref]:
            raise ValueError('Changed starting expert runtime')
    initial = complexity(frozen_gate); current = frozen_gate; trials = []; accepted = []; cache = {}; schedules = []
    counters = {'pair_fits': 0, 'pair_fit_cache_hits': 0, 'gate_rebuilds': 0}
    emit = emit or (lambda kind, value: None)
    for round_index in range(config.max_rounds):
        winners = []
        pairs, ps = ordered_pairs(bank, rows, programs, ordering)
        schedules.append({'round': round_index, 'profiles': ps, 'pairs': pairs})
        for pair in pairs:
            refs = pair['children']
            children = [bank[k] for k in refs]
            candidates, fits = parent_candidates(children, rows, fit_config, cache, counters, config, fitter)
            proposal = {'round': round_index, 'children': list(refs), 'fits': fits, 'candidate_count': len(candidates)}
            emit('pair', proposal)
            if not candidates:
                trials.append({**proposal, 'status': 'no_accuracy_preserving_compact_parent'}); continue
            for parent in candidates:
                if counters['gate_rebuilds'] >= config.max_gate_rebuilds:
                    trials.append({**proposal, 'status': 'gate_rebuild_budget'}); break
                parent_ref = parent['runtime']['artifact_ref']
                proposed = {k: v for k, v in bank.items() if k not in refs}; proposed[parent_ref] = parent
                candidate_gate, gate_fit = rebuild_gate(list(proposed.values()), rows, programs, current)
                counters['gate_rebuilds'] += 1
                routing_before_support = routing_regressions(frozen_gate, candidate_gate, probes)
                preserved, preservation = route_support.preserve_routes(frozen_gate, candidate_gate, probes)
                if preserved is not None:
                    candidate_gate = preserved
                before, after = complexity(current), complexity(candidate_gate)
                routing = routing_regressions(frozen_gate, candidate_gate, probes)
                reasons = []
                if after['experts'] >= before['experts'] or after['terminal_rules'] >= before['terminal_rules']:
                    reasons.append('no_deployed_expert_and_rule_compression')
                if parent_ref not in expert_artifacts(candidate_gate):
                    reasons.append('parent_not_used_by_rebuilt_gate')
                if not routing['passed']:
                    reasons.append('routing_regression')
                trial = {**proposal, 'parent': parent, 'gate': candidate_gate.export(), 'gate_fit': gate_fit,
                         'routing_before_support': routing_before_support, 'route_support_fit': preservation,
                         'before': before, 'after': after, 'routing': routing,
                         'status': 'qualified' if not reasons else 'rejected', 'reasons': reasons}
                trials.append(trial); emit('candidate', {'round': round_index, 'parent_ref': parent_ref,
                    'status': trial['status'], 'reasons': reasons, 'routing_regressions': len(routing['failures']),
                    'rules_before': before['terminal_rules'], 'rules_after': after['terminal_rules'],
                    'shared_correct': parent['sharing']['shared_correct']})
                if not reasons:
                    score = proposal_rank(parent, after)
                    winners.append((score, trial, candidate_gate, proposed))
        if not winners:
            break
        _, winner, current, proposed = min(winners, key=lambda item: item[0])
        deployed = set(expert_artifacts(current)); bank = {k: v for k, v in proposed.items() if k in deployed}
        event = {'round': round_index, 'children': winner['children'], 'parent_ref': winner['parent']['runtime']['artifact_ref'],
                 'parent': winner['parent'], 'gate': current.export(), 'before': winner['before'], 'after': winner['after'],
                 'routing_checked': winner['routing']['checked'], 'sharing': winner['parent']['sharing']}
        accepted.append(event); emit('accepted', {k: v for k, v in event.items() if k not in ('parent', 'gate', 'sharing')})
        if len(bank) < 2 or counters['gate_rebuilds'] >= config.max_gate_rebuilds:
            break
    final_check = routing_regressions(frozen_gate, current, probes)
    if not final_check['passed']:
        raise AssertionError('An accepted merge regressed the frozen routed system')
    return {'version': VERSION, 'ordering': ordering, 'schedules': schedules, 'config': asdict(config), 'fit_config': asdict(fit_config),
            'initial_complexity': initial, 'final_complexity': complexity(current),
            'models': list(bank.values()), 'gate': current.export(), 'accepted': accepted, 'trials': trials,
            'work': counters, 'final_routing_check': final_check,
            'new_model_calls': 0, 'reserved_final_predictions': 0}
