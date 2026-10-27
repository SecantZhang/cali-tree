import json
from copy import deepcopy
import pytest

from run.calitree_large_semantic_policy_v135 import load
from run.verify_calitree_large_probe_v130 import validate
from tests.unit.calitree.test_large_probe_audit_v130 import sample
from critical.core.decision.bounded_local_schema_v131 import schema
from critical.core.decision.artifacts import digest
from critical.core.decision import local_rubric_evidence_v94 as facts


def test_incomplete_new_observer_cache_cannot_reach_fitting(tmp_path,monkeypatch):
    cache=tmp_path/'cache';audit=tmp_path/'audit';cache.mkdir();audit.mkdir()
    (audit/'verification.json').write_text(json.dumps({'passed':True,'complete':False,'snapshot_only':True,'source_masks_unchanged':True}))
    (audit/'manifest.json').write_text('{}')
    def forbidden(*args,**kwargs):raise RuntimeError('Should not read fitting arrays')
    monkeypatch.setattr('run.calitree_large_semantic_policy_v135.old_load',forbidden)
    with pytest.raises(AssertionError):load(cache,audit)


def test_bound_record_cannot_bypass_the_narrower_evidence_schema():
    job,response,profile=sample();profile={**profile,'evidence_max_chars':360}
    job={k:v for k,v in job.items() if k!='request_ref'};job.update(schema=schema(),identity_ref=digest(profile));job['request_ref']=digest(job)
    response={**response,'request_ref':job['request_ref']};value=deepcopy(response['observation']);value['evidence']='x'*361
    response['observation']=value;response['record']=facts.bind(job['program'],job['image_pair_ref'],job['identity_ref'],job['prompt_ref'],value)
    response['response']={**response['response'],'content':json.dumps(value),'parsed':value}
    with pytest.raises(ValueError,match='Bounded evidence'):validate(job,response,profile)
