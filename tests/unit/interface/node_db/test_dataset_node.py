import pytest

from vejudge.database.dl_human_annotations.loader import HumanAnnotationRecord
from vejudge.interface.node_db import dataset_node
from vejudge.interface.node_db.dataset_node import DatasetNodeExecutor


def _raw_item(item_id, use_case="visual montage"):
    return {
        "item_id": item_id,
        "project": item_id.split("::")[0],
        "prompt_idx": int(item_id.split("::")[1]),
        "model": "peanut",
        "use_case": use_case,
        "input": {"user_prompt": "do a thing"},
        "algorithm": "peanut",
        "output": {"output_video_path": ""},
    }


def _raw_dataset():
    return {
        "prj-a::0::peanut": _raw_item("prj-a::0::peanut", "visual montage"),
        "prj-a::1::peanut": _raw_item("prj-a::1::peanut", "visual montage"),
        "prj-b::0::peanut": _raw_item("prj-b::0::peanut", "speech-driven"),
        "prj-b::1::peanut": _raw_item("prj-b::1::peanut", "speech-driven"),
    }


def _human_record(item_id, score, annotator="a1"):
    project, prompt_idx, model = item_id.split("::")
    return HumanAnnotationRecord(
        path="x",
        annotator=annotator,
        project=project,
        model=model,
        prompt_idx=int(prompt_idx),
        cell_key=f"prompt_{prompt_idx}__{model}",
        output_slot=1,
        complete=True,
        annotation={"video_addresses_prompt": str(score), "_complete": True},
    )


@pytest.fixture(autouse=True)
def _no_real_human_annotations_by_default(monkeypatch):
    # Every test below runs against a synthetic `raw_dataset` with no real data checkout on
    # disk — stub the loader so `load_human_annotations()` never hits the real filesystem;
    # tests that care about the labels join opt in via `monkeypatch.setattr` themselves.
    monkeypatch.setattr(dataset_node, "load_human_annotations", lambda **kw: [])


def test_default_sampling_passes_every_item_through(make_ctx):
    # No sampling_mode/ratio params set at all — defaults (unified, ratio=1.0) must still
    # select every item, same as the old dedicated "full" mode used to (now removed).
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert set(result.outputs["dataset"]) == set(_raw_dataset())
    assert result.outputs["labels"] == {}
    assert result.meta == {
        "n_items": 4, "n_raw_items": 4, "n_labels": 0, "n_pool_labeled": 0,
    }


def test_use_case_filter(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["speech-driven"]})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}


def test_item_id_pattern(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"item_id_pattern": r"^prj-a::"})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}


def test_sampling_ratio_unified(make_ctx):
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 0.5, "sampling_mode": "unified"},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["dataset"]) == 2


def test_sampling_ratio_alone_takes_effect_without_an_explicit_mode(make_ctx):
    # Regression guard: sampling_mode used to default to a "full" mode that silently
    # ignored ratio entirely — setting only sampling_ratio (leaving mode unset) must
    # actually narrow the selection now that "full" no longer exists.
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"sampling_ratio": 0.5})
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["dataset"]) == 2


def test_sampling_uses_use_case_already_on_each_item_not_a_re_derivation(make_ctx):
    # Confirms the Dataset Node reads `use_case` straight off each already-loaded item
    # (set upstream, e.g. by a source node) rather than trying to recompute it — stratified
    # sampling here must split evenly across the two use_cases already present.
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 0.5, "sampling_mode": "stratified"},
    )
    result = DatasetNodeExecutor().run(ctx)
    dataset = result.outputs["dataset"]
    assert len(dataset) == 2
    use_cases = {item["use_case"] for item in dataset.values()}
    assert use_cases == {"visual montage", "speech-driven"}  # one from each group


def test_missing_raw_dataset_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "error"


def test_zero_items_after_sampling_gets_a_warning(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["nonexistent"]})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["dataset"] == {}
    assert "Matched 0 items" in result.meta["warning"]


def test_labels_are_joined_by_item_id_for_exactly_the_sampled_items(make_ctx, monkeypatch):
    # Only prj-a's two items have human annotation records; prj-b has none. Sampling is
    # further restricted to prj-a only, so the label lookup must match exactly those two
    # sampled ids, never independently re-sampling the annotation side.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [
            _human_record("prj-a::0::peanut", 5),
            _human_record("prj-a::1::peanut", 3),
        ],
    )
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["visual montage"]})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}
    assert set(result.outputs["labels"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}
    assert result.outputs["labels"]["prj-a::0::peanut"].scores["video_addresses_prompt"] == 5.0
    assert result.meta["n_labels"] == 2


def test_labels_dont_include_items_outside_the_sampled_set(make_ctx, monkeypatch):
    # A human annotation record exists for prj-b, but prj-b is filtered out of the dataset
    # sample — its label must not leak into the output even though it was loaded.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [
            _human_record("prj-a::0::peanut", 5),
            _human_record("prj-b::0::peanut", 2),
        ],
    )
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["visual montage"]})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["labels"]) == {"prj-a::0::peanut"}


def test_items_without_a_matching_human_record_are_simply_absent_from_labels(make_ctx, monkeypatch):
    # No annotation exists yet for one of two sampled items — that's a legitimate partial
    # state (not an error): `labels` just has fewer entries than `dataset`.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [_human_record("prj-a::0::peanut", 5)],
    )
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["visual montage"]})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}
    assert set(result.outputs["labels"]) == {"prj-a::0::peanut"}


def test_require_labels_restricts_the_sampling_pool_to_annotated_items(make_ctx, monkeypatch):
    # Only one of the four raw items has a human record; require_labels must guarantee the
    # entire sample (regardless of ratio) is drawn only from that annotated subset — a
    # sample can never land on 0 label overlap by bad luck.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [_human_record("prj-a::0::peanut", 5)],
    )
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"require_labels": True, "sampling_ratio": 1.0},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut"}
    assert set(result.outputs["labels"]) == {"prj-a::0::peanut"}
    assert result.meta["n_pool_labeled"] == 1
    assert "warning" not in result.meta


def test_zero_label_overlap_after_filtering_has_no_warning_when_the_pool_has_no_labels(make_ctx, monkeypatch):
    # The pool itself has no labels at all after filtering (prj-a is the only labeled
    # project, and it's filtered out here) — nothing to guarantee against, so no warning.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [_human_record("prj-a::0::peanut", 5)],
    )
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()}, params={"item_id_pattern": r"^prj-b::"},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}
    assert result.outputs["labels"] == {}
    assert result.meta["n_pool_labeled"] == 0
    assert "warning" not in result.meta


def test_zero_label_overlap_on_a_sample_warns_when_the_pool_had_labels(make_ctx, monkeypatch):
    # The pool has one labeled item (prj-b::1, the last item in sorted order), but ratio
    # 0.25 only selects the evenly-spaced first item (prj-a::0) — this is exactly the
    # failure mode from the reported "0 aligned items" bug: the sample misses every labeled
    # item even though the pre-sampling pool has one, and require_labels is off, so it must
    # surface as a warning rather than silently producing an unaligned sample.
    monkeypatch.setattr(
        dataset_node,
        "load_human_annotations",
        lambda **kw: [_human_record("prj-b::1::peanut", 5)],
    )
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()}, params={"sampling_ratio": 0.25},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["dataset"]) == {"prj-a::0::peanut"}
    assert result.outputs["labels"] == {}
    assert result.meta["n_pool_labeled"] == 1
    assert "none have human labels" in result.meta["warning"]
    assert "require_labels" in result.meta["warning"]
