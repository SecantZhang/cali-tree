"""Explicit task-and-evidence regions over an existing mixed judge bank.

Instruction-only shortlisting never establishes decision coverage. The frozen
full-bank gate remains a veto so pruning candidates cannot erase disagreements.
"""
from copy import deepcopy

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as evidence
from . import merge_route_support_v24 as previous
from ..optimization.prompt.calitree.task_coverage import task_scope, _validate_scope, LABELS

VERSION = 'semantic-rule-regions-v26'
CONTRACT = digest({'version': VERSION, 'features': evidence.CONTRACT_REF,
                   'region': 'exact structural task scope AND frozen rule AND reached terminal path',
                   'selection': 'frozen full-bank gate veto, then require supported region; never introduce acceptance or verdict'})


def describe(scope, prediction):
    outcomes = ', '.join(f"{kind} ({'required' if state == 'true' else 'must be absent/false'})" for kind, state in scope['outcomes'])
    return (f"{'Compound' if scope['compound'] else 'Single-requirement'} task: {outcomes}; "
            f"identity {'required' if scope['identity_required'] else 'not required'}; "
            f"conditional verdict: {LABELS[prediction]}.")


def region_key(rule_ref, scope, trace):
    return digest([rule_ref, scope, trace])


def build(gate, rows, programs):
    evidence.validate_rows(rows)
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Exact local program coverage required')
    groups = {}
    for row in rows:
        program = programs[row['source_group']]
        if program['instruction'] != row['instruction']:
            raise ValueError('Instruction/program mismatch')
        route = gate.select(program, row['features'])
        if not route['covered']:
            continue
        if route['prediction'] != row['reference']:
            raise ValueError('Cannot assign a trusted region to an incorrect local acceptance')
        scope = task_scope(program)
        for match in route['matches']:
            key = region_key(match['rule_ref'], scope, match['trace'])
            entry = groups.setdefault(key, {'rule_ref': match['rule_ref'], 'expert_ref': match['expert_ref'],
                      'scope': scope, 'path': match['trace'], 'prediction': match['prediction'],
                      'sources': set(), 'instructions': set(), 'batches': set()})
            entry['sources'].add(row['source_group']); entry['instructions'].add(row['instruction']); entry['batches'].add(row['batch'])
    regions = []
    for key, value in sorted(groups.items()):
        region = {k: deepcopy(value[k]) for k in ('rule_ref', 'expert_ref', 'scope', 'path', 'prediction')}
        region.update(region_ref=key, description=describe(value['scope'], value['prediction']),
                      support={k: len(value[k]) for k in ('sources', 'instructions', 'batches')})
        regions.append(region)
    if not regions:
        raise ValueError('No correctly supported local regions')
    artifact = {'version': VERSION, 'contract_ref': CONTRACT, 'previous_gate': gate.export(), 'regions': regions}
    artifact['artifact_ref'] = digest(artifact)
    result = SemanticRegionGate(artifact)
    for row in rows:
        program = programs[row['source_group']]
        before, after = gate.select(program, row['features']), result.select(program, row['features'])
        if (before['covered'], before['prediction']) != (after['covered'], after['prediction']):
            raise AssertionError('Semantic regions lost local coverage')
    return result


class SemanticRegionGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'contract_ref', 'previous_gate', 'regions', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['contract_ref'] != CONTRACT
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Invalid semantic region artifact')
        self.previous = previous.restore(artifact['previous_gate'])
        semantic = previous.core_artifact(self.previous)['previous_gate']
        self.rules = {digest(r): r for r in semantic['base_gate']['rules']}
        self.envelopes = semantic['envelopes']
        self.experts = {ref: evidence.PortableRuleExecutor(model) for ref, model in semantic['base_gate']['experts'].items()}
        self.by_scope = {}; self.regions = {}
        for r in artifact['regions']:
            if set(r) != {'region_ref', 'rule_ref', 'expert_ref', 'scope', 'path', 'prediction', 'description', 'support'}:
                raise ValueError('Invalid semantic region fields')
            _validate_scope(r['scope'])
            rule = self.rules.get(r['rule_ref'])
            if (rule is None or r['expert_ref'] != rule['expert_ref'] or r['prediction'] != rule['expert_prediction']
                    or r['region_ref'] != region_key(r['rule_ref'], r['scope'], r['path'])
                    or r['region_ref'] in self.regions or r['description'] != describe(r['scope'], r['prediction'])):
                raise ValueError('Changed region identity or rule binding')
            tree = self.experts[r['expert_ref']].artifact['tree']
            for condition in r['path']:
                if (set(condition) != {'feature', 'value'} or condition['feature'] != tree.get('feature')
                        or type(condition['value']) is not bool):
                    raise ValueError('Region path is not an exact expert path')
                tree = tree['true' if condition['value'] else 'false']
            if 'feature' in tree or tree.get('prediction') != r['prediction']:
                raise ValueError('Region path does not reach the declared verdict')
            counts = r['support']
            if (set(counts) != {'sources', 'instructions', 'batches'}
                    or any(type(v) is not int or v < 1 for v in counts.values())
                    or counts['instructions'] > counts['sources'] or counts['batches'] > counts['sources']):
                raise ValueError('Invalid region support counts')
            self.regions[r['region_ref']] = deepcopy(r)
            self.by_scope.setdefault(digest(r['scope']), []).append(r['region_ref'])
        if not self.regions:
            raise ValueError('Empty semantic region bank')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def shortlist(self, program):
        """Task routing only: candidates are not permission to trust a verdict."""
        try:
            refs = self.by_scope.get(digest(task_scope(program)), [])
        except (ValueError, TypeError, KeyError):
            refs = []
        return {'task_supported': bool(refs), 'decision_ready': False,
                'region_refs': list(refs), 'expert_refs': sorted({self.regions[r]['expert_ref'] for r in refs})}

    def accepts_task(self, program):
        return self.shortlist(program)['task_supported']

    def definition(self, ref):
        r = self.regions[ref]; rule = self.rules[r['rule_ref']]
        def explain(conditions):
            return [{**c, 'description': evidence.FEATURES[c['feature']]} for c in conditions]
        return {**deepcopy(r), 'expert_path': explain(r['path']), 'evidence_guards': explain(rule['guards']),
                'semantic_support': explain(self.envelopes[r['rule_ref']]['conditions']),
                'trust_requires': 'All region conditions, full-bank agreement and every frozen rejection check.'}

    def select(self, program, record):
        candidates = self.shortlist(program)
        original = self.previous.select(program, record)
        if not original['covered']:
            return {**original, 'semantic_candidates': candidates, 'semantic_regions': []}
        found = []
        for match in original['matches']:
            ref = region_key(match['rule_ref'], task_scope(program), match['trace'])
            if ref in candidates['region_refs']:
                found.append(ref)
        if not found:
            return {'covered': False, 'prediction': -1, 'reason': 'outside_semantic_rule_regions', 'matches': [],
                    'semantic_candidates': candidates, 'semantic_regions': []}
        refs = set(found)
        return {**original, 'reason': 'supported_semantic_rule_region',
                'matches': [m for m in original['matches'] if region_key(m['rule_ref'], task_scope(program), m['trace']) in refs],
                'semantic_candidates': candidates, 'semantic_regions': sorted(refs)}

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, evidence.project(program, observation, pair_ref, interpretation))
