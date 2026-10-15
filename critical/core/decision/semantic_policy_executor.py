"""Grade-blind categorization of cached prose for a compiled semantic policy."""
from pathlib import Path
from copy import deepcopy
from .compiler import TEXT,enum,object_schema
from ..calibration.policy_semantics import STATES,semantic_record,SemanticConditionPolicy

VERSION='prose-to-semantic-states-v8'
TEMPLATE=Path(__file__).parents[1]/'prompts/templates/semantic_policy_execution_v8/classify_states.txt'


def features(policy):
    a=policy.metadata();used={t['feature'] for key in ('yes','at_least_partial') for clause in a[key] for t in clause}
    if a['uninspectable_label'] is not None:used|={'progress','endpoint'}
    return sorted(used)


def schema(policy):
    return object_schema({'states':object_schema({k:enum((*STATES[k],'unknown')) for k in features(policy)}),'rationale':TEXT})


def prose_observations(observation):
    """Whitelist prose fields; all numeric grades and reference data are dropped."""
    return {'contract':deepcopy(observation['contract']),
        'aspects':[{k:deepcopy(a[k]) for k in ('source_quote','kind','requirement','observed','shortfall')} for a in observation['aspects']],
        'qualities':{k:{'applicability':f['applicability'],'evidence':f['evidence']} for k,f in observation['qualities'].items()}}


def interpreted_record(policy,value):
    used=features(policy)
    if not isinstance(value,dict) or set(value)!={'states','rationale'} or not isinstance(value['states'],dict) or set(value['states'])!=set(used) or not isinstance(value['rationale'],str) or not value['rationale'].strip():raise ValueError('Invalid semantic interpretation')
    low={k:STATES[k][-1] for k in STATES};high=deepcopy(low)
    for k,state in value['states'].items():
        if state not in (*STATES[k],'unknown'):raise ValueError('Invalid named semantic state')
        low[k]=STATES[k][0] if state=='unknown' else state;high[k]=STATES[k][-1] if state=='unknown' else state
    return {'has_observation':True,'lower':low,'upper':high}


class SemanticPolicyExecutor:
    def __init__(self,calls):self.calls=calls
    def execute(self,policy,instruction,observation,*,case_id=None,max_tokens=8192):
        kwargs={'case_id':case_id} if case_id is not None else {}
        value,ref=self.calls.call('semantic_policy_states_v8',
            {'instruction':instruction,'learned_semantic_policy':policy.render(),'observations':prose_observations(observation)},
            schema(policy),template=TEMPLATE.read_text(),slot='once',max_tokens=max_tokens,**kwargs)
        record=interpreted_record(policy,value)
        return {'interpretation':value,'decision':policy.predict_records([record])[0],'execution_ref':ref}
