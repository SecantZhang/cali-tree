"""Reuse retained hierarchy children to complete supported local coverage."""
from copy import deepcopy

from ..decision.artifacts import digest
from . import evidence_coverage_v20 as base
from . import evidence_support_v21 as supported

VERSION = 'hierarchical-coverage-completion-v22'


def complete(gate, models, rows, programs):
    base.validate_rows(rows)
    before = [gate.select(programs[r['source_group']], r['features']) for r in rows]
    missing = {i for i, route in enumerate(before) if not route['covered']}
    if not missing:
        return supported.build(gate, rows, programs), {'version': VERSION, 'additional_search': False,
                                                     'added_regions': [], 'uncovered_local_sources': 0}
    candidates, fit = base.build(models, rows, programs, base.Config(**gate.artifact['config']))
    artifact = gate.export(); existing = {digest(r) for r in artifact['rules']}; added = []
    while missing:
        options = []
        for rule in candidates.artifact['rules']:
            if digest(rule) in existing:
                continue
            covered = set()
            executor = candidates.experts[rule['expert_ref']]
            for i in missing:
                row = rows[i]; values = base.feature_values(programs[row['source_group']], row['features'])
                if (values is not None and all(values[c['feature']] == c['value'] for c in rule['guards'])
                        and executor.predict_records([row['features']])[0]['prediction'] == rule['expert_prediction']):
                    covered.add(i)
            if covered:
                options.append((rule, covered))
        if not options or len(artifact['rules']) >= artifact['config']['max_rules']:
            break
        rule, covered = min(options, key=lambda item: (-len(item[1]), len(item[0]['guards']),
                                                      -item[0]['support']['batches'], digest(item[0])))
        artifact['rules'].append(deepcopy(rule)); existing.add(digest(rule)); missing -= covered
        ref = rule['expert_ref']; artifact['experts'][ref] = candidates.experts[ref].metadata()
        added.append({'rule_ref': digest(rule), 'expert_ref': ref, 'newly_covered': len(covered), 'support': rule['support']})
    artifact['rules'].sort(key=digest)
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    merged = base.EvidenceCoverageGate(artifact); result = supported.build(merged, rows, programs)
    for row, previous in zip(rows, before):
        actual = result.select(programs[row['source_group']], row['features'])
        if actual['covered'] and actual['prediction'] != row['reference']:
            raise AssertionError('Hierarchy completion introduced a local error')
        if previous['covered'] and (not actual['covered'] or actual['prediction'] != previous['prediction']):
            raise AssertionError('Hierarchy completion regressed a previously covered local case')
    return result, {'version': VERSION, 'additional_search': True, 'candidate_search': {k: v for k, v in fit.items() if k != 'training'},
                    'added_regions': added, 'uncovered_local_sources': sum(not result.select(programs[r['source_group']], r['features'])['covered'] for r in rows)}
