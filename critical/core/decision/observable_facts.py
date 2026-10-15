"""Instruction-bound observable predicates, without quality grades or verdicts."""
from pathlib import Path
from .compiler import TEXT,enum,object_schema
from .semantic_policy_executor import prose_observations

VERSION='operation-bound-observable-facts-v10'
TEMPLATE=Path(__file__).parents[1]/'prompts/templates/observable_facts_v10/extract.txt'
STATES=('true','false','not_applicable','unknown')
PREDICATES={
 'target_result_visible':'Can the intended edited target or its corresponding result be located and inspected in the edited view?',
 'original_instance_at_source':'For relocation/removal, is the original intended instance still visible at its original source location?',
 'counterpart_at_destination':'For relocation, is an object matching the intended target present at the requested destination?',
 'original_instance_displaced':'For relocation, do stable identifying details establish displacement of the original instance relative to the source?',
 'requested_direction_change':'For a comparative move, does source-to-edit comparison show displacement in the requested direction or reduced relevant separation?',
 'requested_spatial_relation':'Does the edited arrangement visibly satisfy the specific requested left/right/front/behind/on/under/closer relation?',
 'target_instance_count_increased':'Is the number of recognizable intended-target instances greater after the edit than in the source?',
 'explicit_count_matches':'If an exact count is requested, does the visible result have that count?',
 'requested_attribute_visible':'Is the requested color/material/surface property visibly present on the intended target?',
 'contradictory_attribute_remains':'Does a visible portion of the intended target retain an attribute that contradicts the requested attribute change?',
 'target_structure_changed':'Does the intended object have changed construction or structural shape beyond the explicitly requested property/pose transformation?',
 'orientation_landmarks_match':'For orientation, do identifiable top/base/cap/axis landmarks support the requested inversion or rotation?',
 'closure_gap_visible':'For a closure request, is an opening, separated front edge, or unsecured projecting panel still visibly present?',
 'requested_closure_configuration':'For a closure request, do the visible edges/panels establish the specifically requested fully closed or partly closed configuration?',
 'disconnected_pieces_visible':'For tearing/separation, are physically disconnected portions of the original material visible?',
 'contents_in_receiving_container':'For pouring/transfer, are transferred contents visibly in the receiving container or visibly entering it from the source?',
 'hand_target_contact_visible':'For a hand/object interaction, is physical contact with the intended object visible rather than mere approach?',
 'hand_supports_or_grasps_target':'For pickup/grasp/carry, does a visible hand coherently grip or support the intended object rather than merge into an ambiguous shape?',
 'requested_actor_pose_visible':'For a requested actor action/pose/gaze, are the specific observable limb/hand/gaze arrangements present? Bind this to a concrete physical test.',
 'added_entity_recognizable':'For addition, is a newly introduced entity of the requested kind recognizable in the edited image?',
 'specified_entity_attribute_conflict':'Does the edited intended entity visibly conflict with an explicitly specified descriptive attribute, including same-type appearance relative to the source?',
 'requested_removal_absent':'For removal/blanking, is the specifically targeted original entity/content no longer visible?',
 'requested_style_structure_visible':'For style, are distinctive structural visual devices of the requested style evident, beyond related colors or generic texture?',
 'original_style_still_visible':'For a requested style transformation, do substantial recognizable portions still retain the source visual style?',
 'setting_specific_cues_visible':'For a background/setting change, are concrete objects or environmental phenomena identifying that requested setting visible?',
 'original_background_still_visible':'For a background replacement, do substantial original setting-specific background elements remain visible?',
 'source_subject_layout_retained':'Do the original main subject and scene layout remain recognizable under the authorized edit?',
 'unrequested_entity_missing':'Has a distinct source entity unrelated to the requested change disappeared?',
 'unrequested_entity_deformed':'Is a distinct unrelated source entity visibly deformed or structurally altered?',
 'target_markings_or_size_changed':'Have distinctive markings, proportions, or size of the intended target changed beyond the requested transformation?'}
FACT=object_schema({'state':enum(STATES),'bound_question':TEXT,'evidence':TEXT})
SCHEMA=object_schema({'facts':object_schema({k:FACT for k in PREDICATES})})


def validate(value):
    if not isinstance(value,dict) or set(value)!={'facts'} or not isinstance(value['facts'],dict) or set(value['facts'])!=set(PREDICATES):raise ValueError('Exact observable predicate bank required')
    for f in value['facts'].values():
        if (not isinstance(f,dict) or set(f)!={'state','bound_question','evidence'} or f['state'] not in STATES
            or any(not isinstance(f[k],str) or not f[k].strip() for k in ('bound_question','evidence'))):raise ValueError('Invalid grounded fact')
    return value


def fact_record(value):
    validate(value)
    return {'facts':{k:f['state'] for k,f in value['facts'].items()}}


class ObservableFactExtractor:
    def __init__(self,calls):self.calls=calls
    def extract(self,instruction,observations,*,case_id=None,max_tokens=16384):
        kwargs={'case_id':case_id} if case_id is not None else {}
        value,ref=self.calls.call('observable_facts_v10',{'instruction':instruction,'predicate_bank':PREDICATES,
            'observations':prose_observations(observations)},SCHEMA,template=TEMPLATE.read_text(),slot='once',max_tokens=max_tokens,**kwargs)
        validate(value);return {'observations':value,'execution_ref':ref,'version':VERSION}
