import csv
import json

import pytest

from vejudge.database.dl_imagenhub.loader import (
    EDITORS,
    ImagenHubLoader,
    _parse_rating,
    build_split_manifest,
    median_sc_label,
)


def _write_fixture(root, *, uid="sample_100_1"):
    (root / "ratings").mkdir(parents=True)
    header = ["uid", *EDITORS]
    for rater, score in enumerate((0, 0.5, 1), start=1):
        with (root / "ratings" / f"Text-Guided_IE_rater{rater}.tsv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t")
            writer.writeheader()
            writer.writerow({"uid": f"{uid}.jpg", **{editor: f"[{score}, 1]" for editor in EDITORS}})
    (root / "metadata.jsonl").write_text(
        json.dumps({"uid": uid, "turn_index": 1, "instruction": "make it blue"}) + "\n",
        encoding="utf-8",
    )
    (root / "splits").mkdir()
    (root / "splits" / "seed_42.json").write_text(
        json.dumps({"seed": 42, "train": [uid], "test": []}), encoding="utf-8"
    )
    (root / "inputs").mkdir()
    (root / "inputs" / f"{uid}.jpg").write_bytes(b"source")
    for editor in EDITORS:
        (root / "outputs" / editor).mkdir(parents=True)
        (root / "outputs" / editor / f"{uid}.jpg").write_bytes(b"edited")


def test_rating_parser_and_median_semantic_consistency_target():
    assert _parse_rating("[0.5, 1]") == (0.5, 1.0)
    assert median_sc_label([(0, 1), (0.5, 0), (1, 1)]) == (0.5, "partial")
    assert median_sc_label([(1, 0), (1, 0.5), (0.5, 1)]) == (1.0, "yes")
    with pytest.raises(ValueError, match="Rating values"):
        _parse_rating("[2, 1]")


@pytest.mark.parametrize("seed", [42, 43, 44])
def test_exact_grouped_29_150_split_has_no_task_leakage(seed):
    manifest = build_split_manifest((f"sample_{index}_1" for index in range(179)), seed=seed)
    assert len(manifest["train"]) == 29
    assert len(manifest["test"]) == 150
    assert set(manifest["train"]).isdisjoint(manifest["test"])
    assert len(manifest["train"]) * len(EDITORS) == 261
    assert len(manifest["test"]) * len(EDITORS) == 1350
    assert manifest == build_split_manifest(
        (f"sample_{index}_1" for index in reversed(range(179))), seed=seed
    )


def test_loader_emits_nine_image_pairs_and_three_ratings(tmp_path):
    _write_fixture(tmp_path)
    samples, labels = ImagenHubLoader(root=tmp_path, repeat=1, editors=EDITORS).load_all()
    assert len(samples) == len(labels) == 9
    item_id = "sample_100_1::SDEdit"
    assert samples[item_id]["split"] == "train"
    assert samples[item_id]["input"]["source_image_path"].endswith("sample_100_1.jpg")
    assert samples[item_id]["output"]["edited_image_path"].endswith(
        "outputs/SDEdit/sample_100_1.jpg"
    )
    assert labels[item_id]["target_label"] == "partial"
    assert labels[item_id]["median_sc"] == 0.5
    assert len(labels[item_id]["ratings"]) == 3


def test_loader_reports_missing_setup(tmp_path):
    with pytest.raises(FileNotFoundError, match="setup_imagenhub"):
        ImagenHubLoader(root=tmp_path).list_items()


def test_loader_reports_missing_editor_asset(tmp_path):
    _write_fixture(tmp_path)
    missing = tmp_path / "outputs" / "SDEdit" / "sample_100_1.jpg"
    missing.unlink()
    loader = ImagenHubLoader(root=tmp_path, editors=["SDEdit"])
    with pytest.raises(FileNotFoundError, match="setup is incomplete"):
        loader.list_items()
    with pytest.raises(FileNotFoundError, match="Missing ImagenHub image"):
        loader.load_sample("sample_100_1::SDEdit")
