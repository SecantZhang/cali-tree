import hashlib
import json

import pytest

from run.setup_editinspector import (
    assign_evaluation_partitions,
    build_manifest,
    select_rows,
)
from vejudge.database.dl_editinspector import (
    EDITINSPECTOR_REVISION,
    EditInspectorLoader,
    accuracy_level_label,
)


@pytest.mark.parametrize(
    ("level", "label"),
    [(0, "no"), (1, "partial"), (2, "yes"), (3, "yes")],
)
def test_accuracy_level_label_matches_official_annotation_scale(level, label):
    assert accuracy_level_label(level) == label


def test_accuracy_level_label_rejects_unknown_level():
    with pytest.raises(ValueError, match="0..3"):
        accuracy_level_label(4)


def test_stratified_selection_is_exact_and_nested():
    rows = [
        {
            "item_id": f"{label}-{index:03d}",
            "source_index": offset + index,
            "target_label": label,
        }
        for label, count, offset in (
            ("no", 10, 0),
            ("partial", 20, 100),
            ("yes", 70, 200),
        )
        for index in range(count)
    ]
    tenth = select_rows(rows, ratio=0.1, seed=44)
    half = select_rows(rows, ratio=0.5, seed=44)

    assert {
        label: sum(row["target_label"] == label for row in tenth)
        for label in ("no", "partial", "yes")
    } == {"no": 1, "partial": 2, "yes": 7}
    assert {row["item_id"] for row in tenth} <= {
        row["item_id"] for row in half
    }
    assign_evaluation_partitions(rows, half, seed=44)
    assert sum(
        row["evaluation_partition"] == "development"
        for row in half
    ) == 10
    assert sum(
        row["evaluation_partition"] == "confirmation"
        for row in half
    ) == 40


def _materialize_fixture(root):
    (root / "images" / "source").mkdir(parents=True)
    (root / "images" / "edited").mkdir(parents=True)
    (root / "images" / "source" / "0000.png").write_bytes(b"source")
    (root / "images" / "edited" / "0000.png").write_bytes(b"edited")
    row = {
        "source_index": 0,
        "item_id": "editinspector::0000",
        "benchmark_id": "external-task",
        "instruction": "Add a squirrel.",
        "action": "Add",
        "accuracy_level": 1,
        "target_label": "partial",
        "rater_accuracy_levels": [0, 1, 2],
        "annotators": [11, 12, 13],
        "source_url": "https://example.invalid/source.png",
        "edited_url": "https://example.invalid/edited.png",
        "source_path": "images/source/0000.png",
        "edited_path": "images/edited/0000.png",
        "evaluation_partition": "development",
    }
    (root / "metadata.jsonl").write_text(json.dumps(row) + "\n")
    return row


def test_loader_exposes_external_image_pair_and_three_rater_label(tmp_path):
    _materialize_fixture(tmp_path)
    loader = EditInspectorLoader(root=tmp_path)

    samples, labels = loader.load_all()

    sample = samples["editinspector::0000"]
    label = labels["editinspector::0000"]
    assert sample["split"] == "test"
    assert sample["external_partition"] == "development"
    assert sample["task_uid"] == "external-task"
    assert sample["input"]["instruction"] == "Add a squirrel."
    assert sample["input"]["source_image_path"].endswith("0000.png")
    assert label["target_label"] == "partial"
    assert [rating["sc"] for rating in label["ratings"]] == [0.0, 0.5, 1.0]
    assert label["n_annotators"] == 3


def test_loader_reports_incomplete_setup(tmp_path):
    _materialize_fixture(tmp_path)
    (tmp_path / "images" / "edited" / "0000.png").unlink()

    with pytest.raises(FileNotFoundError, match="setup is incomplete"):
        EditInspectorLoader(root=tmp_path).list_items()


def test_manifest_pins_revision_and_hashes_selected_assets(tmp_path):
    row = _materialize_fixture(tmp_path)
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "editinspector_benchmark.csv").write_bytes(b"csv")
    manifest = build_manifest(tmp_path, [row], ratio=0.1, seed=44)

    assert manifest["revision"] == EDITINSPECTOR_REVISION
    assert manifest["label_mapping"]["1"] == "partial"
    assert manifest["label_counts"] == {"no": 0, "partial": 1, "yes": 0}
    assert manifest["partition_counts"] == {
        "development": 1,
        "confirmation": 0,
    }
    assert manifest["files"]["images/source/0000.png"]["sha256"] == hashlib.sha256(
        b"source"
    ).hexdigest()
