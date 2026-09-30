"""Execution precedence, unknown handling, evidence isolation and persistence."""

from copy import deepcopy
import json

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayExecutable, ExecutableRubric
from critical.core.optimization.prompt.calitree.decomposition.executable_policy import parse_executable_policy
from critical.core.optimization.prompt.calitree.decomposition.vision_models import parse_semantic_rubric
from .test_decomposition_vision import Engine, INSTRUCTION, RUBRIC


def source():
    return parse_semantic_rubric({"units": [{"kind": "decision", "lines": [1, 3, 4, 5]}]}, RUBRIC)


def program():
    return {"predicates": [
        {"id": "missing", "question": "Is the requested change absent?", "rubric_unit_ids": ["u1"]},
        {"id": "complete", "question": "Is the change complete without unintended semantic changes?", "rubric_unit_ids": ["u1"]}],
        "rules": [
            {"id": "veto", "when": {"predicate": "missing"}, "label": "no", "rubric_unit_ids": ["u1"]},
            {"id": "success", "when": {"predicate": "complete"}, "label": "yes", "rubric_unit_ids": ["u1"]}],
        "default": "partial", "default_rubric_unit_ids": ["u1"]}


def test_precedence_is_compiled_not_an_implicit_fixed_label_order():
    compiled = parse_executable_policy(program(), source())
    assert compiled.decide({"missing": True, "complete": True})["label"] == "no"
    changed = program()
    changed["rules"].reverse()
    assert parse_executable_policy(changed, source()).decide({"missing": True, "complete": True})["label"] == "yes"
    assert compiled.decide({"missing": False, "complete": False})["label"] == "partial"
    assert compiled.decide({"missing": False, "complete": True})["rules_checked"] == [
        {"rule_id": "veto", "result": False}, {"rule_id": "success", "result": True}]


def test_unknown_blocks_later_success_and_default_but_decisive_operands_are_respected():
    compiled = parse_executable_policy(program(), source())
    with pytest.raises(ValueError, match="blocks"):
        compiled.decide({"missing": None, "complete": True})
    with pytest.raises(ValueError, match="blocks"):
        compiled.decide({"missing": False, "complete": None})
    changed = program()
    changed["rules"][0]["when"] = {"all": [{"predicate": "missing"}, {"not": {"predicate": "complete"}}]}
    assert parse_executable_policy(changed, source()).decide({"missing": None, "complete": True})["label"] == "yes"
    changed["rules"][0]["when"] = {"any": [{"predicate": "missing"}, {"predicate": "complete"}]}
    assert parse_executable_policy(changed, source()).decide({"missing": None, "complete": True})["label"] == "no"


@pytest.mark.parametrize("mutation", ["unknown_reference", "unused", "duplicate", "code", "citation", "missing_evidence"])
def test_invalid_or_untraceable_programs_are_rejected(mutation):
    value = program()
    if mutation == "unknown_reference":
        value["rules"][0]["when"] = {"predicate": "not_defined"}
    elif mutation == "unused":
        value["rules"].pop()
    elif mutation == "duplicate":
        value["predicates"][1]["id"] = "missing"
    elif mutation == "code":
        value["rules"][0]["when"] = {"eval": "arbitrary code"}
    elif mutation == "citation":
        value["predicates"][0]["rubric_unit_ids"] = ["invented"]
    else:
        value["rules"][0]["rubric_unit_ids"] = []
    with pytest.raises(ValueError):
        parse_executable_policy(value, source())


def test_policy_requires_coverage_and_validates_mutated_artifacts():
    rubric = parse_semantic_rubric({"units": [{"kind": "decision", "lines": [1, 3]},
                                            {"kind": "exception", "lines": [4, 5]}]}, RUBRIC)
    with pytest.raises(ValueError, match="omitted"):
        parse_executable_policy(program(), rubric)
    compiled = parse_executable_policy(program(), source())
    assert ExecutableRubric.from_dict(compiled.to_dict()) == compiled
    exported = compiled.to_dict()
    exported["program"]["default"] = "yes"
    assert compiled.program["default"] == "partial"
    exported["source"]["units"][0]["text"] = "tampered rubric"
    with pytest.raises(ValueError):
        ExecutableRubric.from_dict(exported)
    compiled.program["rules"][0]["when"] = {"predicate": "not_defined"}
    with pytest.raises(ValueError):
        compiled.decide({"missing": False, "complete": True})


def observations():
    return {"instruction": INSTRUCTION,
            "requested": [{"condition": {"id": "c1", "requirement": "Gray cylinder removed", "target": "gray cylinder", "reference": None, "source_phrase": INSTRUCTION},
                           "fulfillment": "complete", "source_observation": "Cylinder present", "edited_observation": "Cylinder absent", "explanation": "Target removed"}],
            "preservation": {"recognizability": "clear", "scene_continuity": "same", "unrequested_changes": [{"description": "Sphere removed", "severity": "meaningful", "evidence": "Sphere only in source"}], "explanation": "Unrelated object removed"},
            "image_sha256": ["source", "edited"], "target_label": "SECRET_LABEL", "metadata": "SECRET_ID"}


class ExecutionEngine(Engine):
    def generate(self, user, **kwargs):
        payload = json.loads(user)
        if "rubric_units" in payload:
            self.calls.append((payload, kwargs))
            value = program()
            # The base compiler makes one unit per source line; include all of
            # them, retaining the actual IDs rather than the helper's single ID.
            ids = [u["id"] for u in payload["rubric_units"]]
            for row in [*value["predicates"], *value["rules"]]:
                row["rubric_unit_ids"] = ids
            value["default_rubric_unit_ids"] = ids
            return {"content": json.dumps(value)}
        if "question" in payload:
            self.calls.append((payload, kwargs))
            return {"content": json.dumps({"value": "false", "rationale": "Removal happened but unrelated sphere removed.", "condition_ids": ["c1"], "uses_preservation": True})}
        return super().generate(user, **kwargs)


def test_compilation_and_atomic_predicates_are_label_free_and_resume(tmp_path):
    engine = ExecutionEngine()
    checkpoint = CheckpointStore(tmp_path / "execution.jsonl")
    algorithm = DecompositionTwoWayExecutable(engine, checkpoint=checkpoint)
    result = algorithm.aggregate(algorithm.compile(RUBRIC), observations())
    assert result.label == "partial"
    assert "SECRET" not in json.dumps(engine.calls)
    predicate_calls = [p for p, kwargs in engine.calls if "question" in p]
    assert len(predicate_calls) == 2
    assert all(set(p) == {"question", "criterion_sources", "observations"} for p in predicate_calls)
    assert all("rules" not in p and "media_inputs" not in kwargs for p, kwargs in engine.calls)
    assert result.trace["execution"]["rule_id"] is None
    assert set(result.trace["predicate_findings"]) == {"missing", "complete"}
    resumed_engine = ExecutionEngine()
    resumed = DecompositionTwoWayExecutable(resumed_engine, checkpoint=checkpoint)
    assert resumed.aggregate(resumed.compile(RUBRIC), observations()) == result
    assert not resumed_engine.calls


def test_unknown_findings_never_become_success_or_trigger_quality_retry():
    class UnknownEngine(ExecutionEngine):
        def generate(self, user, **kwargs):
            response = super().generate(user, **kwargs)
            if "question" in json.loads(user):
                response["content"] = json.dumps({"value": "unknown", "rationale": "Conflicting observations", "condition_ids": [], "uses_preservation": False})
            return response
    engine = UnknownEngine()
    algorithm = DecompositionTwoWayExecutable(engine)
    with pytest.raises(ValueError, match="blocks"):
        algorithm.aggregate(algorithm.compile(RUBRIC), observations())
    assert len([p for p, _ in engine.calls if "question" in p]) == 2


def test_invalid_observations_fail_before_predicate_calls():
    engine = ExecutionEngine()
    algorithm = DecompositionTwoWayExecutable(engine)
    policy = algorithm.compile(RUBRIC)
    before = len(engine.calls)
    bad = deepcopy(observations())
    bad["requested"][0]["fulfillment"] = "invented"
    with pytest.raises(ValueError):
        algorithm.aggregate(policy, bad)
    assert len(engine.calls) == before


def test_recording_wrapper_preserves_settings_in_checkpoint_identity(tmp_path):
    from .helpers import RecordingEngine
    store = CheckpointStore(tmp_path / "settings.jsonl")
    first = ExecutionEngine()
    DecompositionTwoWayExecutable(RecordingEngine(first, []), checkpoint=store).compile(RUBRIC)
    unchanged = ExecutionEngine()
    DecompositionTwoWayExecutable(RecordingEngine(unchanged, []), checkpoint=store).compile(RUBRIC)
    assert not unchanged.calls
    changed = ExecutionEngine()
    changed.max_tokens = 8192
    DecompositionTwoWayExecutable(RecordingEngine(changed, []), checkpoint=store).compile(RUBRIC)
    assert len(changed.calls) == 2


def test_executable_policy_works_through_native_aurora_judge_callback(tmp_path, monkeypatch):
    engine = ExecutionEngine()
    algorithm = DecompositionTwoWayExecutable(engine)
    source_path, edited_path = tmp_path / "source.png", tmp_path / "edited.png"
    source_path.write_bytes(b"source")
    edited_path.write_bytes(b"edited")
    facts = observations()
    facts.pop("target_label")
    facts.pop("metadata")
    monkeypatch.setattr(algorithm, "observe", lambda plan, evidence: deepcopy(facts))
    result = algorithm.judge(RUBRIC, {"input": {"instruction": INSTRUCTION, "source_image_path": str(source_path)},
                                    "output": {"edited_image_path": str(edited_path)},
                                    "target_label": "SECRET_LABEL", "metadata": "SECRET_ID"})
    assert result["label"] == "partial"
    assert "SECRET" not in json.dumps(engine.calls)
