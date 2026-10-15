"""Fixed, typed physical quantifiers; object strings and case IDs never escape."""
from copy import deepcopy

from ...decision.bound_evidence_v2 import derive_record, validate_program, KINDS
from ...decision.artifacts import digest

VERSION = 'semantic-physical-quantifiers-v1'
INTERACTIONS = {'grasp', 'contact', 'material_transfer', 'closure', 'orientation', 'separation'}
SCOPE_KINDS = ('presence', 'absence', 'attribute', 'spatial_relation', 'pose', 'contact', 'grasp',
               'material_transfer', 'orientation', 'closure', 'separation', 'count', 'style', 'background', 'other_physical')
SCOPES = tuple('requires_' + k for k in SCOPE_KINDS) + ('requires_identity', 'multiple_outcomes', 'multiple_requirements', 'dependent_outcomes')

# Directions are in desired physical truth, not in arbitrary numerical grades.
# Context features may test either truth value; evidence conditions only test true.
SPECS = {
    'all_requested_grounded': {'text': 'All requested outcomes, original-instance conditions, and necessary physical interactions are established with their dependencies.', 'role': 'core'},
    'all_outcomes_grounded': {'text': 'All requested physical outcome checks are established with their dependencies.', 'role': 'support'},
    'all_outcomes_direct': {'text': 'All requested physical outcome questions have direct affirmative desired evidence, before dependency qualification.', 'role': 'support'},
    'any_outcome_grounded': {'text': 'At least one requested physical outcome witness is established with its dependencies.', 'role': 'support'},
    'any_outcome_direct': {'text': 'At least one requested physical outcome question has direct affirmative desired evidence.', 'role': 'support'},
    'any_intermediate': {'text': 'A linked physical intermediate is observed, with its physical dependencies.', 'role': 'support'},
    'identity_compatible': {'text': 'Every applicable original-instance condition is established, or no such condition is required.', 'role': 'constraint'},
    'preservation_compatible': {'text': 'Every applicable preservation condition is established, or none is required.', 'role': 'constraint'},
    'appearance_preserved': {'text': 'Applicable preservation checks about appearance are established, or none is required.', 'role': 'constraint'},
    'layout_preserved': {'text': 'Applicable preservation checks about relative layout are established, or none is required.', 'role': 'constraint'},
    'structure_preserved': {'text': 'Applicable preservation checks about physical structure are established, or none is required.', 'role': 'constraint'},
    'no_unrelated_disappearance': {'text': 'No applicable collateral-disappearance question has an unmet desired state.', 'role': 'constraint'},
    'no_unrelated_deformation': {'text': 'No applicable collateral-deformation question has an unmet desired state.', 'role': 'constraint'},
}
for kind in SCOPE_KINDS:
    SPECS['all_' + kind + '_outcomes'] = {'text': 'Every requested ' + kind.replace('_', ' ') + ' outcome is established; absent families are not affirmative evidence.', 'role': 'support'}
    SPECS['any_' + kind + '_outcome'] = {'text': 'At least one requested ' + kind.replace('_', ' ') + ' outcome has direct affirmative desired evidence.', 'role': 'support'}
for name in SCOPES:
    SPECS[name] = {'text': 'Instruction-only structural flag: ' + name.replace('_', ' ') + '.', 'role': 'context'}
FEATURES = tuple(SPECS)
CONTRACT_REF = digest({'version': VERSION, 'specs': SPECS, 'scope_features': SCOPES})


def all_state(values, *, empty='not_applicable'):
    values = list(values)
    if not values:
        return empty
    if 'false' in values:
        return 'false'
    return 'true' if all(v == 'true' for v in values) else 'unknown'


def any_state(values):
    values = list(values)
    if not values:
        return 'not_applicable'
    if 'true' in values:
        return 'true'
    return 'false' if all(v == 'false' for v in values) else 'unknown'


def scope_record(program):
    validate_program(program)
    checks = program['checks']; outcomes = [c for c in checks if c['role'] == 'outcome']
    values = {'requires_' + kind: any(c['kind'] == kind for c in outcomes) for kind in SCOPE_KINDS}
    values.update(requires_identity=any(c['role'] == 'identity' for c in checks),
                  multiple_outcomes=len(outcomes) > 1, multiple_requirements=len(program['requirements']) > 1,
                  dependent_outcomes=any(c['dependencies'] for c in outcomes))
    return values


def project(program, observation, pair_ref):
    """Authenticate M1 data and expose only a closed semantic feature vocabulary."""
    if program is None or observation is None:
        return None
    r = derive_record(program, observation, pair_ref); checks = r['checks']; memo = {}
    def grounded(k):
        if k not in memo:
            c = checks[k]
            memo[k] = all_state([c['desired_state'], *(grounded(d) for d in c['dependencies'])])
        return memo[k]
    outcomes = [c for c in checks.values() if c['role'] == 'outcome']
    required = [c for c in checks.values() if c['role'] in ('outcome', 'identity') or c['role'] == 'preservation' and c['kind'] in INTERACTIONS]
    applicable = lambda role: [c for c in checks.values() if c['role'] == role and c['state'] != 'not_applicable']
    compatible = lambda rows: all_state((grounded(c['id']) for c in rows), empty='true')
    preservation = applicable('preservation')
    f = {'all_requested_grounded': all_state(grounded(c['id']) for c in required),
         'all_outcomes_grounded': all_state(grounded(c['id']) for c in outcomes),
         'all_outcomes_direct': all_state(c['desired_state'] for c in outcomes),
         'any_outcome_grounded': any_state(grounded(c['id']) for c in outcomes),
         'any_outcome_direct': any_state(c['desired_state'] for c in outcomes),
         'any_intermediate': any_state(grounded(c['id']) for c in applicable('intermediate')),
         'identity_compatible': compatible(applicable('identity')),
         'preservation_compatible': compatible(preservation),
         'appearance_preserved': compatible(c for c in preservation if c['kind'] == 'attribute'),
         'layout_preserved': compatible(c for c in preservation if c['kind'] == 'spatial_relation'),
         'structure_preserved': compatible(c for c in preservation if c['kind'] == 'other_physical'),
         'no_unrelated_disappearance': compatible(applicable('collateral_disappearance')),
         'no_unrelated_deformation': compatible(applicable('collateral_deformation'))}
    for kind in SCOPE_KINDS:
        selected = [c for c in outcomes if c['kind'] == kind]
        f['all_' + kind + '_outcomes'] = all_state(grounded(c['id']) for c in selected)
        f['any_' + kind + '_outcome'] = any_state(c['desired_state'] for c in selected)
    f.update({k: 'true' if v else 'false' for k, v in scope_record(program).items()})
    value = {'version': VERSION, 'features': f}
    validate_record(value); return value


def validate_record(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {'version', 'features'} or value['version'] != VERSION:
        raise ValueError('Only closed semantic feature records are accepted')
    f = value['features']
    if not isinstance(f, dict) or set(f) != set(FEATURES) or any(v not in ('true', 'false', 'unknown', 'not_applicable') for v in f.values()):
        raise ValueError('Unknown feature or physical state')
    if any(f[k] not in ('true', 'false') for k in SCOPES):
        raise ValueError('Instruction scope flags must be known booleans')


def synthetic_record(**overrides):
    """Logical test fixtures only; not a conversion of human quality grades."""
    f = dict.fromkeys(FEATURES, 'false'); f.update(overrides)
    value = {'version': VERSION, 'features': f}; validate_record(value); return value
