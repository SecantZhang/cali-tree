"""Blind-input isolation, source-first ordering, evidence tracing and cache reuse."""

from copy import deepcopy
import json

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayInventory
from critical.core.optimization.prompt.calitree.decomposition.decomposition_twoway import parse_image_inventory
from .test_decomposition_intent import ScopeEngine
from .test_decomposition_vision import INSTRUCTION, RUBRIC, images


def inventory():
    return {"scene": "Cylinder and sphere on a tabletop", "objects": [
        {"id": "o1", "name": "cylinder", "description": "Small gray solid cylinder", "location": "left",
         "count": 1, "alternatives": ["gray container"], "visibility": "uncertain"},
        {"id": "o2", "name": "sphere", "description": "Round red object", "location": "right",
         "count": None, "alternatives": [], "visibility": "clear"}]}


class InventoryEngine(ScopeEngine):
    def generate(self, user, **kwargs):
        if kwargs["system"].startswith("Inventory visually"):
            payload = json.loads(user)
            self.calls.append((payload, kwargs))
            return {"content": json.dumps(inventory())}
        return super().generate(user, **kwargs)


@pytest.mark.parametrize("field,value", [("count", True), ("count", 0), ("count", -1),
                                        ("alternatives", "container"), ("visibility", "absent"),
                                        ("name", ""), ("id", "1bad")])
def test_invalid_inventory_objects_rejected(field, value):
    bad = inventory()
    bad["objects"][0][field] = value
    with pytest.raises(ValueError):
        parse_image_inventory(bad)


def test_duplicate_inventory_ids_and_extra_metadata_rejected():
    bad = inventory()
    bad["objects"][1]["id"] = "o1"
    with pytest.raises(ValueError, match="duplicate"):
        parse_image_inventory(bad)
    bad = inventory()
    bad["human_label"] = "no"
    with pytest.raises(ValueError, match="Malformed"):
        parse_image_inventory(bad)
    assert parse_image_inventory({"scene": "Empty blank wall", "objects": []})["objects"] == []


def test_blind_caption_has_one_image_and_no_instruction_and_edited_is_not_in_source_binding(tmp_path):
    engine = InventoryEngine()
    algorithm = DecompositionTwoWayInventory(engine)
    result = algorithm.judge(RUBRIC, {"instruction": INSTRUCTION, "evidence": images(tmp_path),
                                     "target_label": "SECRET_LABEL", "metadata": "SECRET_EDITOR"})
    assert result["label"] == "partial"
    assert "SECRET" not in json.dumps(engine.calls)
    captions = [(i,p,k) for i,(p,k) in enumerate(engine.calls) if k["system"].startswith("Inventory visually")]
    assert len(captions) == 2
    assert all(p == {} and len(k["media_inputs"]) == 1 for _,p,k in captions)
    ground = next((i,p,k) for i,(p,k) in enumerate(engine.calls) if "conditions" in p and "media_inputs" in k)
    assert captions[0][0] < ground[0] < captions[1][0]
    assert ground[1]["source_inventory"] == inventory()
    assert "edited" not in json.dumps(ground[1])
    assert len(ground[2]["media_inputs"]) == 1
    check = next(p for p,_ in engine.calls if "condition" in p)
    preservation = next(p for p,k in engine.calls if k["system"].startswith("Compare two images"))
    aggregate = next(p for p,_ in engine.calls if "rubric_units" in p)
    assert check["image_inventory"] == preservation["image_inventory"] == aggregate["image_inventory"] == {"source":inventory(),"edited":inventory()}


def test_inventory_is_cached_by_image_content_not_instruction_and_copies_are_defensive(tmp_path):
    engine = InventoryEngine()
    algorithm = DecompositionTwoWayInventory(engine)
    media = images(tmp_path)
    observations = algorithm.observe(algorithm.decompose(INSTRUCTION), media)
    observations["image_inventory"]["source"]["objects"][0]["name"] = "tampered"
    changed = INSTRUCTION + ", please"
    second = algorithm.observe(algorithm.decompose(changed), media)
    assert second["image_inventory"]["source"]["objects"][0]["name"] == "cylinder"
    assert len([1 for p,k in engine.calls if k["system"].startswith("Inventory visually")]) == 2
    media["edited_image"].write_bytes(b"new edited image contents")
    algorithm.observe(algorithm.decompose(changed), media)
    assert len([1 for p,k in engine.calls if k["system"].startswith("Inventory visually")]) == 3


def test_inventory_trace_and_checkpoint_resume_preserve_uncertainty(tmp_path):
    engine = InventoryEngine()
    store = CheckpointStore(tmp_path / "inventory.jsonl")
    algorithm = DecompositionTwoWayInventory(engine, checkpoint=store)
    media = images(tmp_path)
    first = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, media)
    assert first.trace["observations"]["image_inventory"]["source"]["objects"][0]["visibility"] == "uncertain"
    next_engine = InventoryEngine()
    resumed = DecompositionTwoWayInventory(next_engine, checkpoint=store)
    assert resumed.evaluate(resumed.compile(RUBRIC), INSTRUCTION, media) == first
    assert not next_engine.calls


def test_missing_inventory_blocks_aggregation_before_model_calls(tmp_path):
    engine = InventoryEngine()
    algorithm = DecompositionTwoWayInventory(engine)
    policy = algorithm.compile(RUBRIC)
    observations = algorithm.observe(algorithm.decompose(INSTRUCTION), images(tmp_path))
    observations.pop("image_inventory")
    before = len(engine.calls)
    with pytest.raises(ValueError, match="Both image inventories"):
        algorithm.aggregate(policy, observations)
    assert len(engine.calls) == before


def test_extra_evidence_cannot_override_original_rubric_or_findings(tmp_path):
    engine = InventoryEngine()
    algorithm = DecompositionTwoWayInventory(engine)
    policy = algorithm.compile(RUBRIC)
    observations = algorithm.observe(algorithm.decompose(INSTRUCTION), images(tmp_path))
    algorithm._aggregation_context = lambda _: {"rubric_units": "replacement"}
    before = len(engine.calls)
    with pytest.raises(ValueError, match="reserved"):
        algorithm.aggregate(policy, observations)
    assert len(engine.calls) == before
