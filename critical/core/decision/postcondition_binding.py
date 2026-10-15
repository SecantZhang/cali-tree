"""Bind instruction clauses to physical predicates without seeing observations."""
from pathlib import Path
from .compiler import TEXT,array,enum,object_schema
from .observable_facts import PREDICATES

VERSION='instruction-physical-postconditions-v12'
TEMPLATE=Path(__file__).parents[1]/'prompts/templates/postcondition_binding_v12/compile.txt'
PREDICATE=enum(tuple(PREDICATES))
REQUIREMENT=object_schema({'source_quote':TEXT,'physical_test':TEXT,
    'required_present':array(PREDICATE),'required_absent':array(PREDICATE)})
SCHEMA=object_schema({'postconditions':{**array(REQUIREMENT),'minItems':1,'maxItems':6},
    'supporting_witnesses':array(PREDICATE),'identity_witnesses':array(PREDICATE),
    'collateral_witnesses':array(PREDICATE)})


def validate(value,instruction):
    if not isinstance(value,dict) or set(value)!=set(SCHEMA['properties']) or not isinstance(value['postconditions'],list) or not 1<=len(value['postconditions'])<=6:raise ValueError('Invalid postcondition program')
    for p in value['postconditions']:
        if not isinstance(p,dict) or set(p)!=set(REQUIREMENT['properties']) or any(not isinstance(p[k],str) or not p[k].strip() for k in ('source_quote','physical_test')):
            raise ValueError('A physical test and instruction anchor are required')
        if p['source_quote'] not in instruction:raise ValueError('Postcondition anchor is not a literal instruction span')
        for k in ('required_present','required_absent'):
            if not isinstance(p[k],list) or len(set(p[k]))!=len(p[k]) or any(v not in PREDICATES for v in p[k]):raise ValueError('Invalid primitive predicate')
        if not p['required_present'] and not p['required_absent'] or set(p['required_present'])&set(p['required_absent']):raise ValueError('Nonempty consistent physical conjunction required')
    for k in ('supporting_witnesses','identity_witnesses','collateral_witnesses'):
        if not isinstance(value[k],list) or len(set(value[k]))!=len(value[k]) or any(v not in PREDICATES for v in value[k]):raise ValueError('Invalid supporting predicate')
    return value


class PostconditionCompiler:
    def __init__(self,calls):self.calls=calls
    def compile(self,instruction,*,case_id=None,max_tokens=4096):
        kwargs={'case_id':case_id} if case_id is not None else {}
        value,ref=self.calls.call('physical_postconditions_v12',{'instruction':instruction,'observable_predicates':PREDICATES},
            SCHEMA,template=TEMPLATE.read_text(),slot='once',max_tokens=max_tokens,**kwargs)
        validate(value,instruction);return {'program':value,'execution_ref':ref,'version':VERSION}
