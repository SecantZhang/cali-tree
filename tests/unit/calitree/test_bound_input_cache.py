from copy import deepcopy
import json
from pathlib import Path

import pytest

from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache, CachedEvidenceCoveredJudge
from critical.core.decision.artifacts import digest
from tests.unit.calitree.test_evidence_coverage_v20 import bound_fixture
from tests.unit.calitree.test_task_coverage import Calls

IDENTITY = {'provider': 'test', 'model': 'mock', 'temperature': 0}


def fixture(tmp_path):
    gate, evidence, p, obs, meaning = bound_fixture(tmp_path)
    cache = BoundEvidenceCache(IDENTITY); cache.add(p['instruction'], evidence, p, obs, meaning)
    return gate, evidence, p, obs, meaning, cache


def test_raw_known_input_reuses_evidence_without_any_model_call(tmp_path):
    gate, evidence, p, _, _, cache = fixture(tmp_path); calls = Calls('no')
    judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=IDENTITY)
    for case_id in ('old-id', 'completely-new-id', None):
        result = judge.judge(p['instruction'], evidence, case_id=case_id)
        assert result['judgment']['label'] == 'yes' and result['source'] == 'frozen_tree'
        assert result['evidence_source'] == 'content_cache'
    assert calls.requests == []


def test_changed_image_or_instruction_does_not_hit_cache(tmp_path):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    assert cache.lookup('different instruction', evidence) is None
    Path(evidence['edited_image']).write_bytes(b'new image')
    assert cache.lookup(p['instruction'], evidence) is None


def test_image_paths_can_change_without_changing_the_content_key(tmp_path):
    _, evidence, p, _, _, cache = fixture(tmp_path); renamed = {}
    for key, path in evidence.items():
        target = tmp_path / ('renamed-' + key); target.write_bytes(Path(path).read_bytes()); renamed[key] = str(target)
    assert cache.lookup(p['instruction'], renamed) == cache.lookup(p['instruction'], evidence)


def test_cache_roundtrip_stores_only_evidence_and_rejects_verdicts(tmp_path):
    _, evidence, p, _, _, cache = fixture(tmp_path)
    artifact = json.loads(json.dumps(cache.export()))
    copy = BoundEvidenceCache(IDENTITY, artifact=artifact)
    assert copy.lookup(p['instruction'], evidence) == cache.lookup(p['instruction'], evidence)
    entry = next(iter(artifact['entries'].values())); entry['reference_label'] = 2
    artifact['artifact_ref'] = digest({k: v for k, v in artifact.items() if k != 'artifact_ref'})
    with pytest.raises(ValueError, match='only bound'):
        BoundEvidenceCache(IDENTITY, artifact=artifact)


def test_new_model_identity_or_overwrite_cannot_change_trained_evidence(tmp_path):
    gate, evidence, p, obs, meaning, cache = fixture(tmp_path)
    with pytest.raises(ValueError, match='identity'):
        CachedEvidenceCoveredJudge(Calls(), gate, cache, identity={**IDENTITY, 'model': 'different'})
    with pytest.raises(ValueError, match='contract'):
        BoundEvidenceCache({**IDENTITY, 'model': 'different'}, artifact=cache.export())
    changed = deepcopy(meaning); changed['requirements']['r1']['explanation'] = 'A different valid draw.'
    with pytest.raises(ValueError, match='replace trained evidence'):
        cache.add(p['instruction'], evidence, p, obs, changed)
