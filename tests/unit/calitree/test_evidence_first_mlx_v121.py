import pytest

from critical.lm_engine.local_mlx_evidence_first_v121 import EvidenceFirstEngine,schema
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.lm_engine.local_mlx_v118 import MODEL,REVISION,WEIGHT_BYTES


def test_evidence_order_and_limit_preserve_the_same_semantic_state_vocabulary():
    contract=schema()
    assert contract['required']==['evidence',*facts.FIELDS]
    assert contract['properties']['evidence']=={'type':'string','minLength':1,'maxLength':360}
    assert all(contract['properties'][k]==facts.schema()['properties'][k] for k in facts.FIELDS)


def test_profile_cannot_silently_run_without_ordering_or_with_the_old_schema(tmp_path,monkeypatch):
    identity={'model':MODEL,'revision':REVISION,'weight_bytes':WEIGHT_BYTES,'status':'complete','destination':str(tmp_path)}
    e=EvidenceFirstEngine(tmp_path,identity)
    monkeypatch.delenv('LMFE_STRICT_JSON_FIELD_ORDER',raising=False)
    with pytest.raises(ValueError,match='field-order'):e.generate('prompt',[],schema())
    monkeypatch.setenv('LMFE_STRICT_JSON_FIELD_ORDER','true')
    with pytest.raises(ValueError,match='evidence-first schema'):e.generate('prompt',[],facts.schema())
    assert e._model is None and e._creds is None
