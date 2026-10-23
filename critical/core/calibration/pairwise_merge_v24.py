"""Pairwise expert merges with fresh support fitting and frozen routing checks."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from itertools import combinations

from ..decision.artifacts import digest
from . import local_compression_v18 as local
from . import shared_tree_fit_v24 as learner
from . import evidence_coverage_v20 as coverage
from . import evidence_support_v21 as support
from .counterexample_coverage_v23 import RejectionCoverageGate
from . import merge_route_support_v24 as route_support

VERSION = 'pairwise-shared-merge-v24'


@dataclass(frozen=True)
class Config:
    max_rounds: int = 3
    max_pair_fits: int = 24
    max_gate_rebuilds: int = 32
    max_parent_candidates: int = 3

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ValueError('Positive pairwise search bounds required')


def expert_artifacts(gate):
    return route_support.core_artifact(gate)['previous_gate']['base_gate']['experts']


def complexity(gate):
    outer = route_support.core_artifact(gate); inner = outer['previous_gate']; core = inner['base_gate']
    trees = [local.complexity(p['tree']) for p in core['experts'].values()]
    tree_conditions = sum(t['nodes'] - t['rules'] for t in trees)
    guard_conditions = sum(len(r['guards']) for r in core['rules'])
    semantic_conditions = sum(len(e['conditions']) for e in inner['envelopes'].values())
    rejection_conditions = sum(len(c) for c in outer['support_clauses'])
    routing_conditions = sum(len(c) for c in gate.artifact['clauses']) if gate.artifact['version'] == route_support.VERSION else 0
    return {'experts': len(trees), 'terminal_rules': sum(t['rules'] for t in trees),
            'tree_conditions': tree_conditions, 'coverage_regions': len(core['rules']),
            'guard_conditions': guard_conditions, 'semantic_conditions': semantic_conditions,
            'rejection_conditions': rejection_conditions,
            'routing_conditions': routing_conditions,
            'stored_conditions': tree_conditions + guard_conditions + semantic_conditions + rejection_conditions + routing_conditions}


def proposal_rank(parent, deployment):
    return (deployment['experts'], deployment['terminal_rules'], -parent['sharing']['shared_correct'],
            -parent['sharing']['cross_batch_support'], deployment['stored_conditions'], parent['runtime']['artifact_ref'])


def requirements(children, rows):
    result = []
    for child in children:
        sources = set(child['policy']['training']['source_groups'])
        cohort = [r for r in rows if r['source_group'] in sources]
        if {r['source_group'] for r in cohort} != sources:
            raise ValueError('Child provenance is outside the fitting pool')
        result.append(local.requirement(child, cohort))
        for batch in sorted({r['batch'] for r in cohort}):
            part = [r for r in cohort if r['batch'] == batch]
            result.append({'sources': sorted(r['source_group'] for r in part), 'correct': local.correct(child, part)})
        result.extend(child.get('preserved_requirements', []))
    union = set().union(*(set(c['policy']['training']['source_groups']) for c in children))
    return local.scopes([r for r in rows if r['source_group'] in union], result)


def routing_regressions(previous, candidate, probes):
    """Protect decisions, not expert IDs; labels are not used in this gate."""
    failures = []; checks = []
    for probe in probes:
        before = previous.select(probe['program'], probe['features'])
        after = candidate.select(probe['program'], probe['features'])
        reason = None
        if before['covered'] and not after['covered']:
            reason = 'lost_protected_coverage'
        elif not before['covered'] and after['covered']:
            reason = 'new_unvalidated_acceptance'
        elif before['covered'] and before['prediction'] != after['prediction']:
            reason = 'changed_protected_verdict'
        item = {'case': probe.get('case'), 'before': {'covered': before['covered'], 'prediction': before['prediction']},
                'after': {'covered': after['covered'], 'prediction': after['prediction']}, 'regression': reason}
        checks.append(item)
        if reason:
            failures.append(item)
    return {'passed': not failures, 'checked': len(checks), 'failures': failures, 'checks': checks,
            'scope': 'Exact prior accept/defer and accepted-verdict preservation; expert identities may change.'}


def rebuild_gate(models, rows, programs, previous):
    previous_core = route_support.core_artifact(previous)
    config = coverage.Config(**previous_core['previous_gate']['base_gate']['config'])
    core, report = coverage.build(models, rows, programs, config)
    semantic = support.build(core, rows, programs)
    artifact = deepcopy(previous_core)
    # The v23 counterexample checks remain fixed. Do not recalibrate them to
    # hide new routing regressions after changing the expert bank.
    artifact['previous_gate'] = semantic.export()
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    return RejectionCoverageGate(artifact), {k: v for k, v in report.items() if k != 'training'}


def parent_candidates(children, rows, fit_config, cache, counters, config):
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
            value, report = learner.fit(selected, reqs, max_rules=max_rules, config=profile, preferred=preferred)
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


def develop(models, rows, programs, frozen_gate, probes, *, config=Config(), fit_config=learner.Config(), emit=None):
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
    initial = complexity(frozen_gate); current = frozen_gate; trials = []; accepted = []; cache = {}
    counters = {'pair_fits': 0, 'pair_fit_cache_hits': 0, 'gate_rebuilds': 0}
    emit = emit or (lambda kind, value: None)
    for round_index in range(config.max_rounds):
        winners = []
        for refs in combinations(sorted(bank), 2):
            children = [bank[k] for k in refs]
            candidates, fits = parent_candidates(children, rows, fit_config, cache, counters, config)
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
    return {'version': VERSION, 'config': asdict(config), 'fit_config': asdict(fit_config),
            'initial_complexity': initial, 'final_complexity': complexity(current),
            'models': list(bank.values()), 'gate': current.export(), 'accepted': accepted, 'trials': trials,
            'work': counters, 'final_routing_check': final_check,
            'new_model_calls': 0, 'reserved_final_predictions': 0}
