from copy import deepcopy
import pytest

from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.artifacts import digest
from critical.lm_engine.local_mlx_large_v128 import MODEL,LargeMLXEngine,MEMORY_LIMIT
from run.verify_calitree_large_probe_v130 import validate
from tests.unit.calitree.test_local_cache_audit_v98 import fixture


def sample():
    job,response,profile=fixture();profile={**profile,'model':MODEL,'engine':LargeMLXEngine.name,'max_new_tokens':512}
    job={k:v for k,v in job.items() if k!='request_ref'};job['identity_ref']=digest(profile);job['request_ref']=digest(job)
    value=response['observation'];record=facts.bind(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],value)
    raw={**response['response'],'model':MODEL,'engine':LargeMLXEngine.name,'endpointHost':'local-mlx','peakMemoryBytes':20*1024**3}
    return job,{**response,'request_ref':job['request_ref'],'record':record,'response':raw},profile


def test_large_model_cannot_reuse_a_foreign_image_binding(tmp_path):
    job,response,profile=sample();assert validate(job,response,profile)
    wrong=deepcopy(response);wrong['record']['image_pair_ref']='other'
    with pytest.raises(ValueError,match='binding'):validate(job,wrong,profile)


def test_correct_json_does_not_override_the_native_resource_bound():
    job,response,profile=sample();wrong=deepcopy(response);wrong['response']['peakMemoryBytes']=MEMORY_LIMIT+1
    with pytest.raises(ValueError,match='memory'):validate(job,wrong,profile)
