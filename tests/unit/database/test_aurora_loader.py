import json

import pytest

from vejudge.database.dl_aurora import (
    AURORA_MODELS,
    AuroraBenchLoader,
    build_split_manifest,
    score_to_label,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, (0, "no")),
        (0.49, (0, "no")),
        (0.5, (1, "partial")),
        (1.49, (1, "partial")),
        (1.5, (2, "yes")),
        (2.0, (2, "yes")),
    ],
)
def test_score_to_label_uses_half_point_cutoffs(score, expected):
    assert score_to_label(score) == expected


def test_score_to_label_rejects_out_of_range_values():
    with pytest.raises(ValueError, match=r"\[0, 2\]"):
        score_to_label(2.01)


@pytest.mark.parametrize("seed", [42, 43, 44])
def test_grouped_80_320_split_has_no_task_leakage(seed):
    uids = [f"aurora-task-{index:03d}" for index in range(400)]
    manifest = build_split_manifest(uids, seed=seed)
    assert len(manifest["train"]) == 80
    assert len(manifest["test"]) == 320
    assert set(manifest["train"]).isdisjoint(manifest["test"])
    assert manifest == build_split_manifest(reversed(uids), seed=seed)


def _materialize_fixture(root):
    model = AURORA_MODELS[0]
    task_uid = "aurora-task-fixture"
    item_id = f"{task_uid}::{model}"
    source = "human_ratings/magicbrush/case/input.png"
    edited = f"human_ratings/magicbrush/case/{model}.png"
    (root / source).parent.mkdir(parents=True)
    (root / source).write_bytes(b"source")
    (root / edited).write_bytes(b"edited")
    row = {
        "source_index": 0,
        "item_id": item_id,
        "task_uid": task_uid,
        "instruction": "Put a cat on the seat.",
        "model": model,
        "task": "magicbrush",
        "human_score": 1.5833333333333333,
        "target_score": 2,
        "target_label": "yes",
        "source_path": source,
        "edited_path": edited,
        "prompt_index": 0,
    }
    (root / "metadata.jsonl").write_text(json.dumps(row) + "\n")
    (root / "splits").mkdir()
    (root / "splits" / "seed_42.json").write_text(
        json.dumps({"seed": 42, "train": [task_uid], "test": []})
    )
    return item_id, model


def test_loader_exposes_continuous_and_ordinal_targets(tmp_path):
    item_id, model = _materialize_fixture(tmp_path)
    loader = AuroraBenchLoader(
        root=tmp_path,
        repeat=1,
        models=[model],
        tasks=["magicbrush"],
    )
    samples, labels = loader.load_all()
    sample, label = samples[item_id], labels[item_id]
    assert sample["split"] == "train"
    assert sample["input"]["source_image_path"].endswith("input.png")
    assert sample["output"]["edited_image_path"].endswith(f"{model}.png")
    assert label["human_score"] == pytest.approx(1.5833333333333333)
    assert label["normalized_sc"] == pytest.approx(0.7916666666666666)
    assert label["target_score"] == 2
    assert label["target_label"] == "yes"
    assert label["ratings"] == []
    assert label["raw_ratings_available"] is False


def test_loader_reports_incomplete_setup(tmp_path):
    with pytest.raises(FileNotFoundError, match="setup_aurora_bench"):
        AuroraBenchLoader(root=tmp_path).list_items()


def test_loader_reports_missing_asset(tmp_path):
    item_id, model = _materialize_fixture(tmp_path)
    loader = AuroraBenchLoader(
        root=tmp_path,
        models=[model],
        tasks=["magicbrush"],
    )
    (tmp_path / "human_ratings/magicbrush/case/input.png").unlink()
    with pytest.raises(FileNotFoundError, match="setup is incomplete"):
        loader.list_items()
    with pytest.raises(FileNotFoundError, match="Missing AURORA-Bench image"):
        loader.load_sample(item_id)
