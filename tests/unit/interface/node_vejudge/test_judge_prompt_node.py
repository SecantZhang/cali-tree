from vejudge.interface.node_vejudge.judge_prompt_node import JudgePromptNodeExecutor


def test_builtin_preset_resolves_to_a_builtin_spec(make_ctx):
    ctx = make_ctx(params={"preset": "M3"})
    result = JudgePromptNodeExecutor().run(ctx)
    assert result.status == "done"
    spec = result.outputs["judge_spec"]
    assert spec == {"kind": "builtin", "metric_id": "M3", "modality": "text", "label": "M3"}


def test_video_preset_carries_video_modality(make_ctx):
    ctx = make_ctx(params={"preset": "M5"})
    spec = JudgePromptNodeExecutor().run(ctx).outputs["judge_spec"]
    assert spec["modality"] == "video"


def test_unknown_preset_is_a_node_error(make_ctx):
    ctx = make_ctx(params={"preset": "M99"})
    result = JudgePromptNodeExecutor().run(ctx)
    assert result.status == "error"


def test_custom_preset_builds_a_custom_spec(make_ctx):
    ctx = make_ctx(params={
        "preset": "custom",
        "spec_id": "my_judge",
        "label": "My Judge",
        "modality": "video",
        "user_template": "Rate {user_prompt}",
        "expected_fields": ["score_1_to_5"],
        "score_path": "score_1_to_5",
        "target_dimension": "story_flow_visuals",
    })
    result = JudgePromptNodeExecutor().run(ctx)
    assert result.status == "done"
    spec = result.outputs["judge_spec"]
    assert spec["kind"] == "custom"
    assert spec["spec_id"] == "my_judge"
    assert spec["label"] == "My Judge"
    assert spec["modality"] == "video"
    assert spec["target_dimension"] == "story_flow_visuals"


def test_custom_without_user_template_is_a_node_error(make_ctx):
    ctx = make_ctx(params={"preset": "custom", "user_template": "  "})
    result = JudgePromptNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "user_template" in result.error
