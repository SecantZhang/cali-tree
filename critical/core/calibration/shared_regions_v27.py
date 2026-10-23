"""Exact Boolean simplification and shared storage of semantic rule regions.

Compile the v26 region union into canonical evidence conjunctions with shared
structural task scopes. No observed-only equivalences or new judgments are fit.
The runtime retains the v24 consensus/rejection gate, not the old v26 region bank.
"""
from copy import deepcopy
from functools import lru_cache
from itertools import combinations

from ..decision.artifacts import digest
from . import semantic_regions_v26 as old
from . import evidence_coverage_v20 as evidence
from . import merge_route_support_v24 as core
from ..optimization.prompt.calitree.task_coverage import task_scope, _validate_scope, LABELS

VERSION = 'shared-semantic-regions-v27'
CONTRACT = digest({'version': VERSION, 'features': evidence.CONTRACT_REF,
                   'semantics': 'Exact disjunction of canonical conjunctions per task scope and label; frozen full-bank veto.',
                   'operations': ['duplicate pooling', 'absorption', 'complementary literal elimination'],
                   'storage': 'shared literal pool with per-task support counts'})


def cube(conditions):
    result = {}
    for c in conditions:
        if set(c) != {'feature', 'value'} or c['feature'] not in evidence.FEATURES or type(c['value']) is not bool:
            raise ValueError('Invalid region literal')
        if c['feature'] in result and result[c['feature']] != c['value']:
            raise ValueError('Contradictory region conjunction')
        result[c['feature']] = c['value']
    return frozenset(result.items())


def conditions(term):
    return [{'feature': k, 'value': v} for k, v in sorted(term)]


def canonical_key(term):
    return tuple(sorted(term))


def describe(prediction, count):
    return f'{LABELS[prediction].capitalize()} when all evidence conditions hold for one of {count} supported task scopes; full-bank veto remains required.'


def original_terms(gate):
    terms = {}; scopes = {}
    for r in gate.regions.values():
        scope_ref = digest(r['scope']); scopes[scope_ref] = r['scope']
        combined = r['path'] + gate.rules[r['rule_ref']]['guards'] + gate.envelopes[r['rule_ref']]['conditions']
        key = (r['prediction'], cube(combined))
        terms.setdefault(key, set()).add(scope_ref)
    return terms, scopes


def absorb(terms):
    result = {k: set(v) for k, v in terms.items() if v}
    for key in sorted(result, key=lambda k: (len(k[1]), k[0], canonical_key(k[1]))):
        for other in list(result):
            if key != other and key[0] == other[0] and key[1] <= other[1]:
                result[other] -= result[key]
    return {k: v for k, v in result.items() if v}


def cost(terms):
    return (len(terms), sum(len(k[1]) for k in terms), sum(len(v) for v in terms.values()))


def simplify(terms):
    """Exact identities only: A OR (A AND B)=A, AB OR A!B=A."""
    result = absorb(terms); steps = []
    while True:
        options = []
        keys = sorted(result, key=lambda k: (k[0], canonical_key(k[1])))
        for a, b in combinations(keys, 2):
            shared_scopes = result[a] & result[b]
            if a[0] != b[0] or not shared_scopes:
                continue
            left, right = a[1] - b[1], b[1] - a[1]
            if len(left) != 1 or len(right) != 1:
                continue
            x, y = next(iter(left)), next(iter(right))
            if x[0] != y[0] or x[1] == y[1]:
                continue
            merged = (a[0], a[1] & b[1])
            proposal = {k: set(v) for k, v in result.items()}
            proposal[a] -= shared_scopes; proposal[b] -= shared_scopes
            proposal.setdefault(merged, set()).update(shared_scopes)
            proposal = absorb(proposal)
            if cost(proposal) < cost(result):
                options.append((cost(proposal), canonical_key(merged[1]), tuple(sorted(shared_scopes)), proposal, x[0]))
        if not options:
            return result, steps
        _, _, _, result, removed = min(options, key=lambda x: x[:3])
        steps.append({'removed_complementary_feature': removed, 'cost': list(cost(result))})


def implies_union(term, union, *, max_states=100000):
    """Prove a Boolean cube is covered by a DNF, without sampling examples."""
    visited = 0
    @lru_cache(None)
    def covered(fixed):
        nonlocal visited
        visited += 1
        if visited > max_states:
            raise ValueError('Boolean equivalence proof budget exceeded')
        fixed = frozenset(fixed); values = dict(fixed)
        compatible = [u for u in union if all(k not in values or values[k] == v for k, v in u)]
        if any(u <= fixed for u in compatible):
            return True
        if not compatible:
            return False
        smallest = min(compatible, key=lambda u: (len(u-fixed), canonical_key(u)))
        name = min(k for k, _ in smallest if k not in values)
        return all(covered(tuple(sorted(fixed | {(name, value)}))) for value in (False, True))
    return covered(tuple(sorted(term))), visited


def equivalent(left, right):
    scopes = set().union(*left.values(), *right.values())
    checked = states = 0
    for scope in sorted(scopes):
        for label in range(3):
            a = [k[1] for k, ss in left.items() if k[0] == label and scope in ss]
            b = [k[1] for k, ss in right.items() if k[0] == label and scope in ss]
            for source, target in ((a, b), (b, a)):
                for term in source:
                    passed, used = implies_union(term, target); checked += 1; states += used
                    if not passed:
                        return {'passed': False, 'cube_implications': checked, 'states': states}
    return {'passed': True, 'cube_implications': checked, 'states': states}


def matches(term, values):
    return values is not None and all(values[k] == v for k, v in term)


def build(gate, rows, programs):
    # Reproduce the input definitions to ensure their support is the exact local
    # pool, not metadata supplied by callers or development examples.
    reproduced = old.build(gate.previous, rows, programs)
    if reproduced.export() != gate.export():
        raise ValueError('Input regions do not match the local support pool')
    initial, scopes = original_terms(gate)
    reduced, steps = simplify(initial)
    proof = equivalent(initial, reduced)
    if not proof['passed']:
        raise AssertionError('Region simplification changed the Boolean union')
    local_rows = []
    for r in rows:
        p = programs[r['source_group']]
        local_rows.append((r, digest(task_scope(p)), evidence.feature_values(p, r['features']), gate.previous.select(p, r['features'])))
    entries = []
    for (label, term), tasks in sorted(reduced.items(), key=lambda kv: (kv[0][0], canonical_key(kv[0][1]))):
        supported = [(r, route) for r, task, values, route in local_rows
                     if task in tasks and matches(term, values) and route['covered'] and route['prediction'] == label]
        if not supported or any(r['reference'] != label for r, _ in supported):
            raise ValueError('Invalid simplified local support')
        # A local source is counted once even if multiple original experts or
        # regions support it. Expert links require an actual old-region match.
        refs = set()
        for original in gate.regions.values():
            original_cube = cube(original['path'] + gate.rules[original['rule_ref']]['guards']
                                 + gate.envelopes[original['rule_ref']]['conditions'])
            if original['prediction'] == label and digest(original['scope']) in tasks and term <= original_cube:
                refs.add(original['expert_ref'])
        per_scope = {}
        for task in sorted(tasks):
            part = [r for r, _ in supported if digest(task_scope(programs[r['source_group']])) == task]
            per_scope[task] = {'sources': len({r['source_group'] for r in part}),
                               'instructions': len({r['instruction'] for r in part}),
                               'batches': len({r['batch'] for r in part})}
        entry = {'prediction': label, 'conditions': conditions(term), 'scope_refs': sorted(tasks),
                 'expert_refs': sorted(refs),
                 'support': {'sources': len({r['source_group'] for r, _ in supported}),
                             'instructions': len({r['instruction'] for r, _ in supported}),
                             'batches': len({r['batch'] for r, _ in supported})},
                 'support_by_scope': per_scope, 'description': describe(label, len(tasks))}
        entries.append(entry)
    pool = sorted({(c['feature'], c['value']) for r in entries for c in r['conditions']})
    lookup = {c: i for i, c in enumerate(pool)}
    for entry in entries:
        entry['literal_ids'] = sorted(lookup[(c['feature'], c['value'])] for c in entry.pop('conditions'))
        entry['region_ref'] = digest(entry)
    artifact = {'version': VERSION, 'contract_ref': CONTRACT, 'core_gate': gate.previous.export(),
                'task_scopes': {k: scopes[k] for k in sorted(scopes)}, 'literal_pool': conditions(pool), 'regions': sorted(entries, key=lambda r: r['region_ref'])}
    artifact['artifact_ref'] = digest(artifact)
    result = SharedRegionGate(artifact)
    for row in rows:
        p = programs[row['source_group']]
        before, after = gate.select(p, row['features']), result.select(p, row['features'])
        if (before['covered'], before['prediction']) != (after['covered'], after['prediction']):
            raise AssertionError('Simplified gate changed a local route')
    report = {'before': fragmentation(gate, rows, programs), 'after': fragmentation(result, rows, programs),
              'canonical_kernels_before_boolean_simplification': len(initial), 'simplification_steps': steps,
              'boolean_equivalence': proof, 'new_model_calls': 0}
    return result, report


class SharedRegionGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'contract_ref', 'core_gate', 'task_scopes', 'literal_pool', 'regions', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['contract_ref'] != CONTRACT
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Invalid shared region contract')
        self.previous = core.restore(artifact['core_gate'])
        base = core.core_artifact(self.previous)['previous_gate']['base_gate']
        self.task_scopes = deepcopy(artifact['task_scopes']); self.regions = {}; self.terms = {}; self.by_scope = {}
        pool = artifact['literal_pool']
        for literal in pool:
            cube([literal])
        if pool != conditions(set((c['feature'], c['value']) for c in pool)):
            raise ValueError('Noncanonical literal pool')
        used_literals = set()
        for ref, scope in self.task_scopes.items():
            _validate_scope(scope)
            if digest(scope) != ref or scope not in base['task_profiles']:
                raise ValueError('Unsupported or changed structural scope')
        for r in artifact['regions']:
            if (set(r) != {'prediction', 'literal_ids', 'scope_refs', 'expert_refs', 'support', 'support_by_scope', 'description', 'region_ref'}
                    or type(r['prediction']) is not int or r['prediction'] not in (0,1,2)
                    or r['region_ref'] != digest({k: v for k, v in r.items() if k != 'region_ref'})
                    or r['region_ref'] in self.regions):
                raise ValueError('Invalid shared region')
            if (any(type(i) is not int or not 0 <= i < len(pool) for i in r['literal_ids'])
                    or r['literal_ids'] != sorted(set(r['literal_ids']))):
                raise ValueError('Invalid literal references')
            term = cube([pool[i] for i in r['literal_ids']]); used_literals.update(r['literal_ids'])
            for key, allowed in (('scope_refs', self.task_scopes), ('expert_refs', base['experts'])):
                if not r[key] or r[key] != sorted(set(r[key])) or not set(r[key]) <= set(allowed):
                    raise ValueError('Invalid region scope/expert references')
            counts = r['support']
            if (set(counts) != {'sources', 'instructions', 'batches'} or any(type(v) is not int or v < 1 for v in counts.values())
                    or counts['instructions'] > counts['sources'] or counts['batches'] > counts['sources']
                    or r['description'] != describe(r['prediction'], len(r['scope_refs']))):
                raise ValueError('Invalid shared support or description')
            if set(r['support_by_scope']) != set(r['scope_refs']):
                raise ValueError('Incomplete per-task support')
            for part in r['support_by_scope'].values():
                if (set(part) != {'sources', 'instructions', 'batches'}
                        or any(type(v) is not int or v < 1 for v in part.values())
                        or part['instructions'] > part['sources'] or part['batches'] > part['sources']):
                    raise ValueError('Invalid per-task support')
            if sum(p['sources'] for p in r['support_by_scope'].values()) != counts['sources']:
                raise ValueError('Task supports do not partition region sources')
            self.regions[r['region_ref']] = deepcopy(r); self.terms[r['region_ref']] = term
            for scope in r['scope_refs']:
                self.by_scope.setdefault(scope, []).append(r['region_ref'])
        if used_literals != set(range(len(pool))):
            raise ValueError('Unused literal pool entries')
        if not self.regions or set(self.by_scope) != set(self.task_scopes):
            raise ValueError('Empty or unused shared scope catalog')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def shortlist(self, program):
        try:
            refs = self.by_scope.get(digest(task_scope(program)), [])
        except (ValueError, KeyError, TypeError):
            refs = []
        return {'task_supported': bool(refs), 'decision_ready': False, 'region_refs': sorted(refs),
                'expert_refs': sorted({expert for ref in refs for expert in self.regions[ref]['expert_refs']})}

    def accepts_task(self, program):
        return self.shortlist(program)['task_supported']

    def select(self, program, record):
        candidates = self.shortlist(program); prior = self.previous.select(program, record)
        if not prior['covered']:
            return {**prior, 'semantic_candidates': candidates, 'semantic_regions': []}
        values = evidence.feature_values(program, record)
        found = sorted(ref for ref in candidates['region_refs'] if self.regions[ref]['prediction'] == prior['prediction']
                       and matches(self.terms[ref], values))
        if not found:
            return {'covered': False, 'prediction': -1, 'reason': 'outside_semantic_rule_regions', 'matches': [],
                    'semantic_candidates': candidates, 'semantic_regions': []}
        return {**prior, 'reason': 'supported_shared_semantic_region', 'semantic_candidates': candidates, 'semantic_regions': found}

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, evidence.project(program, observation, pair_ref, interpretation))

    def definition(self, ref):
        r = self.regions[ref]
        return {**deepcopy(r), 'task_scopes': [deepcopy(self.task_scopes[k]) for k in r['scope_refs']],
                'conditions': conditions(self.terms[ref]),
                'evidence_conditions': [{**c, 'description': evidence.FEATURES[c['feature']]} for c in conditions(self.terms[ref])],
                'trust_requires': 'Full frozen expert-bank agreement and rejection checks remain required.'}


def fragmentation(gate, rows, programs):
    regions = list(gate.regions.values())
    if isinstance(gate, SharedRegionGate):
        literals = sum(len(t) for t in gate.terms.values())
        links = sum(len(r['scope_refs']) for r in regions)
        cross = sum(len(r['expert_refs']) > 1 for r in regions)
        single_tasks = sum(p['sources'] == 1 for r in regions for p in r['support_by_scope'].values())
    else:
        literals = sum(len(r['path']) + len(gate.rules[r['rule_ref']]['guards']) + len(gate.envelopes[r['rule_ref']]['conditions']) for r in regions)
        links = len(regions); cross = 0; single_tasks = sum(r['support']['sources'] == 1 for r in regions)
    return {'regions': len(regions), 'singleton_regions': sum(r['support']['sources'] == 1 for r in regions),
            'multi_batch_regions': sum(r['support']['batches'] > 1 for r in regions), 'cross_expert_regions': cross,
            'evidence_literal_occurrences': literals, 'task_scope_links': links, 'singleton_task_scope_links': single_tasks,
            'artifact_bytes': len(__import__('json').dumps(gate.export(), sort_keys=True, separators=(',', ':')).encode())}
