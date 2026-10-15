"""Distinguish requested outcome constraints from descriptive identity evidence."""
from .physical_witness_program import PREDICATES as BASE,DIRECTIONS as BASE_DIRECTIONS,CONCEPTS as BASE_CONCEPTS,CORE,SUPPORT,compile_record as base_record
from .observable_facts import STATES

ROLE_FACTS={
 'requested_entity_attribute_conflict_observed':'Does an explicitly bound required-absent entity-attribute conflict have affirmative evidence? A merely descriptive source-identification attribute is not included unless the instruction compiler makes it an outcome constraint.',
 'requested_count_or_multiplicity_conflict_observed':'Does a bound exact-count or no-duplication postcondition have affirmative contrary evidence? Unrequested count changes and authorized additions are not automatically conflicts.'}
PREDICATES={**BASE,**ROLE_FACTS}
DIRECTIONS={**BASE_DIRECTIONS,**{k:-1 for k in ROLE_FACTS}}
CONCEPTS={k:tuple(dict.fromkeys((*v,*ROLE_FACTS))) for k,v in BASE_CONCEPTS.items()}


def compile_record(primitive,program,intermediate):
    result=base_record(primitive,program,intermediate)
    if result is None:return None
    f=primitive['facts'];positive={k for p in program['postconditions'] for k in p['required_present']};negative={k for p in program['postconditions'] for k in p['required_absent']}
    attr='specified_entity_attribute_conflict' in negative and f['specified_entity_attribute_conflict']=='true'
    count=('explicit_count_matches' in positive and f['explicit_count_matches']=='false' or
           'target_instance_count_increased' in negative and f['target_instance_count_increased']=='true')
    return {'facts':{**result['facts'],'requested_entity_attribute_conflict_observed':'true' if attr else 'false',
        'requested_count_or_multiplicity_conflict_observed':'true' if count else 'false'}}


def validate_record(x):
    if x is None:return
    if not isinstance(x,dict) or set(x)!={'facts'} or not isinstance(x['facts'],dict) or set(x['facts'])!=set(PREDICATES) or any(v not in STATES for v in x['facts'].values()):
        raise ValueError('Only role-bound physical predicates are allowed')
