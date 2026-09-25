from vejudge.core.area.rubrics import area_rubric_spec
from vejudge.evidence import ArtifactRef, EvaluationUnit, EvidenceBundle, EvidenceManifest
from vejudge.interface.node_vejudge import area_judge_node
from vejudge.interface.node_vejudge.area_aggregation_node import AreaAggregationNodeExecutor
from vejudge.interface.node_vejudge.area_judge_node import AreaJudgeNodeExecutor


class FakeEngine:
    def __init__(self):
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return {
            "content": (
                '{"score_1_to_5": 4, "severity": "minor", "confidence": 0.8, '
                '"rationale": "slight jump", "cited_timestamps": [1.9]}'
            ),
            "model": "fake",
            "promptTokens": 1,
            "completionTokens": 1,
            "totalTokens": 2,
        }


def _inputs(tmp_path, evidence_hash="evidence-a"):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    unit = EvaluationUnit(
        unit_id="edit_boundary-0000-x",
        unit_type="edit_boundary",
        start_seconds=1.0,
        end_seconds=5.0,
        applicable_rubrics=["transition_smoothness"],
        artifacts=[ArtifactRef(
            artifact_id="a", kind="short_clip", path=str(clip), sha256="s",
            media_type="video/mp4",
        )],
    )
    manifest = EvidenceManifest(
        item_id="item", cache_key="cache", evidence_hash=evidence_hash,
        source_video_path="/video", source_video_sha256="s",
        preprocessing_config_hash="c", preprocessor_version="v", units=[unit],
    )
    bundle = EvidenceBundle(
        schema_version="evidence-bundle-v1", preprocessing_config={},
        preprocessing_config_hash="c", preprocessor_version="v",
        manifests={"item": manifest},
    )
    return {
        "samples": {"item": {"item_id": "item", "input": {"user_prompt": "smooth edit"}}},
        "evidence_bundle": bundle.to_dict(),
        "engine_config": {"engine_kind": "gemini", "concurrency": 1},
        "area_rubric_spec": area_rubric_spec("transition_smoothness"),
    }


def test_area_judge_dry_run_counts_selected_units(tmp_path, make_ctx):
    result = AreaJudgeNodeExecutor().run(
        make_ctx(inputs=_inputs(tmp_path), dry_run=True)
    )
    assert result.meta["estimated_calls"] == {"area_judge_calls": 1}
    assert result.outputs["area_judge_result"]["item"]["selection"]["coverage"] == 1.0


def test_evidence_hash_invalidates_unit_checkpoint(tmp_path, make_ctx, monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(area_judge_node, "get_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(area_judge_node, "load_creds", lambda **kwargs: object())
    ctx = make_ctx(inputs=_inputs(tmp_path, "a"), dry_run=False, allow_live=True)
    first = AreaJudgeNodeExecutor().run(ctx)
    assert first.outputs["area_judge_result"]["item"]["units"][0]["valid"] is True
    AreaJudgeNodeExecutor().run(ctx)
    assert engine.calls == 1

    ctx.inputs = _inputs(tmp_path, "b")
    AreaJudgeNodeExecutor().run(ctx)
    assert engine.calls == 2
    assert any("::a::item::" in key for key in ctx.checkpoint.keys())
    assert any("::b::item::" in key for key in ctx.checkpoint.keys())


def test_aggregation_node_accepts_fan_in_and_emits_both_outputs(make_ctx):
    area = {
        "item": {
            "rubric_id": "transition_smoothness",
            "evidence_hash": "e",
            "selection": {"selected": 1, "total": 1, "coverage": 1},
            "units": [{
                "unit_id": "u", "unit_type": "edit_boundary", "duration_seconds": 1,
                "score": 4, "severity": "none", "valid": True,
            }],
        }
    }
    result = AreaAggregationNodeExecutor().run(make_ctx(inputs={
        "area_judge_result": [area], "unit_labels": [],
    }))
    assert result.outputs["decomposition_features"]["item"]["features"]
    assert result.outputs["judge_result"]["item"]["area::story_flow_visuals"]["parsed"][
        "score_1_to_5"
    ] == 4
