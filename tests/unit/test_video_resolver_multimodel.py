"""Multi-model layout dispatch in the video resolver (coconut ordinal, grapenut indexed).
The peanut path is covered by test_video_resolver.py and must be unaffected."""

import logging

import vejudge.config as config
from vejudge.database.dl_peanut_eval import video_resolver as vr


def _coconut(root, runs=("001", "002", "003")):
    for run in runs:
        d = root / "coconut" / "prj-c" / run
        d.mkdir(parents=True)
        (d / "render.mp4").write_text("v")
        (d / "timeline.otio").write_text("{}")
        (d / "plan.md").write_text("plan")


def _grapenut(root, idxs=(0, 1, 2)):
    base = root / "grapenut" / "prj-g"
    (base / "videos").mkdir(parents=True)
    (base / "otio").mkdir(parents=True)
    for i in idxs:
        (base / "videos" / f"{i}_video.mp4").write_text("v")
        (base / "otio" / f"{i}_timeline.otio").write_text("{}")


def test_coconut_ordinal_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    _coconut(tmp_path)
    outs = vr.resolve_peanut_outputs("prj-c", "coconut")
    assert sorted(o.prompt_idx for o in outs) == [0, 1, 2]  # 001->0, 002->1, 003->2
    o0 = vr.resolve_peanut_output("prj-c", 0, "coconut")
    assert o0.video_path.endswith("001/render.mp4")
    assert o0.otio_path.endswith("001/timeline.otio")
    assert o0.plan_path.endswith("001/plan.md")
    assert o0.notes_path is None


def test_coconut_skips_runs_without_a_render(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    _coconut(tmp_path, runs=("001", "002"))
    # A 003 dir with no render.mp4 must not be discovered.
    (tmp_path / "coconut" / "prj-c" / "003").mkdir()
    assert sorted(o.prompt_idx for o in vr.resolve_peanut_outputs("prj-c", "coconut")) == [0, 1]


def test_coconut_warns_on_non_contiguous_runs(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    _coconut(tmp_path, runs=("001", "003"))  # gap at 002 -> ordinal assumption suspect
    with caplog.at_level(logging.WARNING):
        outs = vr.resolve_peanut_outputs("prj-c", "coconut")
    assert sorted(o.prompt_idx for o in outs) == [0, 2]  # still deterministic NNN-1
    assert any("not contiguous" in r.message for r in caplog.records)


def test_grapenut_indexed_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    _grapenut(tmp_path)
    assert sorted(o.prompt_idx for o in vr.resolve_peanut_outputs("prj-g", "grapenut")) == [0, 1, 2]
    o1 = vr.resolve_peanut_output("prj-g", 1, "grapenut")
    assert o1.video_path.endswith("videos/1_video.mp4")
    assert o1.otio_path.endswith("otio/1_timeline.otio")


def test_missing_render_dir_is_empty_not_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    assert vr.resolve_peanut_outputs("prj-absent", "coconut") == []
    assert vr.resolve_peanut_outputs("prj-absent", "grapenut") == []
    # A grapenut item whose video file is missing resolves to video_path None.
    assert vr.resolve_peanut_output("prj-absent", 0, "grapenut").video_path is None
