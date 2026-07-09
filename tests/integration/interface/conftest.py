"""Shared fixture-tree builder for interface integration tests."""

import pytest

from tests.e2e_fixture import build as build_fixture_tree
from vejudge.interface.server.graph import EdgeSpec, GraphSpec, NodeSpec


def _graph():
    return GraphSpec(
        nodes=[
            NodeSpec(id="peanut_src", type="peanut_source", params={}),
            NodeSpec(id="ds", type="dataset", params={}),
            NodeSpec(id="engine", type="lm_engine", params={"engine_kind": "gpt"}),
            NodeSpec(id="judge_text", type="judge_text", params={"metrics": ["M3"]}),
            NodeSpec(id="eval", type="eval_text", params={}),
        ],
        edges=[
            EdgeSpec("peanut_src", "raw_dataset", "ds", "raw_dataset"),
            EdgeSpec("ds", "dataset", "judge_text", "dataset"),
            EdgeSpec("engine", "engine_config", "judge_text", "engine_config"),
            EdgeSpec("judge_text", "judge_result", "eval", "judge_result"),
            EdgeSpec("ds", "labels", "eval", "labels"),
        ],
    )


@pytest.fixture
def fixture_tree(tmp_path, monkeypatch):
    import vejudge.config as config
    from vejudge.database.dl_peanut_eval.loader import _use_cases

    paths = build_fixture_tree(tmp_path)
    monkeypatch.setattr(config, "DATA_ROOT", paths.data_root)
    monkeypatch.setattr(config, "RENDERED_ROOT", paths.rendered_root)
    monkeypatch.setattr(config, "HUMAN_ANNOTATIONS_ROOT", paths.annotations_root)
    monkeypatch.setattr(config, "USE_CASES_CONFIG", paths.use_cases_path)
    _use_cases.cache_clear()
    yield
    _use_cases.cache_clear()


@pytest.fixture
def quick_eval_graph():
    return _graph()


@pytest.fixture
def fake_engine(monkeypatch):
    from vejudge.lm_engine import openai_compat
    from vejudge.lm_engine.creds import PlutoCreds

    monkeypatch.setattr(
        "vejudge.interface.node_vejudge.judge_text_node.load_creds",
        lambda: PlutoCreds(token="sk-test", base_url="https://primary"),
    )
    monkeypatch.setattr(
        "vejudge.interface.node_vejudge.judge_video_node.load_creds",
        lambda: PlutoCreds(token="sk-test", base_url="https://primary"),
    )

    def fake_chat(**kwargs):
        return openai_compat.ChatResult(
            content='{"score_1_to_5": 4, "fully_complete": true, "missing_aspects": [], '
            '"reasoning_lines": ["a", "b"]}',
            prompt_tokens=1, completion_tokens=1, total_tokens=2,
            endpoint_host="primary", latency_s=0.01, model="m",
        )

    monkeypatch.setattr(openai_compat, "chat_completion", fake_chat)
