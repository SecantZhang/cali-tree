from copy import deepcopy
import json
import pytest

from critical.core.decision.artifacts import digest
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.lm_engine.local_mlx_evidence_first_v121 import schema,EvidenceFirstEngine
from critical.lm_engine.local_mlx_v118 import MODEL
from run.verify_calitree_evidence_first_v123 import validate
from tests.unit.calitree.test_local_cache_audit_v98 import fixture


def sample():
    job,response,profile=fixture();profile={**profile,'engine':EvidenceFirstEngine.name,'model':MODEL,'max_new_tokens':512}
    job={k:v for k,v in job.items() if k!='request_ref'};job.update(identity_ref=digest(profile),schema=schema());job['request_ref']=digest(job)
    value=response['observation'];value={k:value[k] for k in schema()['required']}
    record=facts.bind(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],value)
    raw={**response['response'],'engine':EvidenceFirstEngine.name,'model':MODEL,'endpointHost':'local-mlx','peakMemoryBytes':1024,'content':json.dumps(value),'parsed':value}
    return job,{**response,'request_ref':job['request_ref'],'observation':value,'record':record,'response':raw},profile


def test_native_field_order_is_checked_even_when_values_and_record_hash_match():
    job,response,profile=sample();assert validate(job,response,profile)
    wrong=deepcopy(response);value=wrong['response']['parsed'];value={k:value[k] for k in reversed(list(value))};wrong['response']['content']=json.dumps(value)
    with pytest.raises(ValueError,match='order'):validate(job,wrong,profile)


def test_narrow_evidence_limit_cannot_be_bypassed_by_the_older_record_contract():
    job,response,profile=sample();wrong=deepcopy(response);value=wrong['observation'];value['evidence']='x'*361
    wrong['response'].update(content=json.dumps(value),parsed=value);wrong['record']=facts.bind(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],value)
    with pytest.raises(ValueError,match='length'):validate(job,wrong,profile)
