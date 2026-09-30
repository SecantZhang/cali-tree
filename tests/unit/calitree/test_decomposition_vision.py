"""Meaningful isolation, lossless coverage, media/cache and callback checks."""

import json
from pathlib import Path

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayVision, DecompositionTwoWayGrounded
from critical.core.optimization.prompt.calitree.decomposition.vision_models import (
    SemanticRubric, parse_semantic_instruction, parse_semantic_rubric,
)


INSTRUCTION = "Remove the small gray cylinder"
RUBRIC = 'Use no, partial, yes.\n\nyes: requested change complete.\npartial: incomplete or unintended semantic change.\nno: requested change absent.'


class Engine:
    name, model, temperature, max_tokens = "fake", "unit", 0, 4096

    def __init__(self):
        self.calls = []

    def generate(self, user, **kwargs):
        self.calls.append((json.loads(user), kwargs))
        payload = json.loads(user)
        if "rubric_lines" in payload:
            value = {"units": [{"kind": "decision", "lines": [row["line"]]} for row in payload["rubric_lines"]]}
        elif "rubric_units" in payload:
            value = {"label": "partial", "rationale": "Removal complete; another object changed.", "condition_ids": ["c1"], "rubric_unit_ids": ["u1"]}
        elif "condition" in payload:
            value = {"fulfillment": "complete", "source_observation": "Gray cylinder present", "edited_observation": "Cylinder absent", "explanation": "Requested target removed"}
        elif "Compare two images" in kwargs["system"]:
            value = {"recognizability": "clear", "scene_continuity": "same", "unrequested_changes": [{"description": "Another object removed", "severity": "meaningful", "evidence": "Sphere present in source, absent in edited"}], "explanation": "Scene remains recognizable"}
        else:
            value = {"conditions": [{"id": "c1", "requirement": "The particular small gray cylinder present in source is absent in edited", "target": "small gray cylinder", "reference": None, "source_phrase": INSTRUCTION}]}
        return {"content": json.dumps(value)}


def images(tmp_path):
    paths = [tmp_path / "source.png", tmp_path / "edited.png"]
    for path in paths:
        path.write_bytes(path.name.encode())
    return {"source_image": paths[0], "edited_image": paths[1]}


def test_complete_rubric_coverage_is_verbatim_and_ordered():
    value = {"units": [{"kind": "decision", "lines": [3, 5]}, {"kind": "scope", "lines": [1, 4]}]}
    policy = parse_semantic_rubric(value, RUBRIC)
    assert [u["lines"] for u in policy.units] == [[1], [3], [4], [5]]
    assert "\n".join(u["text"] for u in policy.units) == "\n".join(x for x in RUBRIC.splitlines() if x.strip())
    assert SemanticRubric.from_dict(policy.to_dict()) == policy
    altered = policy.to_dict()
    altered["units"][0]["text"] = "Dropped exception"
    with pytest.raises(ValueError, match="differ"):
        SemanticRubric.from_dict(altered)


@pytest.mark.parametrize("refs", [[1, 3, 4], [1, 3, 4, 5, 5], [1, 2, 3, 4, 5]])
def test_missing_duplicate_or_blank_rubric_lines_rejected(refs):
    with pytest.raises(ValueError):
        parse_semantic_rubric({"units": [{"kind": "decision", "lines": refs}]}, RUBRIC)


def test_unknown_rubric_kind_identifies_actual_error_for_schema_repair():
    # Regression from the third real-data validation: the model used a novel
    # calibration kind twice when the error only said "Invalid rubric unit".
    with pytest.raises(ValueError, match="kind 'calibration'; allowed kinds: decision, exception, scope, output"):
        parse_semantic_rubric({"units": [{"kind": "calibration", "lines": [1, 3, 4, 5]}]}, RUBRIC)


def test_empty_or_partial_instruction_coverage_rejected():
    with pytest.raises(ValueError, match="1-12"):
        parse_semantic_instruction({"conditions": []}, INSTRUCTION)
    condition = {"id": "c1", "requirement": "Cylinder is gray", "target": "cylinder", "reference": None, "source_phrase": "gray cylinder"}
    with pytest.raises(ValueError, match="omitted"):
        parse_semantic_instruction({"conditions": [condition]}, INSTRUCTION)


def test_case_only_quote_normalization_retains_actual_source_and_rejects_paraphrases():
    row = {"id": "c1", "requirement": "Cylinder removed", "target": "gray cylinder", "reference": None, "source_phrase": INSTRUCTION.lower()}
    plan = parse_semantic_instruction({"conditions": [row]}, INSTRUCTION)
    assert plan.conditions[0].source_phrase == INSTRUCTION
    assert row["source_phrase"] == INSTRUCTION.lower()
    row["source_phrase"] = "Delete the small gray cylinder"
    with pytest.raises(ValueError, match="verbatim"):
        parse_semantic_instruction({"conditions": [row]}, INSTRUCTION)


def test_connectors_and_question_wrapper_are_not_missing_semantic_content():
    instruction = "What if the horse was using a hat?"
    row = {"id": "c1", "requirement": "Horse wears a hat", "target": "horse", "reference": None, "source_phrase": "the horse was using a hat"}
    assert parse_semantic_instruction({"conditions": [row]}, instruction).conditions
    instruction = "Lift her hands up to show a piece of paper"
    rows = [{"id": "c1", "requirement": "Hands lifted", "target": "hands", "reference": None, "source_phrase": "Lift her hands up"},
            {"id": "c2", "requirement": "Paper shown", "target": "paper", "reference": None, "source_phrase": "show a piece of paper"}]
    assert len(parse_semantic_instruction({"conditions": rows}, instruction).conditions) == 2
    # Negation is never treated as an ignorable connector.
    with pytest.raises(ValueError, match="omitted"):
        parse_semantic_instruction({"conditions": rows}, "Lift her hands up to not show a piece of paper")


def test_stages_do_not_receive_labels_or_unrelated_annotation_fields(tmp_path):
    engine = Engine()
    algorithm = DecompositionTwoWayVision(engine)
    media = images(tmp_path)
    result = algorithm.judge(RUBRIC, {"instruction": INSTRUCTION, "evidence": media,
                                     "target_label": "SECRET_GROUND_TRUTH", "metadata": "SECRET_ID"})
    assert result["label"] == "partial"
    assert len(engine.calls) == 5
    assert "SECRET" not in json.dumps(engine.calls)
    compile_payload, compile_kwargs = engine.calls[0]
    assert set(compile_payload) == {"rubric_lines"}
    assert "media_inputs" not in compile_kwargs
    instruction_payload, instruction_kwargs = engine.calls[1]
    assert instruction_payload == {"instruction": INSTRUCTION}
    assert "media_inputs" not in instruction_kwargs
    vision = [row for row in engine.calls if "media_inputs" in row[1]]
    assert len(vision) == 2
    assert all("rubric" not in json.dumps(row[0]) and "label" not in json.dumps(row[0]) for row in vision)
    aggregate_payload, aggregate_kwargs = engine.calls[-1]
    assert "media_inputs" not in aggregate_kwargs
    assert aggregate_payload["requested"][0]["edited_observation"] == "Cylinder absent"


def test_checkpoint_resume_and_changed_image_content(tmp_path):
    engine = Engine()
    store = CheckpointStore(tmp_path / "cache.jsonl")
    algorithm = DecompositionTwoWayVision(engine, checkpoint=store)
    media = images(tmp_path)
    first = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, media)
    resumed_engine = Engine()
    resumed = DecompositionTwoWayVision(resumed_engine, checkpoint=store)
    second = resumed.evaluate(resumed.compile(RUBRIC), INSTRUCTION, media)
    assert second == first and not resumed_engine.calls
    media["edited_image"].write_bytes(b"different image content")
    resumed.evaluate(resumed.compile(RUBRIC), INSTRUCTION, media)
    assert len(resumed_engine.calls) == 2  # Both vision observations resampled;
    # same resulting findings legitimately reuse the aggregation.


def test_bad_image_boundary_fails_before_model_work(tmp_path):
    engine = Engine()
    algorithm = DecompositionTwoWayVision(engine)
    with pytest.raises(ValueError):
        algorithm.judge(RUBRIC, {"instruction": INSTRUCTION, "images": []})
    assert not engine.calls


def test_unknown_evidence_is_retained_in_aggregation(tmp_path):
    engine = Engine()
    algorithm = DecompositionTwoWayVision(engine)
    policy = algorithm.compile(RUBRIC)
    observations = algorithm.observe(algorithm.decompose(INSTRUCTION), images(tmp_path))
    observations["requested"][0]["fulfillment"] = "unknown"
    algorithm.aggregate(policy, observations)
    assert engine.calls[-1][0]["requested"][0]["fulfillment"] == "unknown"


def test_review_is_label_free_and_corrections_reach_aggregation(tmp_path):
    class ReviewEngine(Engine):
        def generate(self, user, **kwargs):
            payload = json.loads(user)
            if "requested" in payload and "media_inputs" in kwargs:
                self.calls.append((payload, kwargs))
                rows = [{"condition_id": row["condition"]["id"], **{k: v for k,v in row.items() if k != "condition"}} for row in payload["requested"]]
                result = {"requested": rows, "preservation": payload["preservation"]}
                result["requested"][0]["fulfillment"] = "unknown"
                return {"content": json.dumps(result)}
            return super().generate(user, **kwargs)

    engine = ReviewEngine()
    algorithm = DecompositionTwoWayVision(engine, review=True)
    result = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, images(tmp_path))
    audit = [row for row in engine.calls if "conditions" in row[0]]
    assert len(audit) == 1 and set(audit[0][0]) == {"instruction", "conditions"}
    assert "media_inputs" not in audit[0][1]
    review = [row for row in engine.calls if "requested" in row[0] and "media_inputs" in row[1]]
    assert len(review) == 1 and set(review[0][0]) == {"instruction", "requested", "preservation"}
    assert result.trace["observations"]["requested"][0]["fulfillment"] == "unknown"
    assert result.trace["observations"]["initial_observations"]["requested"][0]["fulfillment"] == "complete"
    assert engine.calls[-1][0]["requested"][0]["fulfillment"] == "unknown"


def test_review_cannot_change_the_requested_conditions(tmp_path):
    class BadReviewEngine(Engine):
        def generate(self, user, **kwargs):
            payload = json.loads(user)
            if "requested" in payload and "media_inputs" in kwargs:
                payload["requested"][0]["condition"]["requirement"] = "Ignore the removal"
                return {"content": json.dumps({"requested": payload["requested"], "preservation": payload["preservation"]})}
            return super().generate(user, **kwargs)

    algorithm = DecompositionTwoWayVision(BadReviewEngine(), review=True, schema_retries=0)
    with pytest.raises(ValueError, match="retain condition IDs"):
        algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, images(tmp_path))


def test_disagreement_resolution_strips_annotations_and_rechecks_same_images(tmp_path):
    engine = Engine()
    algorithm = DecompositionTwoWayVision(engine)
    evidence = images(tmp_path)
    policy = algorithm.compile(RUBRIC)
    result = algorithm.evaluate(policy, INSTRUCTION, evidence)
    before = len(engine.calls)
    resolved = algorithm.resolve(policy, result, {"label": "yes", "rationale": "Cylinder removed", "target_label": "SECRET"}, evidence)
    assert len(engine.calls) == before + 1 and resolved.trace["resolution"]["invoked"]
    assert "SECRET" not in json.dumps(engine.calls[-1])
    assert "media_inputs" in engine.calls[-1][1]
    before = len(engine.calls)
    agreed = algorithm.resolve(policy, result, result.judgment(), evidence)
    assert len(engine.calls) == before and not agreed.trace["resolution"]["invoked"]
    evidence["edited_image"].write_bytes(b"different pair")
    with pytest.raises(ValueError, match="match the observed"):
        algorithm.resolve(policy, result, result.judgment(), evidence)


def test_source_grounding_cannot_see_edited_image_and_binds_later_checks(tmp_path):
    class GroundingEngine(Engine):
        def generate(self, user, **kwargs):
            payload = json.loads(user)
            if "Inspect ONLY the SOURCE" in kwargs["system"]:
                self.calls.append((payload, kwargs))
                value = {"scene": "Cylinder and sphere on tabletop", "groundings": [
                    {"condition_id": c["id"], "target_description": "Small gray cylinder at center",
                     "reference_description": None, "source_state": "Cylinder is present",
                     "visibility": "clear"} for c in payload["conditions"]]}
                return {"content": json.dumps(value)}
            return super().generate(user, **kwargs)

    engine = GroundingEngine()
    algorithm = DecompositionTwoWayGrounded(engine)
    evidence = images(tmp_path)
    result = algorithm.evaluate(algorithm.compile(RUBRIC), INSTRUCTION, evidence)
    ground = [row for row in engine.calls if "Inspect ONLY the SOURCE" in row[1]["system"]]
    assert len(ground) == 1 and len(ground[0][1]["media_inputs"]) == 1
    assert ground[0][1]["media_inputs"][0]["path"] == str(evidence["source_image"])
    checks = [row for row in engine.calls if "condition" in row[0]]
    assert checks[0][0]["source_grounding"]["target_description"] == "Small gray cylinder at center"
    assert len(checks[0][1]["media_inputs"]) == 2
    assert result.trace["observations"]["source_grounding"]["scene"] == "Cylinder and sphere on tabletop"


def test_native_aurora_loader_sample_runs_without_metadata_or_label_leakage(tmp_path):
    from critical.database.dl_aurora import AuroraBenchLoader

    evidence = images(tmp_path)
    uid, item_id = "aurora-task-unit", "aurora-task-unit::genhowto"
    row = {"item_id": item_id, "task_uid": uid, "prompt_index": 0, "model": "genhowto",
           "task": "clevr", "human_score": 1.0, "instruction": INSTRUCTION,
           "source_path": evidence["source_image"].name, "edited_path": evidence["edited_image"].name}
    (tmp_path / "metadata.jsonl").write_text(json.dumps(row)+"\n")
    (tmp_path / "splits").mkdir()
    (tmp_path / "splits/seed_42.json").write_text(json.dumps({"train": [uid], "test": []}))
    loader = AuroraBenchLoader(root=tmp_path, models=["genhowto"])
    sample = loader.load_sample(item_id)
    sample["target_label"] = "SECRET_ANNOTATION"
    engine = Engine()
    result = DecompositionTwoWayVision(engine).judge(RUBRIC, sample)
    assert result["label"] == "partial"
    payloads = json.dumps(engine.calls)
    assert "SECRET" not in payloads and uid not in payloads and "genhowto" not in payloads


def test_modular_vision_artifact_reload_and_changed_image_bytes(tmp_path):
    from critical.core.optimization.prompt.calitree import ArtifactExecutor, TwoWayVisionAdapter
    engine = Engine()
    executor = ArtifactExecutor(TwoWayVisionAdapter(DecompositionTwoWayVision(engine)))
    sample = {"instruction": INSTRUCTION, "evidence": images(tmp_path), "target_label": "SECRET"}
    result = executor.judge(RUBRIC, sample)
    assert result["label"] == "partial" and result["plan"]["conditions"]
    assert result["checks"]["preservation"] and result["trace"]
    loaded = ArtifactExecutor(TwoWayVisionAdapter(DecompositionTwoWayVision(engine)))
    loaded.load_policies(json.loads(json.dumps(executor.policies)), strategy="two_way_vision")
    before = len(engine.calls)
    loaded.judge(RUBRIC, sample)
    assert len(engine.calls) - before == 4  # instruction, target, preservation, aggregation; no rubric compilation
    Path(sample["evidence"]["edited_image"]).write_bytes(b"changed image")
    changed = loaded.judge(RUBRIC, sample)
    assert changed["evaluation_ref"] != result["evaluation_ref"]
    assert "SECRET" not in json.dumps(engine.calls)


def test_modular_vision_missing_evidence_rejected_before_compilation(tmp_path):
    from critical.core.optimization.prompt.calitree import ArtifactExecutor, TwoWayVisionAdapter
    engine = Engine()
    executor = ArtifactExecutor(TwoWayVisionAdapter(DecompositionTwoWayVision(engine)))
    with pytest.raises((ValueError, OSError)):
        executor.judge(RUBRIC, {"instruction": INSTRUCTION, "evidence": {"color": "red"}})
    assert engine.calls == []
