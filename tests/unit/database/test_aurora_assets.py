import copy
import hashlib
import json

from PIL import Image
import pytest

from critical.database.dl_aurora import AuroraBenchLoader
from critical.database.dl_aurora.assets import materialize_output_panel


def fixture(root, *, task="something", model="instruct-pix2pix-00-22000"):
    source = Image.new("RGB", (48, 32), (10, 80, 150))
    # An asymmetric output makes an incorrect panel/crop observable.
    output = Image.new("RGB", source.size, (200, 30, 20))
    output.putpixel((0, 0), (1, 2, 3))
    composite = Image.new("RGB", (96, 32))
    composite.paste(source, (0, 0))
    composite.paste(output, (48, 0))
    source.save(root / "source.png")
    composite.save(root / "raw.png")
    return {"task": task, "model": model, "source_path": "source.png",
            "edited_path": "raw.png", "human_score": 1.0}, output


def test_output_panel_is_lossless_provenanced_and_does_not_mutate_inputs(tmp_path):
    row, output = fixture(tmp_path)
    before = copy.deepcopy(row)
    raw = (tmp_path / "raw.png").read_bytes()
    normalized = materialize_output_panel(tmp_path, row)
    assert row == before
    assert (tmp_path / "raw.png").read_bytes() == raw
    assert normalized["human_score"] == row["human_score"]
    assert normalized["raw_edited_path"] == "raw.png"
    assert normalized["image_normalization"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert normalized["image_normalization"]["crop_box"] == [48, 0, 96, 32]
    with Image.open(tmp_path / normalized["edited_path"]) as actual:
        assert actual.size == output.size and actual.tobytes() == output.tobytes()
    assert materialize_output_panel(tmp_path, normalized) == normalized


@pytest.mark.parametrize("task,model", [("ag", "instruct-pix2pix-00-22000"), ("something", "mgie")])
def test_unrelated_wide_images_are_not_cropped(tmp_path, task, model):
    row, _ = fixture(tmp_path, task=task, model=model)
    assert materialize_output_panel(tmp_path, row) == row
    assert not (tmp_path / "output_panels").exists()


def test_wrong_source_preview_fails_before_materialization(tmp_path):
    row, _ = fixture(tmp_path)
    Image.new("RGB", (48, 32), "white").save(tmp_path / "source.png")
    with pytest.raises(ValueError, match="left panel does not match"):
        materialize_output_panel(tmp_path, row)
    assert not (tmp_path / "output_panels").exists()


def test_changed_derived_pixels_are_not_silently_reused(tmp_path):
    row, _ = fixture(tmp_path)
    normalized = materialize_output_panel(tmp_path, row)
    Image.new("RGB", (48, 32), "black").save(tmp_path / normalized["edited_path"])
    with pytest.raises(ValueError, match="differs from raw crop"):
        materialize_output_panel(tmp_path, row)


def test_panel_selection_does_not_depend_on_target_labels(tmp_path):
    row, _ = fixture(tmp_path)
    paths = [materialize_output_panel(tmp_path, {**row, "human_score": score})["edited_path"]
             for score in (0, 1, 2)]
    assert len(set(paths)) == 1


def test_loader_rejects_legacy_composite_and_exposes_normalized_output(tmp_path):
    row, _ = fixture(tmp_path)
    row.update(item_id="sample", task_uid="task", prompt_index=0, instruction="Add an object")
    (tmp_path / "splits").mkdir()
    (tmp_path / "splits/seed_42.json").write_text(json.dumps({"train": ["task"], "test": []}))
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="comparison composite"):
        AuroraBenchLoader(root=tmp_path).list_items()
    normalized = materialize_output_panel(tmp_path, row)
    metadata.write_text(json.dumps(normalized) + "\n")
    sample = AuroraBenchLoader(root=tmp_path).load_sample("sample")
    assert sample["output"]["edited_image_path"] == str(tmp_path / normalized["edited_path"])
