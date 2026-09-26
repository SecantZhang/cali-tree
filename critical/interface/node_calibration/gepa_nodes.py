"""Workflow node for the GEPA-optimized flat judge prompt baseline.

GEPA (github.com/gepa-ai/gepa) is a reflective prompt-optimization framework, run entirely
outside this package (an isolated Python 3.10+ venv -- see `run/gepa_baseline/`) since it
requires a newer Python than this project's main venv. The core GEPA package loads the
committed artifact and builds a tree. This node exposes that tree to the workflow, like
`RubricLiteFrozenNodeExecutor` wraps a frozen Rubric-Lite artifact: a single-root, no-children
`prompt_tree` fed unchanged into the existing `calitree_judge` -> `calitree_eval` nodes. This
gives GEPA a baseline directly comparable to "Initial rubric" and "Global TextGrad" without
any change to the tree-building or evaluation code.
"""

from __future__ import annotations

from ...core.optimization.prompt.gepa import (
    ARTIFACT_ROOT,
    GEPA_MODEL_VERSIONS,
    load_frozen_prompt_tree,
)

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

@register
class GepaFrozenNodeExecutor(NodeExecutor):
    """Load a GEPA-optimized global-prompt artifact without training or model calls."""

    node_type = "gepa_frozen"
    category = "node_calibration"
    subcategory = "prompt"
    input_sockets: dict[str, str] = {}
    output_sockets = {"prompt_tree": "prompt_tree"}
    param_schema = {
        "model_version": {
            "type": "enum",
            "options": list(GEPA_MODEL_VERSIONS),
            "default": "gepa_v1_imagenhub",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        model_version = str(ctx.params.get("model_version") or "gepa_v1_imagenhub")
        try:
            tree, artifact = load_frozen_prompt_tree(
                model_version, artifact_root=ARTIFACT_ROOT
            )
        except ValueError as exc:
            return NodeRunResult(status="error", error=str(exc))
        return NodeRunResult(
            outputs={"prompt_tree": tree},
            meta={
                "dry_run": ctx.dry_run,
                "architecture": "gepa",
                "model_version": model_version,
                "model_calls": 0,
                "status": artifact.get("status"),
            },
        )
