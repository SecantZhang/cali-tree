"""Binding, observation preservation, and isolation for fitted decision sets."""
from copy import deepcopy
import hashlib
import json

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import (
    FrozenCriteria, FrozenCriteriaExecutor, NeutralEvidence,
)
from critical.core.optimization.prompt.calitree.decomposition.decision_sets import json_hash
from .test_casewise_fitting import plan, check, Engine


def images(tmp_path):
    source, edited = tmp_path / "source.png", tmp_path / "edited.png"
    source.write_bytes(b"source image bytes")
    edited.write_bytes(b"edited image bytes")
    evidence = {"source_image": str(source), "edited_image": str(edited)}
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, edited)]
    return evidence, hashes


def neutral(hashes, local="old-c1", probe_id="old-q1"):
    return NeutralEvidence.bind(
        [{"id": probe_id, "condition_ids": [local], "property": "interaction",
          "object_class": "person", "reference_class": "curtain"}],
        {role: {"answers": [{"id": probe_id, "answer": "Visible gap between hand and curtain",
                             "uncertainty": "medium"}]} for role in ("source", "edited")},
        hashes, origin="saved observation experiment",
    )


def test_frozen_criteria_binding_and_defensive_export():
    bound = FrozenCriteria.bind("rubric", "Close curtains", plan(), feedback_used=True, origin="prior-fit")
    copy = bound.to_dict()
    restored = FrozenCriteria.from_dict(json.loads(json.dumps(copy)))
    assert restored == bound
    copy["plan"]["conditions"][0]["requirement"] = "open door"
    with pytest.raises(ValueError, match="Changed"):
        FrozenCriteria.from_dict(copy)
    assert bound.to_dict()["plan"] == plan()


@pytest.mark.parametrize("prompt,instruction", [("changed", "Close curtains"), ("rubric", "Open curtains")])
def test_wrong_prompt_or_instruction_stops_before_calls(tmp_path, prompt, instruction):
    engine = Engine([])
    executor = FrozenCriteriaExecutor(engine)
    evidence, _ = images(tmp_path)
    with pytest.raises(ValueError, match="binding"):
        executor.observe(FrozenCriteria.bind("rubric", "Close curtains", plan()),
                         prompt=prompt, instruction=instruction, evidence=evidence)
    assert engine.calls == []


def test_neutral_binding_rejects_changed_or_swapped_image_bytes(tmp_path):
    evidence, hashes = images(tmp_path)
    bound = neutral(hashes)
    with pytest.raises(ValueError, match="different image"):
        bound.checker_payload(list(reversed(hashes)))
    engine = Engine([])
    executor = FrozenCriteriaExecutor(engine)
    from pathlib import Path
    Path(evidence["edited_image"]).write_bytes(b"changed pixels")
    with pytest.raises(ValueError, match="different image"):
        executor.observe(FrozenCriteria.bind("rubric", "Close curtains", plan()),
                         prompt="rubric", instruction="Close curtains", evidence=evidence,
                         neutral_evidence=bound)
    assert not engine.calls


def test_probe_identity_is_independent_of_obsolete_condition_and_probe_ids():
    hashes = ["a" * 64, "b" * 64]
    a, b = neutral(hashes), neutral(hashes, local="revised-cond3", probe_id="new-probe")
    assert a.to_dict() == b.to_dict()
    payload = a.checker_payload(hashes)
    assert "condition_ids" not in json.dumps(payload)
    assert "old-c1" not in json.dumps(payload)
    assert "origin" not in payload
    assert payload["source"]["answers"][0]["id"] == payload["questions"][0]["id"]


def test_unknown_is_preserved_in_features_and_no_label_is_invented(tmp_path):
    evidence, hashes = images(tmp_path)
    criteria = plan()
    criteria["rubric_conflicts"] = ["Known fit label selected this revision"]
    bound = FrozenCriteria.bind("rubric", "Close curtains", criteria, feedback_used=True)
    engine = Engine([check("unknown")])
    result = FrozenCriteriaExecutor(engine).observe(
        bound, prompt="rubric", instruction="Close curtains", evidence=evidence, neutral_evidence=neutral(hashes))
    assert result["local_features"][0]["status"] == "unknown"
    assert result["local_features"][0]["observed"] is False
    assert "label" not in result
    payload = json.loads(engine.calls[0][0].split("INPUT_JSON: ")[1])
    assert set(payload) == {"instruction", "condition", "independent_neutral_observations"}
    assert "Known fit label" not in json.dumps(payload)
    assert result["criteria"]["provenance"]["feedback_used"] is True


def test_checkpoint_replay_and_criterion_change(tmp_path):
    evidence, _ = images(tmp_path)
    cache = CheckpointStore(tmp_path / "checks.jsonl")
    bound = FrozenCriteria.bind("rubric", "Close curtains", plan())
    engine = Engine([check("partial")])
    first = FrozenCriteriaExecutor(engine, checkpoint=cache).observe(
        bound, prompt="rubric", instruction="Close curtains", evidence=evidence)
    replay_engine = Engine([])
    replay = FrozenCriteriaExecutor(replay_engine, checkpoint=CheckpointStore(cache.path)).observe(
        FrozenCriteria.from_dict(bound.to_dict()), prompt="rubric", instruction="Close curtains", evidence=evidence)
    assert replay == first and not replay_engine.calls
    changed = FrozenCriteria.bind("rubric", "Close curtains", plan("window fully covered"))
    another = Engine([check("absent")])
    result = FrozenCriteriaExecutor(another, checkpoint=cache).observe(
        changed, prompt="rubric", instruction="Close curtains", evidence=evidence)
    assert len(another.calls) == 1
    assert result["local_features"][0]["local_criterion_sha256"] != first["local_features"][0]["local_criterion_sha256"]


def test_invalid_checks_are_logged_and_not_cached(tmp_path):
    evidence, _ = images(tmp_path)
    engine = Engine([{"status": "human target"}, {"status": "human target"}])
    cache = CheckpointStore(tmp_path / "checks.jsonl")
    executor = FrozenCriteriaExecutor(engine, checkpoint=cache)
    with pytest.raises(ValueError, match="fields"):
        executor.observe(FrozenCriteria.bind("rubric", "Close curtains", plan()),
                         prompt="rubric", instruction="Close curtains", evidence=evidence)
    assert len(executor.calls) == 2 and len(cache) == 0
    assert all("validation_error" in call for call in executor.calls)


def test_neutral_import_rejects_annotations_missing_answers_and_changed_questions():
    hashes = ["a" * 64, "b" * 64]
    bundle = neutral(hashes).to_dict()
    bundle["probes"][0]["question"] = "Did the requested edit succeed?"
    bundle["artifact_sha256"] = json_hash({k: v for k, v in bundle.items() if k != "artifact_sha256"})
    with pytest.raises(ValueError, match="question mismatch"):
        NeutralEvidence.from_dict(bundle)
    bundle = neutral(hashes).to_dict()
    bundle["observations"]["edited"][0]["label"] = "no"
    bundle["artifact_sha256"] = json_hash({k: v for k, v in bundle.items() if k != "artifact_sha256"})
    with pytest.raises(ValueError, match="stored answer"):
        NeutralEvidence.from_dict(bundle)
    with pytest.raises(ValueError, match="coverage"):
        NeutralEvidence.bind([{"id": "q1", "property": "count", "object_class": "fish", "reference_class": None}],
                             {"source": {"answers": []}, "edited": {"answers": []}}, hashes, origin="test")


def probe():
    return {"id": "old-q7", "condition_ids": ["old-c99"], "property": "interaction",
            "object_class": "person", "reference_class": "curtain"}


def answer(text="A hand is separated from the curtain"):
    return {"answers": [{"id": "q1", "answer": text, "uncertainty": "medium"}]}


def test_fresh_neutral_observer_has_only_questions_and_one_image(tmp_path):
    evidence, hashes = images(tmp_path)
    engine = Engine([answer("A hand holds an object"), answer(), check("absent")])
    executor = FrozenCriteriaExecutor(engine)
    neutral_evidence = executor.observe_neutral([probe()], evidence=evidence)
    assert neutral_evidence.to_dict()["image_sha256"] == hashes
    for index, (prompt_text, kwargs) in enumerate(engine.calls):
        payload = json.loads(prompt_text.split("INPUT_JSON: ")[1])
        assert set(payload) == {"questions"}
        assert "old-c99" not in prompt_text and "old-q7" not in prompt_text
        assert "Close curtains" not in prompt_text
        assert kwargs["media_inputs"] == [{"type": "image", "path": evidence[("source_image", "edited_image")[index]]}]
        assert kwargs["strict_schema"] is True
    result = executor.observe(FrozenCriteria.bind("rubric", "Close curtains", plan()),
                              prompt="rubric", instruction="Close curtains", evidence=evidence,
                              neutral_evidence=neutral_evidence)
    assert result["local_features"][0]["status"] == "absent"
    assert [c["stage"] for c in executor.calls] == ["neutral_observation", "neutral_observation", "condition_check"]


def test_neutral_reuse_is_per_image_and_fresh_namespace_makes_new_calls(tmp_path):
    from pathlib import Path
    evidence, hashes = images(tmp_path)
    cache = CheckpointStore(tmp_path / "observations.jsonl")
    engine = Engine([answer("source"), answer("edited")])
    bound = FrozenCriteriaExecutor(engine, checkpoint=cache).observe_neutral([probe()], evidence=evidence)
    replay_engine = Engine([])
    executor = FrozenCriteriaExecutor(replay_engine, checkpoint=CheckpointStore(cache.path))
    revised = {**probe(), "id": "new-q1", "condition_ids": ["new-c2"]}
    assert executor.observe_neutral([revised], evidence=evidence) == bound
    swapped = executor.observe_neutral([revised], evidence={
        "source_image": evidence["edited_image"], "edited_image": evidence["source_image"]})
    assert swapped.to_dict()["image_sha256"] == list(reversed(hashes))
    assert swapped.checker_payload(list(reversed(hashes)))["source"]["answers"][0]["answer"] == "edited"
    assert not replay_engine.calls
    Path(evidence["edited_image"]).write_bytes(b"new image pixels")
    changed_engine = Engine([answer("new edited")])
    changed = FrozenCriteriaExecutor(changed_engine, checkpoint=cache).observe_neutral([probe()], evidence=evidence)
    assert len(changed_engine.calls) == 1
    assert changed.to_dict()["image_sha256"] != hashes
    fresh_engine = Engine([answer("source fresh"), answer("edited fresh")])
    FrozenCriteriaExecutor(fresh_engine, checkpoint=CheckpointStore(tmp_path / "independent.jsonl")).observe_neutral(
        [probe()], evidence=evidence)
    assert len(fresh_engine.calls) == 2


def test_neutral_schema_repair_and_missing_probe_preflight(tmp_path):
    evidence, _ = images(tmp_path)
    engine = Engine([{"answers": []}, answer(), answer()])
    executor = FrozenCriteriaExecutor(engine)
    with pytest.raises(ValueError, match="reference"):
        executor.observe_neutral([{**probe(), "reference_class": None}], evidence=evidence)
    assert not engine.calls
    executor.observe_neutral([probe()], evidence=evidence)
    assert len(engine.calls) == 3
    assert "coverage" in executor.calls[0]["validation_error"]
    assert "SCHEMA_ERROR" in engine.calls[1][0]


def test_neutral_provider_failure_preserves_completed_image_checkpoint(tmp_path):
    evidence, _ = images(tmp_path)
    cache = CheckpointStore(tmp_path / "observations.jsonl")
    engine = Engine([answer("source")])
    executor = FrozenCriteriaExecutor(engine, checkpoint=cache)
    with pytest.raises(StopIteration):
        executor.observe_neutral([probe()], evidence=evidence)
    assert len(cache) == 1 and executor.calls[-1]["error_type"] == "StopIteration"
    resumed = Engine([answer("edited")])
    FrozenCriteriaExecutor(resumed, checkpoint=cache).observe_neutral([probe()], evidence=evidence)
    assert len(resumed.calls) == 1
