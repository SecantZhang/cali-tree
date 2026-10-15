"""Physical intermediate configurations, distinct from requested terminal states."""
from pathlib import Path
from .compiler import TEXT,enum,object_schema
from .semantic_policy_executor import prose_observations

VERSION='physical-intermediate-witnesses-v13'
TEMPLATE=Path(__file__).parents[1]/'prompts/templates/intermediate_facts_v13/extract.txt'
PREDICATES={
 'actor_limb_position_changed':'For an actor action, do source/edit observations establish that the relevant arm, hand, body, or gaze configuration changed?',
 'arm_directed_toward_target':'For an intended hand/object interaction, is the arm or hand visibly raised, extended, or redirected toward the intended target?',
 'object_like_form_at_hand':'For grasp/pickup, is a target-category object-like form visible at the hand/arm end even when a coherent grasp cannot be identified?',
 'source_vessel_tilted_toward_receiver':'For pouring, is the source container visibly tilted or positioned toward the receiving container, irrespective of whether transferred contents are visible?',
 'closure_edges_approached':'For closing, does source/edit comparison show the relevant fronts/edges moving toward the requested configuration, even if a gap remains?',
 'style_palette_or_texture_changed':'For a requested style transformation, is the palette, surface texture, or brush/line treatment visibly changed, independently of whether characteristic style structure is established?',
 'orientation_end_geometry_reversed':'For inversion, do upper/lower end shapes visibly change order in the requested way, even if distinctive cap/base identity is uncertain?',
 'requested_entity_fragment_visible':'For addition, is a shape or fragment related to the requested entity visible even when the whole entity is not recognizable?'}
FACT=object_schema({'state':enum(('true','false','not_applicable','unknown')),'bound_question':TEXT,'evidence':TEXT})
SCHEMA=object_schema({'facts':object_schema({k:FACT for k in PREDICATES})})


def validate(value):
    if not isinstance(value,dict) or set(value)!={'facts'} or not isinstance(value['facts'],dict) or set(value['facts'])!=set(PREDICATES):raise ValueError('Exact physical intermediate fact bank required')
    for f in value['facts'].values():
        if not isinstance(f,dict) or set(f)!={'state','bound_question','evidence'} or f['state'] not in ('true','false','not_applicable','unknown') or any(not isinstance(f[k],str) or not f[k].strip() for k in ('bound_question','evidence')):raise ValueError('Invalid physical intermediate witness')
    return value


class IntermediateFactExtractor:
    def __init__(self,calls):self.calls=calls
    def extract(self,instruction,observations,*,case_id=None,max_tokens=4096):
        kwargs={'case_id':case_id} if case_id is not None else {}
        value,ref=self.calls.call('physical_intermediates_v13',{'instruction':instruction,'physical_predicate_bank':PREDICATES,'observations':prose_observations(observations)},
            SCHEMA,template=TEMPLATE.read_text(),slot='once',max_tokens=max_tokens,**kwargs)
        validate(value);return {'observations':value,'execution_ref':ref,'version':VERSION}
