"""Judge Prompt Node — produces a ``judge_spec`` artifact (a judge's identity as data).

A config-only node (like the LM Engine node — no gateway call). Either selects a built-in
metric preset (M1-M6, which delegate to the existing prompt/validation/alignment code) or
defines a custom free-text judge. Its ``judge_spec`` output wires into the generic Judge
node. See ``judge_spec.py`` for the artifact shape.
"""

from __future__ import annotations

from typing import Any

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .judge_spec import CUSTOM_TARGET_DIMENSIONS, PRESET_METRIC_IDS, TARGET_DIMENSIONS, builtin_spec


@register
class JudgePromptNodeExecutor(NodeExecutor):
    node_type = "judge_prompt"
    category = "node_vejudge"
    input_sockets: dict = {}
    output_sockets = {"judge_spec": "judge_spec"}
    param_schema = {
        "preset": {"type": "enum", "options": [*PRESET_METRIC_IDS, "custom"], "default": "M1"},
        # Custom-only fields (ignored unless preset == "custom").
        "spec_id": {"type": "string", "default": "custom"},
        "label": {"type": "string", "default": None},
        "modality": {"type": "enum", "options": ["text", "image", "video"], "default": "text"},
        "system": {"type": "text", "default": None},
        "user_template": {"type": "text", "default": None},
        "expected_fields": {"type": "list[string]", "default": None},
        "score_path": {"type": "string", "default": "score_1_to_5"},
        "target_dimension": {
            "type": "enum", "options": CUSTOM_TARGET_DIMENSIONS, "default": TARGET_DIMENSIONS[0],
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        preset = p.get("preset") or "M1"

        if preset != "custom":
            if preset not in PRESET_METRIC_IDS:
                return NodeRunResult(status="error", error=f"Unknown metric preset '{preset}'")
            spec: dict[str, Any] = builtin_spec(preset)
        else:
            user_template = p.get("user_template") or ""
            if not user_template.strip():
                return NodeRunResult(
                    status="error",
                    error="A custom Judge Prompt requires a non-empty 'user_template'.",
                )
            spec_id = (p.get("spec_id") or "custom").strip() or "custom"
            spec = {
                "kind": "custom",
                "spec_id": spec_id,
                "label": (p.get("label") or spec_id),
                "modality": p.get("modality") or "text",
                "system": p.get("system"),
                "user_template": user_template,
                "expected_fields": p.get("expected_fields") or [],
                "score_path": p.get("score_path") or "score_1_to_5",
                "target_dimension": p.get("target_dimension") or TARGET_DIMENSIONS[0],
                "version": "custom-v1",
            }

        return NodeRunResult(
            outputs={"judge_spec": spec},
            meta={"kind": spec["kind"], "modality": spec["modality"], "label": spec.get("label")},
        )
