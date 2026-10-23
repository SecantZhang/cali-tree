"""Selective execution of frozen experts using bounded, evidence-based guards.

The gate learns where existing expert outputs are locally supported. It does not
fit new verdicts, look up source membership, or ask an LLM to reinterpret a rule.
Conflicting expert recommendations and missing evidence defer to the regular judge.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations
import re

from ..decision.artifacts import digest
from ..decision.bound_evidence_v2 import KINDS, validate_program
from .semantic_hierarchy.portable_features_v8 import SPECS, validate_record, project
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from .local_compression_v18 import gate as local_gate, validate_rows
from ..optimization.prompt.calitree.task_coverage import task_scope, _validate_scope

VERSION = 'evidence-coverage-v20'
TASK_SPECS = {'task_outcome_' + k: 'The compiled instruction requests an outcome of kind ' + k for k in KINDS}
TASK_SPECS.update({
    'task_compound': 'The compiled instruction contains multiple requested requirements.',
    'task_identity_required': 'The compiled instruction requires an identity correspondence check.',
    'task_explicit_increase': 'An authorized-change statement begins with increase, enlarge, or expand.',
    'task_explicit_decrease': 'An authorized-change statement begins with reduce, decrease, or shrink.'})
FEATURES = {**SPECS, **TASK_SPECS}
CONTRACT_REF = digest({'version': VERSION, 'features': FEATURES,
                       'direction': 'Case-insensitive leading affirmative verb in compiler authorized_changes; no substring/name matching.'})


@dataclass(frozen=True)
class Config:
    max_guards: int = 6
    max_pair_states: int = 3000
    max_rules: int = 256
    max_rows: int = 256
    max_experts: int = 16

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ValueError('Positive integer coverage bounds required')


def task_features(program):
    validate_program(program)
    values = {'task_outcome_' + k: any(c['role'] == 'outcome' and c['kind'] == k for c in program['checks']) for k in KINDS}
    values.update(task_compound=len(program['requirements']) > 1,
                  task_identity_required=any(c['role'] == 'identity' for c in program['checks']))
    actions = program['contract']['authorized_changes']
    values['task_explicit_increase'] = any(re.match(r'^\s*(increase|enlarge|expand)\b', a, re.I) is not None for a in actions)
    values['task_explicit_decrease'] = any(re.match(r'^\s*(reduce|decrease|shrink)\b', a, re.I) is not None for a in actions)
    return values


def feature_values(program, record):
    validate_record(record)
    if record is None or not record['features']['meaning_available']:
        return None
    return {**record['features'], **task_features(program)}


class _BudgetReached(Exception):
    pass


def build(models, rows, programs, config=Config()):
    """Cover correct expert predictions with reusable, zero-local-error regions.

    Each guard is witnessed by at least two distinct sources and instructions.
    Pairwise witnesses constrain a small set-cover search over counterexamples;
    the exported runtime contains only predicate guards, expert trees and counts.
    """
    validate_rows(rows)
    if (len(rows) > config.max_rows or not 1 <= len(models) <= config.max_experts
            or set(programs) != {r['source_group'] for r in rows}):
        raise ValueError('Coverage input scope or size is invalid')
    values_by_source = {}
    for row in rows:
        p = programs[row['source_group']]
        if p['instruction'] != row['instruction']:
            raise ValueError('Instruction/program mismatch')
        values_by_source[row['source_group']] = feature_values(p, row['features'])
    # Case/source renaming does not change the search order. Identical feature
    # and label ties are interchangeable for all guard scores.
    rows = sorted(rows, key=lambda r: (digest(values_by_source[r['source_group']]), r['reference'], r['source_group']))
    values = [values_by_source[r['source_group']] for r in rows]
    available = sum(1 << i for i, v in enumerate(values) if v is not None)
    full = (1 << len(rows)) - 1
    literals = {}
    for name in sorted(FEATURES, key=lambda k: (not k.startswith('meaning_'), not k.startswith('task_'), k)):
        mask = sum(1 << i for i, v in enumerate(values) if v is not None and v[name])
        for truth, selected in ((True, mask), (False, available ^ mask)):
            literals.setdefault(selected, {'feature': name, 'value': truth})
    experts = {}; predicted = {}
    for model in models:
        sources = set(model['policy']['training']['source_groups'])
        selected = sorted((r for r in rows if r['source_group'] in sources), key=lambda r: r['source_group'])
        if sources != {r['source_group'] for r in selected}:
            raise ValueError('Expert has outside-pool training sources')
        decision = local_gate(model, selected, [{'sources': sorted(sources), 'correct': 0}], max_rules=10000)
        if decision['status'] != 'accepted':
            raise ValueError('Invalid original expert: ' + ','.join(decision['reasons']))
        ref = model['runtime']['artifact_ref']; experts[ref] = deepcopy(model['runtime'])
        predicted[ref] = [p['prediction'] for p in PortableRuleExecutor(model['runtime']).predict_records([r['features'] for r in rows])]
    stats = {'witness_pairs': 0, 'pair_states': 0, 'exhausted_pairs': 0, 'candidate_rules': 0}
    candidates = {}
    for ref in sorted(experts):
        ps = predicted[ref]
        for label in range(3):
            base = sum(1 << i for i, p in enumerate(ps) if p == label and values[i] is not None)
            good = sum(1 << i for i, r in enumerate(rows) if ps[i] == label == r['reference'] and values[i] is not None)
            bad = base & (full ^ good)
            positive = [i for i in range(len(rows)) if good >> i & 1]
            for a, b in combinations(positive, 2):
                if rows[a]['instruction'] == rows[b]['instruction']:
                    continue
                stats['witness_pairs'] += 1
                options = {}
                for mask, literal in literals.items():
                    if mask >> a & 1 and mask >> b & 1:
                        excludes = bad & (full ^ mask)
                        if excludes:
                            # Among equally separating literals prefer broader
                            # positive support, then declared semantic identity.
                            rank = (-(mask & good).bit_count(), not literal['feature'].startswith('meaning_'),
                                    not literal['feature'].startswith('task_'), literal['feature'], literal['value'])
                            if excludes not in options or rank < options[excludes][0]:
                                options[excludes] = (rank, mask, literal)
                visited = 0

                @lru_cache(None)
                def solve(remaining, depth):
                    nonlocal visited
                    if not remaining:
                        return ()
                    if not depth:
                        return None
                    if visited >= config.max_pair_states:
                        raise _BudgetReached
                    visited += 1
                    bits = [1 << i for i in range(len(rows)) if remaining >> i & 1]
                    pivot = min(bits, key=lambda bit: (sum(bool(x & bit) for x in options),
                                                      digest(values[bit.bit_length()-1])))
                    chosen = sorted((x for x in options if x & pivot),
                                    key=lambda x: (-(x & remaining).bit_count(), options[x][0]))
                    best = None
                    for excludes in chosen:
                        tail = solve(remaining & ~excludes, depth - 1)
                        if tail is not None:
                            candidate = (excludes,) + tail
                            if best is None or len(candidate) < len(best):
                                best = candidate
                            if len(best) == 1:
                                break
                    return best

                try:
                    answer = solve(bad, config.max_guards)
                except _BudgetReached:
                    stats['exhausted_pairs'] += 1; answer = None
                stats['pair_states'] += visited
                if answer is None:
                    continue
                mask = base
                guards = []
                for excludes in answer:
                    _, literal_mask, literal = options[excludes]
                    mask &= literal_mask; guards.append(literal)
                guards.sort(key=lambda c: (c['feature'], c['value']))
                cohort = [r for i, r in enumerate(rows) if mask >> i & 1]
                if mask & bad or len(cohort) < 2 or len({r['instruction'] for r in cohort}) < 2:
                    raise AssertionError('An unsupported or incorrect guard escaped search')
                rule = {'expert_ref': ref, 'expert_prediction': label, 'guards': guards,
                        'support': {'sources': len(cohort), 'instructions': len({r['instruction'] for r in cohort}),
                                    'batches': len({r['batch'] for r in cohort})}}
                key = digest(rule); candidates[key] = (rule, mask)
    stats['candidate_rules'] = len(candidates)
    coverable = 0
    for _, mask in candidates.values():
        coverable |= mask
    selected = []; covered = 0
    while covered != coverable and len(selected) < config.max_rules:
        choices = [(key, rule, mask) for key, (rule, mask) in candidates.items() if mask & ~covered]
        key, rule, mask = min(choices, key=lambda x: (-(x[2] & ~covered).bit_count(), len(x[1]['guards']),
                                                     -x[1]['support']['batches'], -x[1]['support']['sources'], x[0]))
        selected.append((key, rule, mask)); covered |= mask
    # Drop redundant regions without sacrificing any covered training source.
    for item in list(reversed(selected)):
        other = 0
        for entry in selected:
            if entry[0] != item[0]:
                other |= entry[2]
        if other == covered:
            selected.remove(item)
    used = {rule['expert_ref'] for _, rule, _ in selected}
    artifact = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'config': asdict(config),
                'experts': {k: experts[k] for k in sorted(used)},
                'rules': [rule for _, rule, _ in sorted(selected)],
                'task_profiles': sorted({digest(task_scope(p)): task_scope(p) for p in programs.values()}.values(), key=digest),
                'fit_contract': 'Each region has two distinct sources/instructions and zero errors on the local fitting pool; unseen correctness is not guaranteed.'}
    artifact['artifact_ref'] = digest(artifact)
    gate = EvidenceCoverageGate(artifact)
    diagnostics = []
    for row in rows:
        route = gate.select(programs[row['source_group']], row['features'])
        if route['covered'] and route['prediction'] != row['reference']:
            raise AssertionError('Fitted gate changed a supported local verdict')
        diagnostics.append({'case': row.get('case'), 'source_group': row['source_group'], 'reference': row['reference'], **route})
    return gate, {'version': VERSION, 'config': asdict(config), **stats,
                  'selected_rules': len(selected), 'coverable_sources': coverable.bit_count(),
                  'covered_sources': covered.bit_count(), 'total_sources': len(rows),
                  'rule_budget_exhausted': covered != coverable, 'training': diagnostics,
                  'training_ref': digest(rows), 'global_optimality_claim': False, 'new_model_calls': 0}


class EvidenceCoverageGate:
    def __init__(self, artifact):
        fields = {'version', 'feature_contract_ref', 'config', 'experts', 'rules', 'task_profiles', 'fit_contract', 'artifact_ref'}
        if (set(artifact) != fields or artifact['version'] != VERSION or artifact['feature_contract_ref'] != CONTRACT_REF
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Changed evidence coverage contract')
        config = Config(**artifact['config'])
        if len(artifact['rules']) > config.max_rules or len(artifact['experts']) > config.max_experts:
            raise ValueError('Coverage artifact exceeds its bounds')
        if not artifact['task_profiles'] or len(artifact['task_profiles']) > config.max_rows:
            raise ValueError('Invalid task profiles')
        for profile in artifact['task_profiles']:
            _validate_scope(profile)
        self.task_profiles = {digest(p) for p in artifact['task_profiles']}
        self.experts = {ref: PortableRuleExecutor(value) for ref, value in artifact['experts'].items()}
        if any(ex.artifact['artifact_ref'] != ref for ref, ex in self.experts.items()):
            raise ValueError('Changed expert identity')
        for rule in artifact['rules']:
            if (set(rule) != {'expert_ref', 'expert_prediction', 'guards', 'support'} or rule['expert_ref'] not in self.experts
                    or type(rule['expert_prediction']) is not int or rule['expert_prediction'] not in (0, 1, 2)
                    or len(rule['guards']) > config.max_guards
                    or len({c['feature'] for c in rule['guards']}) != len(rule['guards'])):
                raise ValueError('Invalid coverage rule')
            for c in rule['guards']:
                if set(c) != {'feature', 'value'} or c['feature'] not in FEATURES or type(c['value']) is not bool:
                    raise ValueError('Undeclared coverage predicate')
            support = rule['support']
            if (set(support) != {'sources', 'instructions', 'batches'} or any(type(v) is not int for v in support.values())
                    or not 2 <= support['instructions'] <= support['sources'] or not 1 <= support['batches'] <= support['sources']):
                raise ValueError('Unsupported coverage region')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def accepts_task(self, program):
        try:
            return digest(task_scope(program)) in self.task_profiles
        except (ValueError, KeyError, TypeError):
            return False

    def select(self, program, record):
        fallback = {'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
        try:
            values = feature_values(program, record)
        except (ValueError, KeyError, TypeError):
            return fallback
        if values is None:
            return fallback
        if not self.accepts_task(program):
            return {**fallback, 'reason': 'unseen_task_profile'}
        predictions = {}; matches = []
        for rule in self.artifact['rules']:
            if not all(values[c['feature']] == c['value'] for c in rule['guards']):
                continue
            ref = rule['expert_ref']
            if ref not in predictions:
                predictions[ref] = self.experts[ref].predict_records([record])[0]
            if predictions[ref]['prediction'] == rule['expert_prediction']:
                matches.append({'rule_ref': digest(rule), 'expert_ref': ref, 'prediction': rule['expert_prediction'],
                                'trace': predictions[ref]['trace']})
        labels = {m['prediction'] for m in matches}
        if len(labels) != 1:
            return {**fallback, 'reason': 'conflicting_supported_experts' if labels else 'no_supported_evidence_region', 'matches': matches}
        return {'covered': True, 'prediction': next(iter(labels)), 'reason': 'supported_expert_consensus', 'matches': matches}

    def select_bound(self, program, observation, pair_ref, interpretation):
        record = project(program, observation, pair_ref, interpretation)
        return self.select(program, record)
