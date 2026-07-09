"""LM Engine Node executor — a reusable, swappable engine config for Judge nodes.

Per ``interface.md``'s original (until now unimplemented) spec: Judge nodes attach to an
engine config rather than embedding model/temperature/concurrency themselves, so the same
graph can be re-pointed at a different model/version without touching the Judge nodes.

The output is a plain JSON-safe dict, never a live ``LMEngine`` instance — an ``LMEngine``
holds an open ``LLMHistoryWriter`` file handle and lazily-loaded credentials, neither of
which survive the hard JSON-encode boundaries every node output passes through today (the
run-status HTTP route's per-poll serialization, and the websocket's ``partial_result``
event). Judge nodes call ``get_engine(**config)`` themselves, exactly as they already did
with their own inline params — only the source of those kwargs moves upstream.
"""

from __future__ import annotations

from typing import Any

from ... import config
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

ENGINE_KINDS = ["gemini", "gpt", "qwen", "claude", "deepseek", "llama", "kimi"]


@register
class LMEngineNodeExecutor(NodeExecutor):
    node_type = "lm_engine"
    category = "node_lm_engine"
    input_sockets: dict[str, str] = {}
    output_sockets = {"engine_config": "engine_config"}
    param_schema = {
        "engine_kind": {"type": "enum", "options": ENGINE_KINDS, "default": "gpt"},
        "model": {"type": "string", "default": config.DEFAULT_TEXT_MODEL},
        "temperature": {"type": "number", "default": 0.3},
        "max_tokens": {"type": "number", "default": 4096, "min": 1},
        "concurrency": {"type": "number", "default": 1, "min": 1},
        # Not wired to any behavior yet — vejudge/lm_engine/health.py exists at the engine
        # layer but isn't hooked into the interface's Judge nodes at all today (same
        # "shape now, behavior later" precedent as the Preprocessing Node's stub params).
        "health_check": {"type": "bool", "default": False},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        engine_kind = p.get("engine_kind", "gpt")
        if engine_kind not in ENGINE_KINDS:
            return NodeRunResult(
                status="error", error=f"Unknown engine kind '{engine_kind}'. Options: {ENGINE_KINDS}"
            )
        engine_config: dict[str, Any] = {
            "engine_kind": engine_kind,
            "model": p.get("model") or None,
            "temperature": p.get("temperature", 0.3),
            "max_tokens": int(p.get("max_tokens") or 4096),
            "concurrency": max(1, int(p.get("concurrency") or 1)),
        }
        return NodeRunResult(outputs={"engine_config": engine_config}, meta={})
