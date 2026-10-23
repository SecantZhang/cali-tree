"""Conservative semantic-support filtering for the frozen v20 evidence gate.

Keep coarse semantic predicates that are constant over a region's local support.
This can only reject v20 acceptances; it never resolves an expert disagreement by
arbitrarily discarding one side. No new verdicts or case-signature lookup is fitted.
"""
from copy import deepcopy

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as base

VERSION = 'semantic-supported-evidence-coverage-v21'
SEMANTIC = tuple(sorted(k for k in base.SPECS if k.startswith('meaning_') and k != 'meaning_available'))
CONTRACT_REF = digest({'version': VERSION, 'base': base.CONTRACT_REF, 'features': {k: base.SPECS[k] for k in SEMANTIC},
                       'selection': 'All locally constant semantic predicates; monotone rejection only, retain base conflict abstentions.'})


def build(gate, rows, programs):
    base.validate_rows(rows)
    if set(programs) != {r['source_group'] for r in rows}:
        raise ValueError('Exact training program coverage required')
    values = {}
    for r in rows:
        if programs[r['source_group']]['instruction'] != r['instruction']:
            raise ValueError('Instruction/program mismatch')
        values[r['source_group']] = base.feature_values(programs[r['source_group']], r['features'])
    envelopes = {}
    for rule in gate.artifact['rules']:
        executor = gate.experts[rule['expert_ref']]
        cohort = [r for r in rows if values[r['source_group']] is not None
                  and all(values[r['source_group']][c['feature']] == c['value'] for c in rule['guards'])
                  and executor.predict_records([r['features']])[0]['prediction'] == rule['expert_prediction']]
        if len(cohort) < 2 or len({r['instruction'] for r in cohort}) < 2 or any(r['reference'] != rule['expert_prediction'] for r in cohort):
            raise ValueError('Invalid original support region')
        conditions = [{'feature': f, 'value': cohort[0]['features']['features'][f]} for f in SEMANTIC
                      if all(r['features']['features'][f] == cohort[0]['features']['features'][f] for r in cohort)]
        envelopes[digest(rule)] = {'conditions': conditions, 'sources': len(cohort),
                                  'instructions': len({r['instruction'] for r in cohort}),
                                  'batches': len({r['batch'] for r in cohort})}
    artifact = {'version': VERSION, 'contract_ref': CONTRACT_REF, 'base_gate': gate.export(), 'envelopes': envelopes}
    artifact['artifact_ref'] = digest(artifact)
    result = SupportedCoverageGate(artifact)
    for row in rows:
        p = programs[row['source_group']]
        before, after = gate.select(p, row['features']), result.select(p, row['features'])
        if (before['covered'], before['prediction']) != (after['covered'], after['prediction']):
            raise AssertionError('Semantic support filter lost local coverage or changed a verdict')
    return result


class SupportedCoverageGate:
    def __init__(self, artifact):
        if (set(artifact) != {'version', 'contract_ref', 'base_gate', 'envelopes', 'artifact_ref'}
                or artifact['version'] != VERSION or artifact['contract_ref'] != CONTRACT_REF
                or artifact['artifact_ref'] != digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})):
            raise ValueError('Changed semantic-support contract')
        self.base = base.EvidenceCoverageGate(artifact['base_gate'])
        if set(artifact['envelopes']) != {digest(r) for r in self.base.artifact['rules']}:
            raise ValueError('Incomplete semantic-support regions')
        for envelope in artifact['envelopes'].values():
            if (set(envelope) != {'conditions', 'sources', 'instructions', 'batches'}
                    or any(type(envelope[k]) is not int for k in ('sources', 'instructions', 'batches'))
                    or not 2 <= envelope['instructions'] <= envelope['sources']
                    or not 1 <= envelope['batches'] <= envelope['sources']):
                raise ValueError('Invalid semantic support counts')
            if len({c['feature'] for c in envelope['conditions']}) != len(envelope['conditions']):
                raise ValueError('Repeated support condition')
            for c in envelope['conditions']:
                if set(c) != {'feature', 'value'} or c['feature'] not in SEMANTIC or type(c['value']) is not bool:
                    raise ValueError('Undeclared semantic-support condition')
        self.artifact = deepcopy(artifact)

    def export(self):
        return deepcopy(self.artifact)

    def accepts_task(self, program):
        return self.base.accepts_task(program)

    def select(self, program, record):
        route = self.base.select(program, record)
        if not route['covered']:
            return route
        matches = [m for m in route['matches'] if all(record['features'][c['feature']] == c['value']
                   for c in self.artifact['envelopes'][m['rule_ref']]['conditions'])]
        if not matches:
            return {'covered': False, 'prediction': -1, 'reason': 'outside_semantic_support', 'matches': []}
        return {**route, 'reason': 'supported_expert_and_semantic_region', 'matches': matches}

    def select_bound(self, program, observation, pair_ref, interpretation):
        return self.select(program, base.project(program, observation, pair_ref, interpretation))
