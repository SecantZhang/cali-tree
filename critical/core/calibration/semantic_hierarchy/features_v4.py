"""Label-blind role/kind distributions from authenticated M1 observations.

Keep partial proportions, explicit failures and uncertainty. None of these
observations is a mandatory label gate. No free text or object names escape.
"""
from ...decision.bound_evidence_v2 import derive_record, KINDS
from ...decision.artifacts import digest

VERSION = 'semantic-check-distributions-v4'
ROLES = ('outcome', 'identity', 'preservation', 'intermediate',
         'collateral_disappearance', 'collateral_deformation')
STATES = ('true', 'false', 'unknown', 'not_applicable')
SPECS = {}
for role in ROLES:
    for kind in ('all', *sorted(KINDS)):
        prefix = role + '_' + kind
        family = role.replace('_', ' ') + (' checks' if kind == 'all' else ' / ' + kind.replace('_', ' ') + ' checks')
        for n in (1, 2, 3):
            SPECS[prefix + '_count_ge_' + str(n)] = f'At least {n} {family} are present.'
        for state in STATES:
            for quantifier in ('any', 'majority', 'all'):
                SPECS[prefix + '_' + state + '_' + quantifier] = (
                    f'{quantifier.capitalize()} of the applicable family of {family} '
                    f'have direct desired-state {state}; an empty family is false.')
FEATURES = tuple(sorted(SPECS))
CONTRACT_REF = digest({'version': VERSION, 'specs': SPECS,
                       'state_semantics': 'M1 effective desired states, before dependency conjunction; separate role interactions are learned.'})


def validate_record(record):
    if record is None:
        return
    if not isinstance(record, dict) or set(record) != {'version', 'features'} or record['version'] != VERSION:
        raise ValueError('Invalid closed check-distribution record')
    f = record['features']
    if not isinstance(f, dict) or set(f) != set(FEATURES) or any(type(v) is not bool for v in f.values()):
        raise ValueError('Only declared semantic booleans are accepted')


def project(program, observation, pair_ref):
    if program is None or observation is None:
        return None
    # Validates exact questions, expected polarity, graph, and ordered image pair.
    bound = derive_record(program, observation, pair_ref)
    checks = list(bound['checks'].values()); values = {}
    for role in ROLES:
        for kind in ('all', *sorted(KINDS)):
            selected = [c for c in checks if c['role'] == role and (kind == 'all' or c['kind'] == kind)]
            n = len(selected); prefix = role + '_' + kind
            for threshold in (1, 2, 3):
                values[prefix + '_count_ge_' + str(threshold)] = n >= threshold
            for state in STATES:
                count = sum(c['desired_state'] == state for c in selected)
                values[prefix + '_' + state + '_any'] = count > 0
                values[prefix + '_' + state + '_majority'] = n > 0 and 2 * count > n
                values[prefix + '_' + state + '_all'] = n > 0 and count == n
    value = {'version': VERSION, 'features': values}
    validate_record(value)
    return value


def synthetic_record(**values):
    result = {'version': VERSION, 'features': dict.fromkeys(FEATURES, False)}
    result['features'].update(values); validate_record(result)
    return result
