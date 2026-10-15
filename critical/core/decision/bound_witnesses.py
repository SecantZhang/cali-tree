"""Quantified physical-witness conditions over instruction-bound postconditions.

These are exact properties of a concrete proposition program and its evidence,
not grades for overall editing quality or degrees of satisfaction.
"""
from .observable_facts import PREDICATES as PRIMITIVES,STATES
from ..calibration.factual_rules import DIRECTIONS as PRIMITIVE_DIRECTIONS,CONCEPTS as PRIMITIVE_CONCEPTS

DERIVED={
 'all_bound_postconditions_established':'For EVERY physical postcondition compiled from the instruction, does each required-present witness have affirmative evidence and each required-absent conflict have contrary evidence? Expand the bound physical tests to interpret this condition.',
 'some_bound_postcondition_established':'Is at least one complete instruction-bound physical postcondition established by all of its required affirmative/contrary witnesses?',
 'a_required_positive_witness_visible':'Is affirmative evidence available for at least one specific physical witness required by the instruction-bound program?',
 'a_forbidden_physical_condition_visible':'Is a physical condition that the bound instruction requires to be absent actually observed?',
 'a_required_physical_condition_contradicted':'Is contrary evidence recorded for a specific physical witness that the bound instruction requires?',
 'a_required_physical_test_undecidable':'Is a required physical test unknown or missing applicable evidence in the cached observations?',
 'supporting_physical_change_visible':'Is a concrete motion, contact, pose, attribute, introduced entity, style structure or setting cue identified as supporting evidence by the instruction program visibly established? Mere target visibility does not count.',
 'original_and_destination_instances_both_visible':'For a relocation, is the original at its source AND a recognizable counterpart at the requested destination both affirmatively observed?',
 'selected_identity_motion_witness_visible':'Does the instruction program identify a relocation/counterpart witness and the evidence affirmatively establish that specific witness?',
 'selected_identity_caution_visible':'Does a selected identity witness record the original remaining at its source, or unrequested changes to target markings/size/structure?',
 'selected_external_collateral_change_visible':'Do selected collateral witnesses establish a missing or deformed unrelated entity, or lost recognizable original subject/layout?',
 'requested_attribute_with_visible_residual':'Does the bound program require an attribute and absence of a contrary residual, while the evidence shows both the requested attribute and the contrary residual?',
 'physical_support_without_bound_postcondition':'Is concrete supporting physical change witnessed while no complete instruction-bound postcondition is established?',
 'all_bound_postconditions_contradicted':'Does every bound physical postcondition contain at least one explicitly contrary required witness or an explicitly observed forbidden condition?'}
PREDICATES={**PRIMITIVES,**DERIVED}
DIRECTIONS={**PRIMITIVE_DIRECTIONS,
 'all_bound_postconditions_established':1,'some_bound_postcondition_established':1,'a_required_positive_witness_visible':1,
 'a_forbidden_physical_condition_visible':-1,'a_required_physical_condition_contradicted':-1,
 'a_required_physical_test_undecidable':-1,'supporting_physical_change_visible':1,
 'original_and_destination_instances_both_visible':-1,'selected_identity_motion_witness_visible':1,
 'selected_identity_caution_visible':-1,'selected_external_collateral_change_visible':-1,
 'requested_attribute_with_visible_residual':-1,'all_bound_postconditions_contradicted':-1}
CONCEPTS={k:tuple(dict.fromkeys((*v,*DERIVED))) for k,v in PRIMITIVE_CONCEPTS.items()}
MOTION={'original_instance_displaced','counterpart_at_destination'}
CAUTIONS={'original_instance_at_source','target_structure_changed','target_markings_or_size_changed'}
SUPPORT={'original_instance_displaced','requested_direction_change','requested_attribute_visible','orientation_landmarks_match',
 'requested_closure_configuration','disconnected_pieces_visible','contents_in_receiving_container','hand_target_contact_visible',
 'hand_supports_or_grasps_target','requested_actor_pose_visible','added_entity_recognizable','requested_removal_absent',
 'requested_style_structure_visible','setting_specific_cues_visible'}


def compile_record(primitive,program):
    if primitive is None or program is None:return None
    f=primitive['facts'];requirements=program['postconditions']
    established=[];contradicted=[];positive=[];forbidden=[];unknown=[]
    for p in requirements:
        checks=[f[k]=='true' for k in p['required_present']]+[f[k]=='false' for k in p['required_absent']]
        established.append(all(checks))
        contradicted.append(any(f[k]=='false' for k in p['required_present']) or any(f[k]=='true' for k in p['required_absent']))
        positive.extend(f[k]=='true' for k in p['required_present']);forbidden.extend(f[k]=='true' for k in p['required_absent'])
        unknown.extend(f[k] in ('unknown','not_applicable') for k in p['required_present']+p['required_absent'])
    support=any(f[k]=='true' for k in program['supporting_witnesses'] if k in SUPPORT)
    identity=program['identity_witnesses'];collateral=program['collateral_witnesses']
    selected_collateral=any(f[k]=='true' for k in collateral if k in ('unrequested_entity_missing','unrequested_entity_deformed'))
    selected_collateral|='source_subject_layout_retained' in collateral and f['source_subject_layout_retained']=='false'
    residual=any('requested_attribute_visible' in p['required_present'] and 'contradictory_attribute_remains' in p['required_absent'] for p in requirements)
    values={
       'all_bound_postconditions_established':all(established),'some_bound_postcondition_established':any(established),
       'a_required_positive_witness_visible':any(positive),'a_forbidden_physical_condition_visible':any(forbidden),
       'a_required_physical_condition_contradicted':any(contradicted),'a_required_physical_test_undecidable':any(unknown),
       'supporting_physical_change_visible':support,
       'original_and_destination_instances_both_visible':'original_instance_at_source' in identity and f['original_instance_at_source']=='true' and f['counterpart_at_destination']=='true',
       'selected_identity_motion_witness_visible':any(f[k]=='true' for k in identity if k in MOTION),
       'selected_identity_caution_visible':any(f[k]=='true' for k in identity if k in CAUTIONS),
       'selected_external_collateral_change_visible':bool(selected_collateral),
       'requested_attribute_with_visible_residual':residual and f['requested_attribute_visible']=='true' and f['contradictory_attribute_remains']=='true',
       'physical_support_without_bound_postcondition':support and not any(established),
       'all_bound_postconditions_contradicted':all(contradicted)}
    return {'facts':{**f,**{k:'true' if bool(v) else 'false' for k,v in values.items()}}}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only physical predicates and exact bound-witness propositions allowed')
