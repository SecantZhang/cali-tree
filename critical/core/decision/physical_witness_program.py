"""Physical postconditions plus intermediate witnesses, with explicit proof status."""
from .bound_witnesses import PREDICATES as BOUND_PREDICATES,DIRECTIONS as BOUND_DIRECTIONS,CONCEPTS as BOUND_CONCEPTS,compile_record as bound_record
from .intermediate_facts import PREDICATES as INTERMEDIATES
from .observable_facts import STATES

EXTRA={
 'all_positive_physical_assertions_established':'Does every instruction-bound affirmative physical test have direct affirmative evidence? Negative/absence constraints are evaluated separately, so this does not assert their fulfillment.',
 'unrequested_deformation_observed':'Do the cached observations affirmatively establish a deformation of a distinct unrelated entity? Unknown is lack of a recorded deformation witness, not a claim that no deformation occurred.',
 'unrequested_disappearance_observed':'Do the observations affirmatively establish disappearance of a distinct unrelated entity?',
 'instruction_related_intermediate_witness':'Is a concrete approach/contact/tilt/edge-motion/style-treatment/end-reversal/entity-fragment witness tied to the requested operation visible, even when its terminal postcondition is not established? Limb motion alone is insufficient.'}
PREDICATES={**BOUND_PREDICATES,**INTERMEDIATES,**EXTRA}
DIRECTIONS={**BOUND_DIRECTIONS,**{k:1 for k in INTERMEDIATES},
    'all_positive_physical_assertions_established':1,'unrequested_deformation_observed':-1,
    'unrequested_disappearance_observed':-1,'instruction_related_intermediate_witness':1}
CONCEPTS={k:tuple(dict.fromkeys((*v,*EXTRA,*INTERMEDIATES))) for k,v in BOUND_CONCEPTS.items()}
CORE={
 'all_bound_postconditions_established','some_bound_postcondition_established','a_required_positive_witness_visible',
 'all_positive_physical_assertions_established','requested_direction_change','requested_spatial_relation','requested_attribute_visible',
 'orientation_landmarks_match','requested_closure_configuration','disconnected_pieces_visible','contents_in_receiving_container',
 'hand_supports_or_grasps_target','requested_actor_pose_visible','added_entity_recognizable','requested_removal_absent',
 'requested_style_structure_visible','setting_specific_cues_visible'}
SUPPORT=CORE|{'supporting_physical_change_visible','physical_support_without_bound_postcondition',
    'instruction_related_intermediate_witness','arm_directed_toward_target','object_like_form_at_hand',
    'source_vessel_tilted_toward_receiver','closure_edges_approached','style_palette_or_texture_changed',
    'orientation_end_geometry_reversed','requested_entity_fragment_visible','hand_target_contact_visible'}


def compile_record(primitive,program,intermediate):
    if primitive is None or program is None or intermediate is None:return None
    bound=bound_record(primitive,program);f=primitive['facts'];mid=intermediate['facts']
    positive={k for p in program['postconditions'] for k in p['required_present']}
    intermediate_witness=any(mid[k]=='true' for k in INTERMEDIATES if k!='actor_limb_position_changed')
    intermediate_witness|=mid['actor_limb_position_changed']=='true' and f['hand_target_contact_visible']=='true'
    values={'all_positive_physical_assertions_established':bool(positive) and all(f[k]=='true' for k in positive),
        'unrequested_deformation_observed':f['unrequested_entity_deformed']=='true',
        'unrequested_disappearance_observed':f['unrequested_entity_missing']=='true',
        'instruction_related_intermediate_witness':intermediate_witness}
    return {'facts':{**bound['facts'],**mid,**{k:'true' if v else 'false' for k,v in values.items()}}}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only bound physical assertions and witnesses allowed')
