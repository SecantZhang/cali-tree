"""Closed semantic-interpretation features plus stable M1 physical summaries."""
from ...decision.artifacts import digest
from ...decision.semantic_interpretation_v5 import FIELDS, make_input, validate
from . import stable_features_v5 as stable

VERSION='interpreted-bound-evidence-v6'
SPECS=dict(stable.SPECS)
SPECS['meaning_available']='A valid label-blind instruction-relative interpretation is available.'
for field,options in FIELDS.items():
    for option in options:
        for quantifier in ('all','any','majority'):
            SPECS['meaning_'+field+'_'+option+'_'+quantifier]=(quantifier.capitalize()+' of the requested requirements have '+field.replace('_',' ')+' = '+option.replace('_',' ')+'.')
FEATURES=tuple(k for k in SPECS if k.startswith('meaning_'))+tuple(stable.FEATURES)
CONTRACT_REF=digest({'version':VERSION,'physical_contract':stable.CONTRACT_REF,'specs':SPECS,'predicate_order':FEATURES,
                    'semantic_input':'instruction_relative_evidence_v5; never dataset labels or previous satisfaction decisions'})


def validate_record(record):
    if record is None:return
    if not isinstance(record,dict) or set(record)!={'version','features'} or record['version']!=VERSION:
        raise ValueError('Invalid interpreted feature record')
    if not isinstance(record['features'],dict) or set(record['features'])!=set(FEATURES) or any(type(v) is not bool for v in record['features'].values()):
        raise ValueError('Undeclared semantic feature or non-Boolean value')


def project(program,observation,pair_ref,interpretation):
    physical=stable.project(program,observation,pair_ref)
    if physical is None:return None
    values=dict.fromkeys(FEATURES,False);values.update(physical['features'])
    if interpretation is not None:
        payload=make_input(program,observation,pair_ref);validate(payload,interpretation)
        requirements=list(interpretation['requirements'].values());n=len(requirements)
        values['meaning_available']=True
        for field,options in FIELDS.items():
            for option in options:
                count=sum(r[field]==option for r in requirements)
                values['meaning_'+field+'_'+option+'_any']=count>0
                values['meaning_'+field+'_'+option+'_majority']=2*count>n
                values['meaning_'+field+'_'+option+'_all']=count==n
    value={'version':VERSION,'features':values};validate_record(value);return value


def synthetic_record(**values):
    result={'version':VERSION,'features':dict.fromkeys(FEATURES,False)}
    result['features'].update(values);validate_record(result);return result
