import json

import pytest

import vejudge.config as config
from vejudge.database.dl_peanut_eval.loader import _use_cases
from vejudge.interface.node_db.dataset_node import DatasetNodeExecutor

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


def _humaneval_file(root, *, annotator, project, prompt_idx, model, scores):
    path = root / project / f"{annotator}_prompt{prompt_idx}_{project}_{model}_humaneval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    ann = dict(scores)
    ann["_complete"] = True
    path.write_text(
        json.dumps(
            {
                "annotator": annotator,
                "project": project,
                "model": model,
                "prompt_idx": prompt_idx,
                "cell_key": f"prompt_{prompt_idx}__{model}",
                "output_slot": 1,
                "annotation": ann,
            }
        )
    )


@pytest.fixture
def human_annotations_fixture(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    annotations_root = tmp_path / "human_annotations"
    use_cases_path = data_root / "use_cases_config.json"
    data_root.mkdir(parents=True, exist_ok=True)
    use_cases_path.write_text(
        json.dumps({p: {"use_case": uc} for p, (uc, _) in PROJECTS.items()})
    )
    for project, (_, n_prompts) in PROJECTS.items():
        for i in range(n_prompts):
            _humaneval_file(
                annotations_root, annotator="ann1", project=project, prompt_idx=i,
                model="peanut", scores={"video_addresses_prompt": "4"},
            )
    monkeypatch.setattr(config, "DATA_ROOT", data_root)
    monkeypatch.setattr(config, "HUMAN_ANNOTATIONS_ROOT", annotations_root)
    monkeypatch.setattr(config, "USE_CASES_CONFIG", use_cases_path)
    _use_cases.cache_clear()
    yield
    _use_cases.cache_clear()


def test_peanut_eval_loads_all_items(peanut_fixture, make_ctx):
    ctx = make_ctx(params={"loader": "peanut_eval", "model": "peanut"})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    dataset = result.outputs["dataset"]
    assert set(dataset) == {
        "prj-a::0::peanut", "prj-a::1::peanut", "prj-b::0::peanut", "prj-b::1::peanut",
    }
    assert dataset["prj-a::0::peanut"]["use_case"] == "visual montage"
    assert "labels" not in result.outputs


def test_peanut_eval_use_case_filter(peanut_fixture, make_ctx):
    ctx = make_ctx(
        params={"loader": "peanut_eval", "model": "peanut", "use_case_filter": ["speech-driven"]}
    )
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}


def test_peanut_eval_item_id_pattern(peanut_fixture, make_ctx):
    ctx = make_ctx(params={"loader": "peanut_eval", "item_id_pattern": r"^prj-a::"})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}


def test_peanut_eval_sampling_ratio_unified(peanut_fixture, make_ctx):
    ctx = make_ctx(
        params={"loader": "peanut_eval", "sampling_ratio": 0.5, "sampling_mode": "unified"}
    )
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["dataset"]) == 2


def test_unknown_loader_is_a_node_error(peanut_fixture, make_ctx):
    ctx = make_ctx(params={"loader": "nope"})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "error"
    assert "nope" in result.error


def test_peanut_eval_skips_a_bad_item_instead_of_failing_the_whole_node(
    peanut_fixture, make_ctx, tmp_path
):
    # A rendered notes file exists for prompt_idx=2, but user_query.json only defines
    # 1 prompt (indices out of range) — a real data inconsistency found via prj-duygu-interview
    # in production data. One bad item must not drop the rest of a project-less (all-projects)
    # Dataset Node's output.
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

    ctx = make_ctx(params={"loader": "peanut_eval"})
    result = DatasetNodeExecutor().run(ctx)

    assert result.status == "done"
    dataset = result.outputs["dataset"]
    assert "prj-broken::0::peanut" in dataset  # the good item still loads
    assert "prj-broken::2::peanut" not in dataset  # the bad one is skipped, not fatal
    assert {"prj-a::0::peanut", "prj-a::1::peanut", "prj-b::0::peanut", "prj-b::1::peanut"} <= set(
        dataset
    )  # unrelated projects are unaffected
    assert result.meta["skipped_items"] == ["prj-broken::2::peanut"]


def test_human_annotations_loads_labels(human_annotations_fixture, make_ctx):
    ctx = make_ctx(params={"loader": "human_annotations", "model": "peanut"})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    labels = result.outputs["labels"]
    assert set(labels) == {
        "prj-a::0::peanut", "prj-a::1::peanut", "prj-b::0::peanut", "prj-b::1::peanut",
    }
    assert labels["prj-a::0::peanut"].scores["video_addresses_prompt"] == 4.0
    assert labels["prj-a::0::peanut"].use_case == "visual montage"
    assert "dataset" not in result.outputs
    assert "warning" not in result.meta


def test_peanut_eval_zero_items_gets_a_warning(peanut_fixture, make_ctx):
    # A filter that matches nothing — the exact shape of the real bug this guards against:
    # a misconfigured/misresolved data root (or an overly narrow filter) silently produces
    # an empty dataset with status "done" and no other signal that anything is wrong.
    ctx = make_ctx(params={"loader": "peanut_eval", "use_case_filter": ["nonexistent"]})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["dataset"] == {}
    assert "Matched 0 items" in result.meta["warning"]


def test_human_annotations_zero_items_gets_a_warning(human_annotations_fixture, make_ctx):
    ctx = make_ctx(params={"loader": "human_annotations", "model": "nonexistent-model"})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["labels"] == {}
    assert "Matched 0 items" in result.meta["warning"]
