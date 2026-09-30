"""Intent scope isolation, exact traces, and downstream context consistency."""

from copy import deepcopy
import json

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayIntent
from critical.core.optimization.prompt.calitree.decomposition.decomposition_twoway import parse_edit_scope
from .test_decomposition_vision import Engine, INSTRUCTION, RUBRIC, images


def scope(instruction=INSTRUCTION):
    return {"operations": [{"id": "a1", "action": "remove whole object", "target": "cylinder",
                            "selectors": ["small", "gray"], "quantity": None,
                            "requested_delta": "The entire selected cylinder is absent",
                            "permitted_effects": ["The cylinder and its occlusion/shadow may disappear"],
                            "source_phrase": instruction}], "ambiguities": []}


@pytest.mark.parametrize("field,value", [("quantity", True), ("quantity", 0), ("quantity", -1),
                                        ("selectors", "gray"), ("permitted_effects", [""]),
                                        ("source_phrase", "gray cylinder"), ("action", "")])
def test_invalid_scope_is_rejected(field, value):
    bad = scope()
    bad["operations"][0][field] = value
    with pytest.raises(ValueError):
        parse_edit_scope(bad, INSTRUCTION)


def test_scope_rejects_duplicate_ids_unknown_fields_and_empty_operations():
    bad = scope()
    bad["operations"].append(deepcopy(bad["operations"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        parse_edit_scope(bad, INSTRUCTION)
    bad = scope()
    bad["operations"][0]["target_label"] = "no"
    with pytest.raises(ValueError, match="Malformed"):
        parse_edit_scope(bad, INSTRUCTION)
    with pytest.raises(ValueError, match="1-12"):
        parse_edit_scope({"operations": [], "ambiguities": []}, INSTRUCTION)


class ScopeEngine(Engine):
    def generate(self, user, **kwargs):
        payload = json.loads(user)
        if kwargs["system"].startswith("Parse ONLY"):
            self.calls.append((payload, kwargs))
            return {"content": json.dumps(scope(payload["instruction"]))}
        if "edit_scope" in payload:
            self.calls.append((payload, kwargs))
            return {"content": json.dumps({"conditions": [{"id": "c1", "requirement": "The entire selected small gray cylinder is absent", "target": "small gray cylinder", "reference": None, "source_phrase": payload["instruction"]}]})}
        if "conditions" in payload and "media_inputs" in kwargs:
            self.calls.append((payload, kwargs))
            return {"content": json.dumps({"scene": "Cylinder and sphere",
                                           "groundings": [{"condition_id": c["id"], "target_description": "small gray cylinder on left", "reference_description": None, "source_state": "Cylinder present", "visibility": "clear"} for c in payload["conditions"]]})}
        if kwargs["system"].startswith("Compare two images"):
            self.calls.append((payload, kwargs))
            return {"content": json.dumps({"recognizability": "clear", "scene_continuity": "same",
                                           "unrequested_changes": [], "explanation": "Only the requested cylinder removed"})}
        return super().generate(user, **kwargs)


def test_scope_is_instruction_only_and_shared_with_checks_preservation_and_aggregation(tmp_path):
    engine = ScopeEngine()
    algorithm = DecompositionTwoWayIntent(engine)
    result = algorithm.judge(RUBRIC, {"instruction": INSTRUCTION, "evidence": images(tmp_path),
                                     "target_label": "SECRET_GROUND_TRUTH", "metadata": "SECRET_EDITOR"})
    assert result["label"] == "partial"  # The fake aggregator's fixed output.
    assert "SECRET" not in json.dumps(engine.calls)
    scope_calls = [(p, k) for p, k in engine.calls if k["system"].startswith("Parse ONLY")]
    assert len(scope_calls) == 1  # decompose and grounding share the validated cache.
    assert scope_calls[0][0] == {"instruction": INSTRUCTION}
    assert "media_inputs" not in scope_calls[0][1]
    planning = [p for p, _ in engine.calls if "edit_scope" in p]
    assert planning == [{"instruction": INSTRUCTION, "edit_scope": scope()}]
    grounding = [(p, k) for p, k in engine.calls if "conditions" in p and "media_inputs" in k]
    assert len(grounding) == 1 and len(grounding[0][1]["media_inputs"]) == 1
    condition = next(p for p, _ in engine.calls if "condition" in p)
    assert condition["source_grounding"]["edit_scope"] == scope()
    preservation = next(p for p, k in engine.calls if k["system"].startswith("Compare two images"))
    aggregate = next(p for p, _ in engine.calls if "rubric_units" in p)
    assert preservation["source_grounding"]["edit_scope"] == scope()
    assert aggregate["source_grounding"]["edit_scope"] == scope()
    assert all("rubric" not in p and "label" not in p for p, k in engine.calls if "media_inputs" in k)


def test_intent_trace_and_checkpoint_resume_do_not_recompute_scope(tmp_path):
    engine = ScopeEngine()
    store = CheckpointStore(tmp_path / "intent.jsonl")
    algorithm = DecompositionTwoWayIntent(engine, checkpoint=store)
    media = images(tmp_path)
    result = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, media)
    assert result.trace["observations"]["source_grounding"]["edit_scope"] == scope()
    assert result.trace["plan"]["conditions"][0]["requirement"].startswith("The entire")
    resumed_engine = ScopeEngine()
    resumed = DecompositionTwoWayIntent(resumed_engine, checkpoint=store)
    assert resumed.evaluate(resumed.compile(RUBRIC), INSTRUCTION, media) == result
    assert not resumed_engine.calls


def test_scope_cache_depends_on_instruction_and_returns_defensive_copies():
    engine = ScopeEngine()
    algorithm = DecompositionTwoWayIntent(engine)
    first = algorithm.scope(INSTRUCTION)
    first["operations"][0]["target"] = "mutated"
    assert algorithm.scope(INSTRUCTION)["operations"][0]["target"] == "cylinder"
    changed = "Remove only the feather from the hat"
    assert algorithm.scope(changed)["operations"][0]["source_phrase"] == changed
    assert len(engine.calls) == 2


def test_unvalidated_review_resolution_combinations_rejected():
    for keyword in ("review", "resolve_disagreements"):
        with pytest.raises(ValueError, match="not been validated"):
            DecompositionTwoWayIntent(Engine(), **{keyword: True})
