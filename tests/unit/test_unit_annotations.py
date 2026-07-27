import json

import pytest

from vejudge.database.unit_annotations import load_unit_annotations


def test_unit_annotation_loader_validates_and_normalizes(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps({
        "item_id": "i", "unit_id": "u", "rubric_id": "transition_smoothness",
        "rating": 3, "comment": "abrupt",
    }) + "\n")
    records = load_unit_annotations(path)
    assert records[0]["rating"] == 3.0
    assert records[0]["comment"] == "abrupt"


def test_unit_annotation_loader_rejects_out_of_range_rating(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps({
        "item_id": "i", "unit_id": "u", "rubric_id": "transition_smoothness",
        "rating": 8,
    }) + "\n")
    with pytest.raises(ValueError, match="rating"):
        load_unit_annotations(path)
