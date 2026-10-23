"""Empirical cross-expert region merging with local and routing constraints.

Unlike v27, candidates may broaden evidence coverage. Every accepted replacement
retains child support and every recorded baseline route; the frozen full-bank
consensus/rejection executor remains authoritative for the actual verdict.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
import json

from ..decision.artifacts import digest
from . import shared_regions_v27 as shared

VERSION = 'semantic-cross-expert-region-merge-v28'
CONTRACT = digest({'version': VERSION, 'executor': shared.CONTRACT,
                   'mode': 'empirical widening by common conditions and union of permitted scopes; frozen core veto',
                   'contributors': 'require a supported frozen-core match from a contributing expert',
                   'guarantee': 'local correctness and observed routing retention, not universal Boolean equivalence'})


@dataclass(frozen=True)
class Config:
    max_rounds: int = 32
    max_candidates_per_round: int = 64
    min_literal_similarity: float = 0.5

    def __post_init__(self):
        if (type(self.max_rounds) is not int or self.max_rounds < 1
                or type(self.max_candidates_per_round) is not int or self.max_candidates_per_round < 1
                or type(self.min_literal_similarity) not in (int, float)
                or not 0 < self.min_literal_similarity <= 1):
            raise ValueError('Invalid semantic merge bounds')


def unwrap(gate):
    return gate.executor if isinstance(gate, SemanticMergedRegionGate) else gate


def metrics(gate):
    executor = unwrap(gate); rs = list(executor.regions.values())
    return {'regions': len(rs), 'condition_occurrences': sum(len(t) for t in executor.terms.values()),
            'singleton_regions': sum(r['support']['sources'] == 1 for r in rs),
            'cross_expert_regions': sum(len(r['expert_refs']) > 1 for r in rs),
            'multi_batch_regions': sum(r['support']['batches'] > 1 for r in rs),
            'task_scope_links': sum(len(r['scope_refs']) for r in rs),
            'singleton_task_scope_links': sum(c['sources'] == 1 for r in rs for c in r['support_by_scope'].values()),
            'artifact_bytes': len(json.dumps(gate.export(), sort_keys=True, separators=(',', ':')).encode()),
            'expert_trees': len(executor.previous.artifact.get('core_gate', executor.previous.artifact)['previous_gate']['base_gate']['experts'])}


def definitions(gate):
    executor = unwrap(gate)
    return {ref: {'prediction': r['prediction'], 'term': executor.terms[ref], 'tasks': set(r['scope_refs']),
                  'experts': set(r['expert_refs'])} for ref, r in executor.regions.items()}


def pair_candidates(bank, config):
    pairs = []
    for a, b in combinations(sorted(bank), 2):
        left, right = bank[a], bank[b]
        if left['prediction'] != right['prediction'] or left['experts'] == right['experts']:
            continue
        overlap = left['tasks'] & right['tasks']
        common = left['term'] & right['term']
        # A matching label or boilerplate is not enough to define similarity.
        anchors = [(k,v) for k,v in common if (k.startswith('meaning_') and k != 'meaning_available') or k.startswith('outcome_')]
        if not overlap or not anchors:
            continue
        similarity = Fraction(len(common), len(left['term'] | right['term']))
        if similarity < config.min_literal_similarity:
            continue
        task_overlap = Fraction(len(overlap), len(left['tasks'] | right['tasks']))
        pairs.append(((-similarity * task_overlap, -similarity, (a,b)),
                      {'children': [a,b], 'literal_similarity': float(similarity), 'task_similarity': float(task_overlap),
                       'shared_semantic_conditions': len(anchors),
                       'parent': {'prediction': left['prediction'], 'term': common,
                                  'tasks': left['tasks'] | right['tasks'], 'experts': left['experts'] | right['experts']}}))
    return [item for _, item in sorted(pairs)]


def prepared(gate, examples):
    executor = unwrap(gate)
    return [{'scope': digest(shared.task_scope(e['program'])),
             'values': shared.evidence.feature_values(e['program'], e['features']),
             'core_route': executor.previous.select(e['program'], e['features']),
             'baseline': gate.select(e['program'], e['features'])} for e in examples]


def applicable(region, probe):
    route = probe['core_route']
    return (route['covered'] and region['prediction'] == route['prediction'] and probe['scope'] in region['tasks']
            and shared.matches(region['term'], probe['values'])
            and any(m['expert_ref'] in region['experts'] for m in route['matches']))


def evaluate_bank(bank, probes):
    failures = []; routes = []
    for i, probe in enumerate(probes):
        core = probe['core_route']
        accepted = any(applicable(r, probe) for r in bank.values())
        route = {'covered': bool(accepted), 'prediction': core['prediction'] if accepted else -1}
        routes.append(route)
        before = probe['baseline']
        if (before['covered'], before['prediction']) != (route['covered'], route['prediction']):
            failures.append({'probe_index': i, 'before': {'covered': before['covered'], 'prediction': before['prediction']}, 'after': route})
    return {'passed': not failures, 'checked': len(probes), 'failures': failures}, routes


def support(definition, rows, programs, local_probes):
    found = [r for r,p in zip(rows, local_probes) if applicable(definition, p)]
    if not found or any(r['reference'] != definition['prediction'] for r in found):
        raise ValueError('Region has incorrect or empty local support')
    def counts(part):
        return {'sources': len({r['source_group'] for r in part}), 'instructions': len({r['instruction'] for r in part}),
                'batches': len({r['batch'] for r in part})}
    by_scope = {scope: counts([r for r in found if digest(shared.task_scope(programs[r['source_group']])) == scope])
                for scope in sorted(definition['tasks'])}
    if any(not c['sources'] for c in by_scope.values()):
        raise ValueError('Unsupported permitted task scope')
    return counts(found), by_scope, {r['source_group'] for r in found}


def pack(baseline, bank, rows, programs, local_probes):
    executor = unwrap(baseline); pool = sorted(set().union(*(r['term'] for r in bank.values())))
    lookup = {literal: i for i,literal in enumerate(pool)}; entries = []
    for r in bank.values():
        counts, by_scope, _ = support(r, rows, programs, local_probes)
        entry = {'prediction': r['prediction'], 'literal_ids': sorted(lookup[c] for c in r['term']),
                 'scope_refs': sorted(r['tasks']), 'expert_refs': sorted(r['experts']), 'support': counts,
                 'support_by_scope': by_scope, 'description': shared.describe(r['prediction'], len(r['tasks']))}
        entry['region_ref'] = digest(entry); entries.append(entry)
    tasks = set().union(*(r['tasks'] for r in bank.values()))
    artifact = {'version': shared.VERSION, 'contract_ref': shared.CONTRACT,
                'core_gate': executor.artifact['core_gate'], 'literal_pool': shared.conditions(pool),
                'task_scopes': {k: executor.task_scopes[k] for k in sorted(tasks)}, 'regions': sorted({r['region_ref']:r for r in entries}.values(), key=lambda r:r['region_ref'])}
    artifact['artifact_ref'] = digest(artifact)
    wrapper = {'version': VERSION, 'contract_ref': CONTRACT, 'executor': artifact}
    wrapper['artifact_ref'] = digest(wrapper)
    return SemanticMergedRegionGate(wrapper)


def develop(baseline, rows, programs, probes, *, config=Config()):
    shared.evidence.validate_rows(rows)
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Exact local program scope required')
    rows = sorted(rows, key=lambda r:r['source_group'])
    if any(programs[r['source_group']]['instruction'] != r['instruction'] for r in rows):
        raise ValueError('Instruction/program mismatch')
    local_examples = [{'program': programs[r['source_group']], 'features': r['features']} for r in rows]
    locals_ = prepared(baseline, local_examples)
    if any(not p['baseline']['covered'] or p['baseline']['prediction'] != r['reference'] for r,p in zip(rows,locals_)):
        raise ValueError('Baseline must preserve all local labels before region merging')
    # Regression probes supply baseline routing only; reference labels ignored.
    regression = prepared(baseline, probes)
    current = baseline; bank = definitions(current); trials = []; accepted = []; considered = 0; tested = 0
    for round_index in range(config.max_rounds):
        candidates = pair_candidates(bank, config); considered += len(candidates); winners = []
        for candidate in candidates[:config.max_candidates_per_round]:
            tested += 1; child_refs = candidate['children']; parent = candidate['parent']
            parent_key = digest([parent['prediction'], shared.conditions(parent['term']), sorted(parent['tasks']), sorted(parent['experts'])])
            proposal = {k:v for k,v in bank.items() if k not in child_refs}; proposal[parent_key] = parent
            retention = []
            parent_support, _, parent_sources = support(parent, rows, programs, locals_)
            for ref in child_refs:
                _, _, sources = support(bank[ref], rows, programs, locals_)
                retention.append({'child': ref, 'sources': len(sources), 'retained': len(sources & parent_sources)})
            local_check, _ = evaluate_bank(proposal, locals_)
            routing, _ = evaluate_bank(proposal, regression)
            reasons = []
            if not local_check['passed'] or any(r['sources'] != r['retained'] for r in retention):
                reasons.append('local_support_regression')
            if not routing['passed']:
                reasons.append('routing_regression')
            if len(proposal) >= len(bank):
                reasons.append('no_region_compression')
            trial = {k:v for k,v in candidate.items() if k != 'parent'}
            trial.update(round=round_index, parent={'prediction': parent['prediction'], 'conditions': shared.conditions(parent['term']),
                          'scope_refs': sorted(parent['tasks']), 'expert_refs': sorted(parent['experts'])},
                         local_support=parent_support, child_retention=retention, local_check=local_check, routing=routing,
                         status='rejected' if reasons else 'qualified', reasons=reasons)
            trials.append(trial)
            if not reasons:
                rank = (len(proposal), sum(len(r['term']) for r in proposal.values()), -parent_support['sources'],
                        -len(parent['experts']), -candidate['literal_similarity'], tuple(child_refs))
                winners.append((rank, trial, proposal))
        if not winners:
            break
        _, winner, proposal = min(winners, key=lambda v:v[0])
        next_gate = pack(baseline, proposal, rows, programs, locals_)
        before = metrics(current); after = metrics(next_gate)
        if after['regions'] >= before['regions']:
            raise AssertionError('Accepted region merge did not compress')
        # Check the real deployed executor as well as the cached search evaluator.
        for e,p in zip(local_examples + probes, locals_ + regression):
            route = next_gate.select(e['program'], e['features'])
            if (route['covered'],route['prediction']) != (p['baseline']['covered'],p['baseline']['prediction']):
                raise AssertionError('Packed runtime differs from checked candidate')
        accepted.append({'round': round_index, 'trial_index': trials.index(winner), 'before': before, 'after': after,
                         'children': winner['children'], 'parent': winner['parent'], 'child_retention': winner['child_retention'],
                         'support': winner['local_support'], 'gate_ref': next_gate.artifact['artifact_ref']})
        current = next_gate; bank = definitions(current)
    if not isinstance(current, SemanticMergedRegionGate):
        current = pack(baseline, bank, rows, programs, locals_)
    # Old regions are contained in the final regional union: no coverage loss
    # for any feature assignment. The reverse implication is deliberately optional.
    old_bank = definitions(baseline); final_bank = definitions(current); checks = 0; broadened = False
    for old_region in old_bank.values():
        for task in old_region['tasks']:
            union = [r['term'] for r in final_bank.values() if r['prediction']==old_region['prediction'] and task in r['tasks']]
            passed,_ = shared.implies_union(old_region['term'],union); checks += 1
            if not passed:
                raise AssertionError('Merged regions lost old Boolean coverage')
    for new_region in final_bank.values():
        for task in new_region['tasks']:
            union = [r['term'] for r in old_bank.values() if r['prediction']==new_region['prediction'] and task in r['tasks']]
            passed,_ = shared.implies_union(new_region['term'],union)
            broadened |= not passed
    return current, {'version': VERSION, 'config': asdict(config), 'before': metrics(baseline), 'after': metrics(current),
                     'accepted': accepted, 'trials': trials, 'work': {'eligible_pairs': considered, 'tested_candidates': tested},
                     'baseline_boolean_coverage_retained': True, 'containment_checks': checks, 'boolean_regions_broadened': broadened,
                     'regression_probes': len(probes), 'new_model_calls': 0, 'reserved_final_predictions': 0,
                     'scope': 'Known local and routing retention; expanded regions do not have a universal correctness guarantee.'}


class SemanticMergedRegionGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'contract_ref', 'executor', 'artifact_ref'} or artifact['version'] != VERSION
                or artifact['contract_ref'] != CONTRACT
                or artifact['artifact_ref'] != digest({k:v for k,v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Invalid semantic merged-region contract')
        self.executor = shared.SharedRegionGate(artifact['executor'])
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def shortlist(self, program):
        return self.executor.shortlist(program)

    def accepts_task(self, program):
        return self.executor.accepts_task(program)

    def select(self, program, record):
        candidates = self.shortlist(program); route = self.executor.previous.select(program, record)
        if not route['covered']:
            return {**route, 'semantic_candidates': candidates, 'semantic_regions': []}
        values = shared.evidence.feature_values(program, record)
        contributors = {m['expert_ref'] for m in route['matches']}
        found = [ref for ref in candidates['region_refs']
                 if self.executor.regions[ref]['prediction'] == route['prediction']
                 and contributors.intersection(self.executor.regions[ref]['expert_refs'])
                 and shared.matches(self.executor.terms[ref], values)]
        if not found:
            return {'covered': False, 'prediction': -1, 'reason': 'outside_semantic_rule_regions', 'matches': [],
                    'semantic_candidates': candidates, 'semantic_regions': []}
        return {**route, 'reason': 'supported_semantically_merged_region', 'semantic_candidates': candidates,
                'semantic_regions': sorted(found)}

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, shared.evidence.project(program, observation, pair_ref, interpretation))

    def definition(self, ref):
        return {**self.executor.definition(ref), 'contributing_expert_required': True, 'validation': 'Empirically merged; local and recorded-route preservation, not exact equivalence to original regions.'}
