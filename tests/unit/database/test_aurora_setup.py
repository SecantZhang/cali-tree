import hashlib
import json
import zipfile

import pytest

from run.setup_aurora_bench import (
    AURORA_MODELS,
    EXPECTED_ITEMS,
    EXPECTED_TASKS,
    _safe_members,
    build_manifest,
    parse_ratings,
    task_uid,
    validate_assets,
    verify_sha256,
)


def test_task_uid_is_stable_and_depends_on_prompt():
    first = task_uid("human_ratings/ag/1/input.png", "open the door")
    assert first == task_uid("human_ratings/ag/1/input.png", "open the door")
    assert first != task_uid("human_ratings/ag/1/input.png", "close the door")


def test_verify_sha256_accepts_match_and_rejects_mutation(tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b"ratings")
    expected = hashlib.sha256(b"ratings").hexdigest()
    verify_sha256(path, expected)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_sha256(path, "0" * 64)


def test_safe_members_rejects_archive_traversal(tmp_path):
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.png", b"bad")
    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(ValueError, match="Unsafe path"):
            _safe_members(archive)


def _write_full_ratings(path):
    rows = []
    for prompt_index in range(EXPECTED_TASKS):
        task = ("ag", "clevr", "emu", "epic", "kubric", "magicbrush", "something", "whatsup")[
            prompt_index % 8
        ]
        for model_index, model in enumerate(AURORA_MODELS):
            rows.append({
                "input": f"human_ratings/{task}/{prompt_index}/input.png",
                "gen": f"human_ratings/{task}/{prompt_index}/{model_index}.png",
                "prompt": f"instruction {prompt_index}",
                "model": model,
                "score": (prompt_index + model_index) % 3,
                "task": task,
            })
    assert len(rows) == EXPECTED_ITEMS
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_parse_ratings_preserves_continuous_score_and_builds_complete_groups(tmp_path):
    ratings = tmp_path / "ratings.json"
    _write_full_ratings(ratings)
    rows = parse_ratings(ratings)
    assert len(rows) == 2_000
    assert len({row["task_uid"] for row in rows}) == 400
    assert len({row["prompt_index"] for row in rows}) == 400
    assert {row["target_label"] for row in rows} == {"no", "partial", "yes"}


def test_manifest_records_score_semantics_and_hashed_assets(tmp_path):
    ratings = tmp_path / "source" / "human_ratings.json"
    ratings.parent.mkdir(parents=True)
    _write_full_ratings(ratings)
    rows = parse_ratings(ratings)
    for row in rows:
        for field in ("source_path", "edited_path"):
            path = tmp_path / row[field]
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(field.encode())
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text("{}\n")
    (tmp_path / "splits").mkdir()
    for seed in (42, 43, 44):
        (tmp_path / "splits" / f"seed_{seed}.json").write_text("{}\n")
    assets = validate_assets(tmp_path, rows)
    manifest = build_manifest(tmp_path, rows, assets)
    assert manifest["items"] == 2_000
    assert manifest["tasks"] == 400
    assert manifest["human_score_scale"]["semantics"]["1"] == "partial"
    assert sum(manifest["label_counts"].values()) == 2_000
