"""Case-independent semantic predicates: no counts, majorities, names or IDs."""
from ...decision.artifacts import digest
from ...decision.bound_evidence_v2 import KINDS
from . import interpreted_features_v6 as interpreted

VERSION='portable-semantic-predicates-v8'
PHYSICAL=tuple(k for k in interpreted.FEATURES if not k.startswith('meaning_') and (k.endswith('_any') or k.endswith('_all')))
MEANING=tuple(k for k in interpreted.FEATURES if k.startswith('meaning_') and not k.endswith('_majority'))
OPERATIONS=tuple(k for k in KINDS if k!='identity')
SPECS={k:interpreted.SPECS[k] for k in MEANING}
for kind in OPERATIONS:
    SPECS['requires_'+kind]='The instruction requests a '+kind.replace('_',' ')+' outcome.'
for key in PHYSICAL:SPECS[key]=interpreted.SPECS[key]
FEATURES=tuple(SPECS)
CONTRACT_REF=digest({'version':VERSION,'meaning_contract':interpreted.CONTRACT_REF,'predicates':SPECS,
    'prohibited':'Case/source IDs, object names, instruction text, image hashes, coordinates, raw check cardinalities, majority thresholds, and lookup of observed case signatures.',
    'physical_quantifiers':'Any/all over canonical physical checks. Presence of an outcome kind describes the instruction; it is not a raw check-count threshold.'})


def validate_record(record):
    if record is None:return
    if not isinstance(record,dict) or set(record)!={'version','features'} or record['version']!=VERSION:
        raise ValueError('Invalid portable semantic record')
    if not isinstance(record['features'],dict) or set(record['features'])!=set(FEATURES) or any(type(v) is not bool for v in record['features'].values()):
        raise ValueError('Only whitelisted case-independent semantic predicates are accepted')


def from_interpreted(record):
    interpreted.validate_record(record)
    if record is None:return None
    old=record['features'];values={k:old[k] for k in (*MEANING,*PHYSICAL)}
    values.update({'requires_'+kind:old['outcome_'+kind+'_count_ge_1'] for kind in OPERATIONS})
    result={'version':VERSION,'features':values};validate_record(result);return result


def project(program,observation,pair_ref,interpretation):
    return from_interpreted(interpreted.project(program,observation,pair_ref,interpretation))


def synthetic_record(**values):
    result={'version':VERSION,'features':dict.fromkeys(FEATURES,False)}
    result['features'].update(values);validate_record(result);return result
