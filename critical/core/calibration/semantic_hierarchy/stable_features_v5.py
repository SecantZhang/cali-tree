"""Duplicate-invariant distributions of authenticated bound checks.

Only exact bound definitions (apart from local IDs/order) are equated. This does
not claim paraphrase equivalence. Contradictory duplicate observations become
unknown rather than being majority-voted or silently dropped.
"""
from collections import defaultdict

from ...decision.bound_evidence_v2 import derive_record, KINDS
from ...decision.artifacts import digest
from . import features_v4 as base

VERSION = 'canonical-bound-check-distributions-v5'
FEATURES, SPECS, ROLES, STATES = base.FEATURES, base.SPECS, base.ROLES, base.STATES
CONTRACT_REF = digest({'version':VERSION,'distribution_contract':base.CONTRACT_REF,
    'equivalence':'Exact typed bound definition, requirement definitions, and recursive dependency definitions; local IDs/order excluded.',
    'duplicate_conflict':'unknown'})


def validate_record(record):
    if record is None:return
    if not isinstance(record,dict) or set(record)!={'version','features'} or record['version']!=VERSION:
        raise ValueError('Invalid stable evidence record')
    base.validate_record({'version':base.VERSION,'features':record['features']})


def as_base(record):
    """Explicit bridge to the frozen v4 fitting engine, under the v5 wrapper."""
    validate_record(record)
    return None if record is None else {'version':base.VERSION,'features':dict(record['features'])}


def canonical_checks(program, observation, pair_ref):
    record=derive_record(program,observation,pair_ref)
    checks={c['id']:c for c in program['checks']}
    requirements={r['id']:{k:v for k,v in r.items() if k not in ('id','check_ids')} for r in program['requirements']}
    memo={}
    def key(check_id):
        if check_id not in memo:
            c=checks[check_id]
            body={k:v for k,v in c.items() if k not in ('id','check_ref','dependencies','requirement_ids')}
            body['requirements']=sorted({digest(requirements[k]) for k in c['requirement_ids']})
            body['dependencies']=sorted({key(k) for k in c['dependencies']})
            memo[check_id]=digest(body)
        return memo[check_id]
    buckets=defaultdict(list)
    for c in record['checks'].values():buckets[key(c['id'])].append(c)
    unique=[];conflicts=[]
    for identity,rows in sorted(buckets.items()):
        states={r['desired_state'] for r in rows}
        state=next(iter(states)) if len(states)==1 else 'unknown'
        unique.append({'role':rows[0]['role'],'kind':rows[0]['kind'],'desired_state':state})
        if len(states)>1:conflicts.append({'definition_ref':identity,'states':sorted(states),'effective_state':'unknown'})
    return unique,{'input_checks':len(checks),'unique_checks':len(unique),
                   'duplicates_removed':len(checks)-len(unique),'duplicate_conflicts':conflicts}


def project_with_audit(program, observation, pair_ref):
    if program is None or observation is None:return None,{'missing_evidence':True}
    checks,audit=canonical_checks(program,observation,pair_ref);values={}
    for role in ROLES:
        for kind in ('all',*sorted(KINDS)):
            selected=[c for c in checks if c['role']==role and (kind=='all' or c['kind']==kind)]
            n=len(selected);prefix=role+'_'+kind
            for threshold in (1,2,3):values[prefix+'_count_ge_'+str(threshold)]=n>=threshold
            for state in STATES:
                count=sum(c['desired_state']==state for c in selected)
                values[prefix+'_'+state+'_any']=count>0
                values[prefix+'_'+state+'_majority']=n>0 and 2*count>n
                values[prefix+'_'+state+'_all']=n>0 and count==n
    result={'version':VERSION,'features':values};validate_record(result)
    return result,audit


def project(program, observation, pair_ref):
    return project_with_audit(program,observation,pair_ref)[0]
