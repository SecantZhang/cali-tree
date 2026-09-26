"""Load a frozen GEPA prompt as a CaliTree-compatible flat tree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path(__file__).resolve().parent / "artifacts"
GEPA_MODEL_VERSIONS = ("gepa_v1_imagenhub",)


def load_frozen_prompt_tree(
    model_version: str, *, artifact_root: Path = ARTIFACT_ROOT
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the prompt tree and its source artifact for a known GEPA model."""
    if model_version not in GEPA_MODEL_VERSIONS:
        raise ValueError(f"Unknown frozen GEPA model {model_version!r}")

    artifact_path = artifact_root / f"{model_version}.json"
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        prompt = str(artifact["prompt"])
        if not prompt.strip():
            raise ValueError("artifact prompt is empty")
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid frozen GEPA artifact {model_version!r}: {exc}") from exc

    tree: dict[str, Any] = {
        "version": f"frozen:{model_version}",
        "model_version": model_version,
        # A flat tree uses CaliTreeJudgeNodeExecutor's global prompt path.
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
    return tree, artifact
