"""Video resolver against a synthetic rendered-output tree."""

import vejudge.config as config
from vejudge.database.dl_peanut_eval import video_resolver


def _build_tree(root):
    base = root / "peanut-v4-multi-track-gpt-5-1-medium" / "prj-x"
    (base / "videos").mkdir(parents=True)
    (base / "notes").mkdir(parents=True)
    (base / "otio").mkdir(parents=True)
    (base / "videos" / "20260101_000000_prompt_0_final.mp4").write_text("x")
    (base / "notes" / "20260101_000000_prompt_0_notes.json").write_text("{}")
    (base / "otio" / "20260101_000000_prompt_0_final.otio").write_text("{}")
    (base / "videos" / "20260101_000000_prompt_1_final.mp4").write_text("x")
    (base / "notes" / "20260101_000000_prompt_1_notes.json").write_text("{}")


def test_resolve_outputs(tmp_path, monkeypatch):
    _build_tree(tmp_path)
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)

    outs = video_resolver.resolve_peanut_outputs("prj-x", "peanut")
    idxs = sorted(o.prompt_idx for o in outs)
    assert idxs == [0, 1]

    o0 = video_resolver.resolve_peanut_output("prj-x", 0, "peanut")
    assert o0.video_path and o0.video_path.endswith("prompt_0_final.mp4")
    assert o0.notes_path and o0.notes_path.endswith("prompt_0_notes.json")
    assert o0.otio_path and o0.otio_path.endswith("prompt_0_final.otio")


def test_missing_project_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RENDERED_ROOT", tmp_path)
    assert video_resolver.resolve_peanut_outputs("nope", "peanut") == []
