"""Facet-progress and faithful-completion policy reconstructed from fit examples."""
from .artifacts import digest

FIELDS = {
    'new_requested_content': ('none', 'some', 'uncertain'),
    'all_material_facets': ('yes', 'no', 'uncertain'),
    'operation_fidelity': ('faithful', 'unfaithful', 'uncertain'),
    'source_entity_fidelity': ('preserved', 'incidental_change', 'material_unrequested_change', 'uncertain'),
    'scope_coverage': ('full', 'partial', 'not_applicable', 'uncertain'),
}
VERSION = 'new-subgoal-faithful-endpoint-v150'


def schema():
    properties = {n: {'type': 'string', 'enum': list(states)} for n, states in FIELDS.items()}
    properties.update(evidence={'type': 'string', 'minLength': 1, 'maxLength': 400},
                      material_gap={'type': 'string', 'minLength': 1, 'maxLength': 220})
    return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}


def validate(value):
    if not isinstance(value, dict) or set(value) != set(schema()['properties']):
        raise ValueError('Closed requested-facet record required')
    for name, states in FIELDS.items():
        if value[name] not in states:
            raise ValueError('Unknown facet state: '+name)
    for name, cap in (('evidence', 400), ('material_gap', 220)):
        if not isinstance(value[name], str) or not value[name].strip() or len(value[name]) > cap:
            raise ValueError('Bounded explicit facet evidence required')
    return value


def decide(value, *, cautious=False):
    """Return a grade or None; unknown content never becomes an invented grade."""
    v = validate(value)
    if v['new_requested_content'] == 'none':
        return None if v['all_material_facets'] == 'yes' else 0
    if v['new_requested_content'] == 'uncertain':
        return None
    full = (v['all_material_facets'] == 'yes' and v['operation_fidelity'] == 'faithful' and
            v['source_entity_fidelity'] in ('preserved', 'incidental_change') and
            v['scope_coverage'] in ('full', 'not_applicable'))
    if full:
        return 2
    gap = (v['all_material_facets'] == 'no' or v['operation_fidelity'] == 'unfaithful' or
           v['source_entity_fidelity'] == 'material_unrequested_change' or v['scope_coverage'] == 'partial')
    return 1 if gap or cautious else None


CONTRACT_REF = digest({'version': VERSION, 'schema': schema(),
    'policy': 'No newly realized requested facet -> No; some meaningful facet plus established material gap/unfaithful operation -> Partial; all facets, faithful operation and scope with no material unrequested entity change -> Yes. Uncertain evidence defers.',
    'cautious_ablation': 'Some established requested content with unknown completion may map to Partial in the declared cautious readout.'})
