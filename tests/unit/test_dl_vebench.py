"""VE-Bench loader + label materialization against a synthetic VE-Bench-DB tree."""

import json

import vejudge.config as config
from vejudge.database.dl_human_annotations.aggregate import aggregate_annotations
from vejudge.database.dl_human_annotations.loader import load_human_annotations
from vejudge.database.dl_vebench import VeBenchLoader, materialize_vebench_labels
from vejudge.database.dl_vebench.loader import _labels


def _build(root):
    (root / "train_samples" / "edited").mkdir(parents=True)
    (root / "train_samples" / "src").mkdir(parents=True)
    (root / "label.txt").write_text(
        "001flatten_dog.mp4|5.5|Turn the dog into a cat\n"
        "02t2vzero_ship.mp4|3.2|A pirate ship on lava\n"
        "99noedit_missing.mp4|4.0|This one has no edited video\n",
        encoding="utf-8",
    )
    for stem in ("001flatten_dog", "02t2vzero_ship"):
        (root / "train_samples" / "edited" / f"{stem}.mp4").write_text("v")
        (root / "train_samples" / "src" / f"{stem}.mp4").write_text("v")
    # 99noedit_missing has a label but no edited video -> must be dropped.


def test_list_items_skips_labels_without_an_edited_video(tmp_path, monkeypatch):
    _build(tmp_path)
    monkeypatch.setattr(config, "VEBENCH_ROOT", tmp_path)
    _labels.cache_clear()
    items = VeBenchLoader().list_items()
    assert set(items) == {"001flatten_dog::0::vebench", "02t2vzero_ship::0::vebench"}


def test_load_sample_maps_prompt_and_videos(tmp_path, monkeypatch):
    _build(tmp_path)
    monkeypatch.setattr(config, "VEBENCH_ROOT", tmp_path)
    _labels.cache_clear()
    s = VeBenchLoader().load_sample("001flatten_dog::0::vebench")
    assert s["model"] == "vebench" and s["prompt_idx"] == 0
    assert s["input"]["user_prompt"] == "Turn the dog into a cat"
    assert s["output"]["output_video_path"].endswith("edited/001flatten_dog.mp4")
    assert s["input"]["source_video_path"].endswith("src/001flatten_dog.mp4")


def test_materialized_labels_round_trip_to_edit_quality(tmp_path, monkeypatch):
    _build(tmp_path)
    monkeypatch.setattr(config, "VEBENCH_ROOT", tmp_path)
    _labels.cache_clear()
    ann_root = tmp_path / "ann"
    n = materialize_vebench_labels(out_root=ann_root)
    assert n == 2  # only the two with an edited video
    agg = aggregate_annotations(load_human_annotations(root=ann_root))
    rec = agg["001flatten_dog::0::vebench"]
    assert rec.scores["edit_quality"] == 5.5
    assert rec.model == "vebench" and rec.n_annotators == 1


def test_label_parse_handles_pipe_in_prompt(tmp_path, monkeypatch):
    (tmp_path / "label.txt").write_text("x.mp4|4.0|a | b | c\n", encoding="utf-8")
    _labels.cache_clear()
    monkeypatch.setattr(config, "VEBENCH_ROOT", tmp_path)
    assert _labels(str(tmp_path / "label.txt"))["x"] == (4.0, "a | b | c")
