from vejudge.interface.node_vejudge.lm_engine_node import ENGINE_KINDS, LMEngineNodeExecutor


def test_default_params_produce_a_json_safe_config_dict(make_ctx):
    ctx = make_ctx(params={})
    result = LMEngineNodeExecutor().run(ctx)

    assert result.status == "done"
    cfg = result.outputs["engine_config"]
    assert cfg == {
        "engine_kind": "gpt",
        "model": None,
        "temperature": 0.3,
        "max_tokens": 4096,
        "concurrency": 1,
    }
    # Every value must be a plain JSON-safe primitive — no live objects (this is the whole
    # point of this node: never carry a live LMEngine across a socket).
    import json
    json.dumps(cfg)


def test_custom_params_flow_through(make_ctx):
    ctx = make_ctx(params={
        "engine_kind": "gemini", "model": "gemini-2.5-pro", "temperature": 0.7,
        "max_tokens": 2048, "concurrency": 8,
    })
    result = LMEngineNodeExecutor().run(ctx)

    assert result.outputs["engine_config"] == {
        "engine_kind": "gemini", "model": "gemini-2.5-pro", "temperature": 0.7,
        "max_tokens": 2048, "concurrency": 8,
    }


def test_unknown_engine_kind_is_a_node_error(make_ctx):
    ctx = make_ctx(params={"engine_kind": "not-a-real-engine"})
    result = LMEngineNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "not-a-real-engine" in result.error


def test_no_input_sockets():
    assert LMEngineNodeExecutor.input_sockets == {}


def test_engine_kinds_cover_all_provider_families():
    # Expanded from the original 3 (gemini/gpt/qwen) to provider-accurate families so the
    # frontend model dropdown can group the full model catalog by real provider.
    assert set(ENGINE_KINDS) == {
        "gemini", "gpt", "qwen", "claude", "deepseek", "llama", "kimi",
    }


def test_new_provider_family_engine_kind_flows_through(make_ctx):
    ctx = make_ctx(params={"engine_kind": "claude", "model": "claude-sonnet-4.5"})
    result = LMEngineNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["engine_config"]["engine_kind"] == "claude"
    assert result.outputs["engine_config"]["model"] == "claude-sonnet-4.5"
