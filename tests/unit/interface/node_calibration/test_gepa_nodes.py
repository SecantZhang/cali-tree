import json

import pytest

from vejudge.interface.node_calibration.gepa_nodes import (
    ARTIFACT_ROOT,
    GepaFrozenNodeExecutor,
)


def test_gepa_frozen_loads_the_committed_artifact(make_ctx):
    result = GepaFrozenNodeExecutor().run(make_ctx(
        params={"model_version": "gepa_v1_imagenhub"},
        inputs={},
    ))

    assert result.status == "done"
    tree = result.outputs["prompt_tree"]
    # Reuses the existing "flat, single global rubric" fast path in calitree_judge.
    assert tree["architecture"] == "rubric_lite"
    assert tree["gepa_architecture"] == "gepa"
    assert tree["roots"] == ["gepa:global"]
    assert tree["nodes"]["gepa:global"]["children"] == []
    assert "ordinal_thresholds" not in tree  # plain {"label","rationale"} schema, not scored
    assert tree["prediction_cache"] == {}
    assert len(tree["nodes"]["gepa:global"]["prompt"]) > 0
    assert result.meta["model_calls"] == 0
    assert result.meta["architecture"] == "gepa"


def test_gepa_frozen_rejects_unknown_model_version(make_ctx):
    result = GepaFrozenNodeExecutor().run(make_ctx(
        params={"model_version": "not_a_real_version"},
        inputs={},
    ))

    assert result.status == "error"
    assert "Unknown frozen GEPA model" in result.error


def test_gepa_frozen_errors_cleanly_on_missing_artifact(make_ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.gepa_nodes.ARTIFACT_ROOT", tmp_path
    )
    result = GepaFrozenNodeExecutor().run(make_ctx(
        params={"model_version": "gepa_v1_imagenhub"},
        inputs={},
    ))

    assert result.status == "error"
    assert "Invalid frozen GEPA artifact" in result.error


def test_gepa_frozen_errors_cleanly_on_empty_prompt(make_ctx, monkeypatch, tmp_path):
    (tmp_path / "gepa_v1_imagenhub.json").write_text(
        json.dumps({"prompt": "   "}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "vejudge.interface.node_calibration.gepa_nodes.ARTIFACT_ROOT", tmp_path
    )
    result = GepaFrozenNodeExecutor().run(make_ctx(
        params={"model_version": "gepa_v1_imagenhub"},
        inputs={},
    ))

    assert result.status == "error"
    assert "Invalid frozen GEPA artifact" in result.error


def test_gepa_artifact_file_exists_on_disk():
    assert (ARTIFACT_ROOT / "gepa_v1_imagenhub.json").is_file()
