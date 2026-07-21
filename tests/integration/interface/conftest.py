"""Shared fixture-tree builder for interface integration tests."""

import pytest

from tests.e2e_fixture import build as build_fixture_tree
from vejudge.interface.server.graph import EdgeSpec, GraphSpec, NodeSpec


def _graph():
    return GraphSpec(
        nodes=[
            NodeSpec(id="peanut_src", type="peanut_source", params={}),
            # Aggregated labels (mean) — the Dataset node now defaults to "none" (per-rater),
            # but this shared eval-graph fixture asserts judge-vs-consensus agreement.
            NodeSpec(id="ds", type="dataset", params={"aggregation_method": "mean"}),
            NodeSpec(id="engine", type="lm_engine", params={"engine_kind": "gpt"}),
            NodeSpec(id="prompt", type="judge_prompt", params={"preset": "M3"}),
            NodeSpec(id="judge", type="judge", params={}),
            NodeSpec(id="eval", type="eval", params={}),
        ],
        edges=[
            EdgeSpec("peanut_src", "raw_dataset", "ds", "raw_dataset"),
            EdgeSpec("ds", "samples", "judge", "samples"),
            EdgeSpec("engine", "engine_config", "judge", "engine_config"),
            EdgeSpec("prompt", "judge_spec", "judge", "judge_spec"),
            EdgeSpec("judge", "judge_result", "eval", "judge_result"),
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
    monkeypatch.setattr(config, "VEBENCH_ROOT", paths.vebench_root)
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
        "vejudge.interface.node_vejudge.judge_node.load_creds",
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
