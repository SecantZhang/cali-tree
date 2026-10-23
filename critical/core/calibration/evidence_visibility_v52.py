"""Retain bound source/view confidence as closed, duplicate-invariant predicates."""
from ..decision.bound_evidence_v2 import derive_record, ROLES
from ..decision.artifacts import digest

VERSION = 'bound-evidence-visibility-v52'
FIELDS = {'source_anchor': ('identified', 'ambiguous', 'not_found', 'not_needed'),
          'edited_coverage': ('adequate', 'occluded', 'cropped', 'unclear', 'not_needed'),
          'applicability': ('applicable', 'not_applicable', 'unknown')}
COUPLINGS = ('desired_true_source_ambiguous', 'desired_false_source_ambiguous', 'desired_unknown_source_identified',
             'desired_true_view_inadequate', 'desired_false_view_inadequate', 'desired_unknown_view_adequate',
             'desired_true_well_observed', 'desired_false_well_observed', 'desired_unknown_well_observed')
SPECS = {'visibility_available': 'Valid source anchoring, edited-view coverage and applicability observations are available.'}
for role in ROLES:
    for field, options in FIELDS.items():
        for option in options:
            for quantifier in ('any', 'all'):
                SPECS[f'visibility_{role}_{field}_{option}_{quantifier}'] = f'{quantifier} nonempty {role} checks have {field}={option}.'
    for coupling in COUPLINGS:
        SPECS[f'visibility_{role}_{coupling}_any'] = f'At least one {role} check has {coupling}; desired state is instruction-polarity normalized.'
CONTRACT_REF = digest({'version': VERSION, 'specs': SPECS,
                       'prohibited': 'Check counts, majority votes, raw text, object names, check/case/source IDs, hashes and coordinates as predictors.',
                       'aggregation': 'Non-vacuous any/all over bound categorical observations. Identical duplicate observations do not change predicates.'})


def project(program, observation, pair_ref):
    if program is None or observation is None:
        return None
    bound = derive_record(program, observation, pair_ref)
    values = dict.fromkeys(SPECS, False)
    values['visibility_available'] = True
    for role in ROLES:
        rows = [c for c in bound['checks'].values() if c['role'] == role]
        for field, options in FIELDS.items():
            for option in options:
                matches = [c['observation'][field] == option for c in rows]
                values[f'visibility_{role}_{field}_{option}_any'] = any(matches)
                values[f'visibility_{role}_{field}_{option}_all'] = bool(matches) and all(matches)
        for c in rows:
            state, obs = c['desired_state'], c['observation']
            ambiguous = obs['source_anchor'] in ('ambiguous', 'not_found')
            inadequate = obs['edited_coverage'] in ('occluded', 'cropped', 'unclear')
            well_observed = obs['source_anchor'] in ('identified', 'not_needed') and obs['edited_coverage'] in ('adequate', 'not_needed') and obs['applicability'] == 'applicable'
            conditions = {'desired_true_source_ambiguous': state == 'true' and ambiguous,
                          'desired_false_source_ambiguous': state == 'false' and ambiguous,
                          'desired_unknown_source_identified': state == 'unknown' and obs['source_anchor'] == 'identified',
                          'desired_true_view_inadequate': state == 'true' and inadequate,
                          'desired_false_view_inadequate': state == 'false' and inadequate,
                          'desired_unknown_view_adequate': state == 'unknown' and obs['edited_coverage'] == 'adequate',
                          **{f'desired_{s}_well_observed': state == s and well_observed for s in ('true', 'false', 'unknown')}}
            for name, truth in conditions.items():
                values[f'visibility_{role}_{name}_any'] |= truth
    assert set(values) == set(SPECS) and all(type(v) is bool for v in values.values())
    return {'version': VERSION, 'features': values}
