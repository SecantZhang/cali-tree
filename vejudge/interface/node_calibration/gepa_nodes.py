"""Workflow node for the GEPA-optimized flat judge prompt baseline.

GEPA (github.com/gepa-ai/gepa) is a reflective prompt-optimization framework, run entirely
outside this package (an isolated Python 3.10+ venv -- see `run/gepa_baseline/`) since it
requires a newer Python than this project's main venv. This node's only job is to load the
one committed artifact its offline optimization run produces and wrap it exactly like
`RubricLiteFrozenNodeExecutor` wraps a frozen Rubric-Lite artifact: a single-root, no-children
`prompt_tree` fed unchanged into the existing `calitree_judge` -> `calitree_eval` nodes. This
gives GEPA a baseline directly comparable to "Initial rubric" and "Global TextGrad" without
any change to the tree-building or evaluation code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

ARTIFACT_ROOT = (
    Path(__file__).resolve().parents[2] / "core" / "calibration" / "artifacts"
)
GEPA_MODEL_VERSIONS = ("gepa_v1_imagenhub",)


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
        if model_version not in GEPA_MODEL_VERSIONS:
            return NodeRunResult(
                status="error",
                error=f"Unknown frozen GEPA model {model_version!r}",
            )
        artifact_path = ARTIFACT_ROOT / f"{model_version}.json"
        try:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            prompt = str(artifact["prompt"])
            if not prompt.strip():
                raise ValueError("artifact prompt is empty")
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return NodeRunResult(
                status="error",
                error=f"Invalid frozen GEPA artifact {model_version!r}: {exc}",
            )
        tree: dict[str, Any] = {
            "version": f"frozen:{model_version}",
            "model_version": model_version,
            # Reuses calitree_judge's existing "flat, single global rubric, skip
            # embedding-based routing" fast path (CaliTreeJudgeNodeExecutor checks
            # `tree.get("architecture") == "rubric_lite"`) -- a GEPA-optimized prompt is the
            # same shape (one prompt, no children, no embedding model needed).
            "architecture": "rubric_lite",
            "gepa_architecture": "gepa",
            "training_provenance": artifact.get("training_provenance") or {},
            "selective_policy": artifact.get("selective_policy") or {},
            "roots": ["gepa:global"],
            "nodes": {
                "gepa:global": {
                    "id": "gepa:global",
                    "prompt": prompt,
                    "covered_ids": [],
                    "children": [],
                    "embedding": [],
                    "centroid": [],
                    "validated": True,
                    "state": "global",
                },
            },
            "prediction_cache": {},
        }
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
