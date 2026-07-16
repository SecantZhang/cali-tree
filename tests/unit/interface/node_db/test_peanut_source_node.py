import json

import pytest

import vejudge.config as config
from vejudge.database.dl_peanut_eval.loader import _use_cases
from vejudge.interface.node_db.peanut_source_node import PeanutSourceNodeExecutor

PROJECTS = {
    "prj-a": ("visual montage", 2),  # (use_case, n_prompts)
    "prj-b": ("speech-driven", 2),
}


def _build_peanut_tree(root, data_root):
    for project, (_, n_prompts) in PROJECTS.items():
        (data_root / project).mkdir(parents=True, exist_ok=True)
        (data_root / project / "user_query.json").write_text(
            json.dumps({"prompts": [{"user_request": f"req {i}"} for i in range(n_prompts)]})
        )
        base = root / "peanut-v4-multi-track-gpt-5-1-medium" / project
        (base / "videos").mkdir(parents=True)
        (base / "notes").mkdir(parents=True)
        for i in range(n_prompts):
            (base / "videos" / f"20260101_000000_prompt_{i}_final.mp4").write_text("x")
            (base / "notes" / f"20260101_000000_prompt_{i}_notes.json").write_text("{}")

    use_cases_path = data_root / "use_cases_config.json"
    use_cases_path.write_text(
        json.dumps({p: {"use_case": uc} for p, (uc, _) in PROJECTS.items()})
    )
    return use_cases_path


@pytest.fixture
def peanut_fixture(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    rendered_root = tmp_path / "rendered"
    use_cases_path = _build_peanut_tree(rendered_root, data_root)
    monkeypatch.setattr(config, "DATA_ROOT", data_root)
    monkeypatch.setattr(config, "RENDERED_ROOT", rendered_root)
    monkeypatch.setattr(config, "USE_CASES_CONFIG", use_cases_path)
    _use_cases.cache_clear()
    yield
    _use_cases.cache_clear()


def test_loads_all_items_with_no_sampling(peanut_fixture, make_ctx):
    ctx = make_ctx(params={"model": "peanut"})
    result = PeanutSourceNodeExecutor().run(ctx)
    assert result.status == "done"
    raw = result.outputs["raw_dataset"]
    assert set(raw) == {
        "prj-a::0::peanut", "prj-a::1::peanut", "prj-b::0::peanut", "prj-b::1::peanut",
    }
    assert raw["prj-a::0::peanut"]["use_case"] == "visual montage"


def test_projects_filter(peanut_fixture, make_ctx):
    ctx = make_ctx(params={"model": "peanut", "projects": ["prj-b"]})
    result = PeanutSourceNodeExecutor().run(ctx)
    assert set(result.outputs["raw_dataset"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}


def test_skips_a_bad_item_instead_of_failing_the_whole_node(peanut_fixture, make_ctx):
    # A rendered notes file exists for prompt_idx=2, but user_query.json only defines 1
    # prompt (indices out of range) — a real data inconsistency found via
    # prj-duygu-interview in production data. One bad item must not drop the rest.
    data_root = config.DATA_ROOT
    rendered_root = config.RENDERED_ROOT
    project = "prj-broken"
    (data_root / project).mkdir(parents=True)
    (data_root / project / "user_query.json").write_text(
        json.dumps({"prompts": [{"user_request": "only one prompt"}]})
    )
    base = rendered_root / "peanut-v4-multi-track-gpt-5-1-medium" / project
    (base / "videos").mkdir(parents=True)
    (base / "notes").mkdir(parents=True)
    for i in (0, 2):  # index 2 has a render but no matching prompt entry
        (base / "videos" / f"20260101_000000_prompt_{i}_final.mp4").write_text("x")
        (base / "notes" / f"20260101_000000_prompt_{i}_notes.json").write_text("{}")
    use_cases = json.loads(config.USE_CASES_CONFIG.read_text())
    use_cases[project] = {"use_case": "unknown"}
    config.USE_CASES_CONFIG.write_text(json.dumps(use_cases))

    ctx = make_ctx(params={})
    result = PeanutSourceNodeExecutor().run(ctx)

    assert result.status == "done"
    raw = result.outputs["raw_dataset"]
    assert "prj-broken::0::peanut" in raw  # the good item still loads
    assert "prj-broken::2::peanut" not in raw  # the bad one is skipped, not fatal
    assert {"prj-a::0::peanut", "prj-a::1::peanut", "prj-b::0::peanut", "prj-b::1::peanut"} <= set(raw)
    assert result.meta["skipped_items"] == ["prj-broken::2::peanut"]


def test_zero_items_gets_a_warning(peanut_fixture, make_ctx):
    # A misresolved data root (or a project filter matching nothing) silently produces an
    # empty raw_dataset with status "done" and no other signal that anything is wrong.
    ctx = make_ctx(params={"projects": ["nonexistent-project"]})
    result = PeanutSourceNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["raw_dataset"] == {}
    assert "Matched 0 items" in result.meta["warning"]


def test_models_list_merges_across_models(peanut_fixture, make_ctx):
    # Add a coconut render tree (ordinal 001/002 -> prompt 0/1) for prj-a, reusing the same
    # source project. `models` should load BOTH models and merge, keyed by model-namespaced
    # item ids (no collision with the peanut items).
    rendered_root = config.RENDERED_ROOT
    for run, _idx in (("001", 0), ("002", 1)):
        d = rendered_root / "coconut" / "prj-a" / run
        d.mkdir(parents=True)
        (d / "render.mp4").write_text("v")
        (d / "timeline.otio").write_text('{"tracks": {"children": []}}')

    ctx = make_ctx(params={"models": ["peanut", "coconut"]})
    raw = PeanutSourceNodeExecutor().run(ctx).outputs["raw_dataset"]
    # Peanut items still present…
    assert {"prj-a::0::peanut", "prj-b::0::peanut"} <= set(raw)
    # …plus the coconut renders of prj-a (ordinal mapped).
    assert {"prj-a::0::coconut", "prj-a::1::coconut"} <= set(raw)
    assert raw["prj-a::0::coconut"]["output"]["output_video_path"].endswith("001/render.mp4")
