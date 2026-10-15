"""Qualify relocation multiplicity by instruction roles, not generic counts."""
from .intent_role_facts import PREDICATES as BASE,DIRECTIONS as BASE_DIRECTIONS,CONCEPTS as BASE_CONCEPTS,CORE,SUPPORT,compile_record as base_record
from .observable_facts import STATES

EXTRA={
 'relocation_duplicate_observed':'When the instruction compiler identifies original-instance relocation witnesses, does the evidence affirmatively show more recognizable target instances than in the source? Authorized addition is not this conflict.',
 'relocation_counterpart_contradicted':'For an instruction-selected original-instance relocation, do the observations explicitly deny both original displacement and a matching destination counterpart?'}
PREDICATES={**BASE,**EXTRA}
DIRECTIONS={**BASE_DIRECTIONS,**{k:-1 for k in EXTRA}}
CONCEPTS={k:tuple(dict.fromkeys((*v,*EXTRA))) for k,v in BASE_CONCEPTS.items()}


def semantic_priority(fact):
    if fact=='all_bound_postconditions_established':return 0
    if fact in ('all_positive_physical_assertions_established','requested_entity_attribute_conflict_observed',
        'requested_count_or_multiplicity_conflict_observed','relocation_duplicate_observed','relocation_counterpart_contradicted',
        'selected_original_source_persistence_observed','selected_destination_counterpart_failure_observed'):return 1
    if fact in ('a_required_positive_witness_visible','some_bound_postcondition_established','a_required_physical_test_undecidable'):return 2
    if fact in ('unrequested_deformation_observed','selected_external_collateral_change_visible'):return 3
    if fact in ('instruction_related_intermediate_witness','physical_support_without_bound_postcondition','supporting_physical_change_visible',
        'actor_limb_position_changed','arm_directed_toward_target','object_like_form_at_hand','source_vessel_tilted_toward_receiver',
        'closure_edges_approached','style_palette_or_texture_changed','orientation_end_geometry_reversed','requested_entity_fragment_visible'):return 5
    return 4


def compile_record(primitive,program,intermediate):
    value=base_record(primitive,program,intermediate)
    if value is None:return None
    selected=set(program['identity_witnesses']);f=primitive['facts']
    relocation=bool(selected&{'original_instance_displaced','original_instance_at_source','counterpart_at_destination'})
    return {'facts':{**value['facts'],'relocation_duplicate_observed':'true' if relocation and f['target_instance_count_increased']=='true' else 'false',
        'relocation_counterpart_contradicted':'true' if relocation and f['original_instance_displaced']=='false' and f['counterpart_at_destination']=='false' else 'false'}}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only instruction-role-qualified physical witnesses allowed')
