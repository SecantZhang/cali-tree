"""Role-qualified identity facts: source persistence versus appearance drift."""
from .role_bound_witnesses import PREDICATES as BASE,DIRECTIONS as BASE_DIRECTIONS,CONCEPTS as BASE_CONCEPTS,CORE,SUPPORT,compile_record as base_record
from .observable_facts import STATES

EXCLUDED={'selected_identity_caution_visible','target_structure_changed','target_markings_or_size_changed','specified_entity_attribute_conflict'}
IDENTITY={
 'selected_original_source_persistence_observed':'Does an instruction-selected original-instance witness affirmatively show the original target remaining at its source location? This is distinct from changed appearance.',
 'selected_destination_counterpart_failure_observed':'Does an instruction-selected destination counterpart test have explicit contrary evidence? Descriptive appearance differences alone are not this fact.'}
PREDICATES={**{k:v for k,v in BASE.items() if k not in EXCLUDED},**IDENTITY}
DIRECTIONS={**{k:v for k,v in BASE_DIRECTIONS.items() if k in PREDICATES},**{k:-1 for k in IDENTITY}}
CONCEPTS={k:tuple(dict.fromkeys((*(name for name in v if name in PREDICATES),*IDENTITY))) for k,v in BASE_CONCEPTS.items()}


def compile_record(primitive,program,intermediate):
    value=base_record(primitive,program,intermediate)
    if value is None:return None
    selected=program['identity_witnesses'];f=primitive['facts']
    persistence='original_instance_at_source' in selected and f['original_instance_at_source']=='true'
    counterpart='counterpart_at_destination' in selected and f['counterpart_at_destination']=='false'
    return {'facts':{**{k:v for k,v in value['facts'].items() if k not in EXCLUDED},
       'selected_original_source_persistence_observed':'true' if persistence else 'false',
       'selected_destination_counterpart_failure_observed':'true' if counterpart else 'false'}}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only intent-role-qualified physical facts allowed')
