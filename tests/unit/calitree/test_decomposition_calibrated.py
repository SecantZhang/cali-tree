"""Offline contracts for image-backed grading and supervised reference isolation."""

from copy import deepcopy
import json

from PIL import Image
import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import (
    DecompositionTwoWayCalibratedVision, VisualReference, VisualReferenceBank,
)
from critical.core.optimization.prompt.calitree.decomposition.visual_calibration import parse_visual_grade
from .test_decomposition_intent import ScopeEngine
from .test_decomposition_vision import INSTRUCTION, RUBRIC


def image(path, color):
    Image.new("RGB", (3, 3), color).save(path)
    return path


def inputs(tmp_path):
    references = tuple(VisualReference(f"train-{i}", INSTRUCTION, ("The cylinder is removed",),
                                      image(tmp_path / f"ref-{i}-source.png", (i * 50, 0, 0)),
                                      image(tmp_path / f"ref-{i}-edited.png", (0, i * 50, 0)), label, i)
                       for i, label in enumerate(("no", "partial", "yes")))
    evidence = {"source_image": image(tmp_path / "query-source.png", "white"),
                "edited_image": image(tmp_path / "query-edited.png", "blue")}
    return references, evidence


class VisualEngine(ScopeEngine):
    def __init__(self, invalid=False):
        super().__init__()
        self.invalid = invalid

    def generate(self, user, **kwargs):
        if "\nINPUT_JSON: " not in user:
            return super().generate(user, **kwargs)
        payload = json.loads(user.split("\nINPUT_JSON: ", 1)[1].split("\nSCHEMA_ERROR: ", 1)[0])
        self.calls.append((payload, kwargs))
        value = {"label": "partial", "rationale": "Cylinder removed; another object changed.",
                 "condition_findings": [{"condition_id": c["id"], "source_observation": "Cylinder present",
                                         "edited_observation": "Cylinder absent", "fulfillment": "complete"}
                                        for c in payload["query"]["condition_plan"]],
                 "rubric_unit_ids": [payload["rubric_units"][0]["id"]],
                 "reference_ids": [payload["calibration_examples"][0]["id"]] if payload["calibration_examples"] else [],
                 "rubric_conflicts": []}
        if self.invalid:
            value["condition_findings"] = []
        return {"content": json.dumps(value), "parsed": value}


def test_roles_are_adjacent_and_query_annotations_are_withheld(tmp_path):
    references, evidence = inputs(tmp_path)
    engine = VisualEngine()
    algorithm = DecompositionTwoWayCalibratedVision(engine, references=references)
    result = algorithm.judge(RUBRIC, {"instruction": INSTRUCTION, "evidence": evidence,
                                     "target_label": "SECRET_HUMAN_LABEL", "metadata": "SECRET_EDITOR"})
    assert result["label"] == "partial"
    assert "SECRET" not in json.dumps(engine.calls)
    payload, kwargs = engine.calls[-1]
    assert "system" not in kwargs  # Retain the frozen experiment's message placement.
    assert set(payload["query"]) == {"instruction", "condition_plan", "source_image_position", "edited_image_position"}
    assert payload["query"]["source_image_position"] == 7
    assert payload["query"]["edited_image_position"] == 8
    assert [r["human_label"] for r in payload["calibration_examples"]] == ["no", "partial", "yes"]
    media = kwargs["media_inputs"]
    assert len(media) == 16
    for i in range(8):
        assert media[2 * i]["type"] == "text"
        assert media[2 * i + 1]["type"] == "image"
        assert f"Image {i + 1}:" in media[2 * i]["text"]
    assert "QUERY SOURCE" in media[-4]["text"] and "QUERY EDITED" in media[-2]["text"]
    assert "REFERENCE r1 SOURCE" in media[0]["text"]
    assert all("media_inputs" not in k for p, k in engine.calls if "instruction" in p and "query" not in p)


def test_no_reference_arm_does_not_require_calibration_annotations(tmp_path):
    _, evidence = inputs(tmp_path)
    engine = VisualEngine()
    algorithm = DecompositionTwoWayCalibratedVision(engine)
    result = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, evidence)
    assert result.trace["decision"]["reference_ids"] == []
    assert result.trace["grade_input"]["calibration_examples"] == []
    assert len(result.trace["media"]) == 4


def test_independent_parent_stages_cannot_silently_bypass_visual_calibration():
    algorithm = DecompositionTwoWayCalibratedVision(VisualEngine())
    with pytest.raises(NotImplementedError, match="jointly observes"):
        algorithm.observe(None, None)
    with pytest.raises(NotImplementedError, match="query image pair"):
        algorithm.aggregate(None, None)


def test_cache_resume_revalidates_findings_and_separates_changed_query_pixels(tmp_path):
    references, evidence = inputs(tmp_path)
    checkpoint = CheckpointStore(tmp_path / "checkpoint.jsonl")
    engine = VisualEngine()
    algorithm = DecompositionTwoWayCalibratedVision(engine, references=references, checkpoint=checkpoint)
    policy = algorithm.compile(RUBRIC)
    result = algorithm.evaluate(policy, INSTRUCTION, evidence)
    call_count = len(engine.calls)
    assert algorithm.evaluate(policy, INSTRUCTION, evidence) == result
    assert len(engine.calls) == call_count
    resumed_engine = VisualEngine()
    resumed = DecompositionTwoWayCalibratedVision(resumed_engine, references=references, checkpoint=checkpoint)
    assert resumed.evaluate(resumed.compile(RUBRIC), INSTRUCTION, evidence) == result
    assert resumed_engine.calls == []
    image(evidence["edited_image"], "yellow")
    resumed.evaluate(policy, INSTRUCTION, evidence)
    assert len(resumed_engine.calls) == 1
    assert resumed_engine.calls[0][0]["query"]["instruction"] == INSTRUCTION
    key = resumed.calls[-1]["key"]
    corrupted = deepcopy(checkpoint.get(key))
    corrupted["condition_findings"] = []
    checkpoint.put(key, corrupted)
    broken = DecompositionTwoWayCalibratedVision(VisualEngine(), references=references, checkpoint=checkpoint)
    with pytest.raises(ValueError, match="condition coverage"):
        broken.evaluate(policy, INSTRUCTION, evidence)


def test_schema_repair_is_bounded_without_quality_retries(tmp_path):
    _, evidence = inputs(tmp_path)
    engine = VisualEngine(invalid=True)
    algorithm = DecompositionTwoWayCalibratedVision(engine)
    with pytest.raises(ValueError, match="condition coverage"):
        algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, evidence)
    assert len([p for p, _ in engine.calls if "query" in p]) == 2
    assert [c["attempt"] for c in algorithm.calls if c["stage"] == "aggregate_visual"] == [0, 1]


def test_retrieval_excludes_query_source_pixels_in_other_encodings(tmp_path):
    references, _ = inputs(tmp_path)
    alternative = VisualReference("other-no", "Keep the sphere", ("The sphere remains",),
                                  image(tmp_path / "alternative.png", "green"), references[0].edited_image, "no", 0)
    bank = VisualReferenceBank([*references, alternative])
    copied = tmp_path / "copy.bmp"
    Image.open(references[0].source_image).save(copied)
    algorithm = DecompositionTwoWayCalibratedVision(VisualEngine())
    plan = algorithm.decompose(INSTRUCTION)
    selected = bank.select(plan, copied)
    assert references[0] not in selected and alternative in selected
    assert len({r.id for r in selected}) == 3
    image(references[1].edited_image, "purple")
    with pytest.raises(ValueError, match="reference images changed"):
        bank.select(plan, copied)


@pytest.mark.parametrize("score,label", [(True, "partial"), (float("nan"), "partial"), (3, "yes"), (1, "yes")])
def test_bad_training_annotations_are_rejected(tmp_path, score, label):
    source = image(tmp_path / "source.png", "white")
    with pytest.raises(ValueError):
        VisualReference("ref", INSTRUCTION, ("Cylinder removed",), source, source, label, score)


def test_grade_requires_complete_condition_coverage_and_valid_reference_citations(tmp_path):
    references, evidence = inputs(tmp_path)
    algorithm = DecompositionTwoWayCalibratedVision(VisualEngine(), references=references)
    result = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, evidence)
    payload = result.trace["grade_input"]
    for change in (lambda r: r.update(reference_ids=[]), lambda r: r.update(reference_ids=["UNKNOWN"]),
                   lambda r: r["condition_findings"].append(deepcopy(r["condition_findings"][0]))):
        bad = deepcopy(result.trace["decision"])
        change(bad)
        with pytest.raises(ValueError):
            parse_visual_grade(bad, payload)
