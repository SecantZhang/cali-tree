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
    assert set(result.outputs["samples"]) == set(_raw_dataset())
    assert result.outputs["labels"] == {}
    assert result.meta == {
        "n_items": 4, "n_raw_items": 4, "n_labels": 0, "n_pool_labeled": 0,
    }


def test_fan_in_merges_multiple_source_pools(make_ctx):
    # The executor delivers a fan-in socket as a list of raw_dataset dicts (one per wired
    # source); the Dataset node merges them. Item ids are model-namespaced, so a peanut and
    # a coconut source contribute distinct items with no collision.
    peanut = _raw_dataset()
    coconut = {
        "prj-a::0::coconut": _raw_item("prj-a::0::coconut"),
        "prj-c::0::coconut": _raw_item("prj-c::0::coconut"),
    }
    ctx = make_ctx(inputs={"raw_dataset": [peanut, coconut]})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert set(result.outputs["samples"]) == set(peanut) | set(coconut)


def test_connected_raw_labels_are_joined_without_loading_legacy_annotations(
    make_ctx, monkeypatch,
):
    raw_labels = {
        "prj-a::0::peanut": {"target_label": "yes"},
        "prj-b::0::peanut": {"target_label": "partial"},
    }

    def legacy_loader_must_not_run(**_kwargs):
        raise AssertionError("legacy video annotations should not be loaded")

    monkeypatch.setattr(dataset_node, "load_human_annotations", legacy_loader_must_not_run)
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset(), "raw_labels": raw_labels})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["labels"] == raw_labels


def test_raw_label_fan_in_joins_only_sampled_items(make_ctx):
    raw_labels = [
        {"prj-a::0::peanut": {"target_label": "yes"}},
        {"prj-b::0::peanut": {"target_label": "no"}},
    ]
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset(), "raw_labels": raw_labels},
        params={"item_id_pattern": r"^prj-a::"},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert result.outputs["labels"] == {
        "prj-a::0::peanut": {"target_label": "yes"},
    }


def test_use_case_filter(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["speech-driven"]})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["samples"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}


def test_item_id_pattern(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"item_id_pattern": r"^prj-a::"})
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["samples"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}


def test_sampling_ratio_unified(make_ctx):
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 0.5, "sampling_mode": "unified"},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["samples"]) == 2


def test_sampling_ratio_above_one_is_an_absolute_count(make_ctx):
    # _raw_dataset() has 4 items; a value > 1 samples exactly that many, not a fraction.
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"sampling_ratio": 3})
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["samples"]) == 3


def test_count_is_clamped_to_the_available_items(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"sampling_ratio": 99})
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["samples"]) == 4  # only 4 exist


def test_full_dataset_toggle_overrides_the_ratio(make_ctx):
    # full_dataset on → the whole (filtered) pool, ignoring a fractional sampling_ratio.
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 0.25, "full_dataset": True},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["samples"]) == 4


def test_sampling_ratio_alone_takes_effect_without_an_explicit_mode(make_ctx):
    # Regression guard: sampling_mode used to default to a "full" mode that silently
    # ignored ratio entirely — setting only sampling_ratio (leaving mode unset) must
    # actually narrow the selection now that "full" no longer exists.
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"sampling_ratio": 0.5})
    result = DatasetNodeExecutor().run(ctx)
    assert len(result.outputs["samples"]) == 2


def test_sampling_uses_use_case_already_on_each_item_not_a_re_derivation(make_ctx):
    # Confirms the Dataset Node reads `use_case` straight off each already-loaded item
    # (set upstream, e.g. by a source node) rather than trying to recompute it — stratified
    # sampling here must split evenly across the two use_cases already present.
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 0.5, "sampling_mode": "stratified"},
    )
    result = DatasetNodeExecutor().run(ctx)
    dataset = result.outputs["samples"]
    assert len(dataset) == 2
    use_cases = {item["use_case"] for item in dataset.values()}
    assert use_cases == {"visual montage", "speech-driven"}  # one from each group


def test_split_label_stratified_balances_train_and_preserves_test_prevalence(make_ctx):
    raw_dataset = {}
    raw_labels = {}
    # Train is deliberately majority-"no"; the six-case subset should still contain all
    # three train classes. Test remains prevalence-weighted instead of being balanced.
    rows = [
        ("train", "no", 12), ("train", "partial", 3), ("train", "yes", 3),
        ("test", "no", 60), ("test", "partial", 8), ("test", "yes", 4),
    ]
    for split, label, count in rows:
        for index in range(count):
            item_id = f"{split}-{label}-{index}::0::peanut"
            raw_dataset[item_id] = {
                **_raw_item(item_id),
                "split": split,
            }
            raw_labels[item_id] = {
                "target_label": label,
                "split": split,
            }

    result = DatasetNodeExecutor().run(make_ctx(
        inputs={"raw_dataset": raw_dataset, "raw_labels": raw_labels},
        params={
            "sampling_ratio": 12,
            "sampling_mode": "split_label_stratified",
            "require_labels": True,
        },
    ))

    assert result.status == "done"
    selected = result.outputs["samples"]
    train_labels = [
        raw_labels[item_id]["target_label"]
        for item_id in selected
        if raw_dataset[item_id]["split"] == "train"
    ]
    test_labels = [
        raw_labels[item_id]["target_label"]
        for item_id in selected
        if raw_dataset[item_id]["split"] == "test"
    ]
    assert sorted(train_labels) == ["no", "partial", "yes"]
    assert test_labels.count("no") > test_labels.count("partial") >= test_labels.count("yes")


def test_split_specific_ratios_keep_complete_task_groups(make_ctx):
    raw_dataset = {}
    raw_labels = {}
    for split, n_tasks in (("train", 3), ("test", 10)):
        for task_index in range(n_tasks):
            task_uid = f"{split}-task-{task_index}"
            for editor_index, editor in enumerate(("A", "B")):
                item_id = f"{task_uid}::{editor_index}::{editor}"
                raw_dataset[item_id] = {
                    **_raw_item(item_id),
                    "split": split,
                    "task_uid": task_uid,
                    "editor": editor,
                }
                raw_labels[item_id] = {
                    "target_label": "no",
                    "split": split,
                }

    result = DatasetNodeExecutor().run(make_ctx(
        inputs={"raw_dataset": raw_dataset, "raw_labels": raw_labels},
        params={
            "sampling_mode": "split_label_stratified",
            "train_sampling_ratio": 1.0,
            "test_sampling_ratio": 0.2,
            "group_by_task": True,
            "require_labels": True,
        },
    ))

    selected = result.outputs["samples"]
    assert result.status == "done"
    assert result.meta["split_counts"] == {"train": 6, "test": 4}
    assert result.meta["task_counts"] == {"train": 3, "test": 2}
    by_task = {}
    for sample in selected.values():
        by_task.setdefault(sample["task_uid"], set()).add(sample["editor"])
    assert all(editors == {"A", "B"} for editors in by_task.values())


def test_group_offsets_produce_complementary_heldout_halves(make_ctx):
    raw_dataset = {}
    raw_labels = {}
    for task_index in range(10):
        task_uid = f"test-task-{task_index}"
        for editor in ("A", "B"):
            item_id = f"{task_uid}::0::{editor}"
            raw_dataset[item_id] = {
                **_raw_item(item_id),
                "split": "test",
                "task_uid": task_uid,
                "editor": editor,
            }
            raw_labels[item_id] = {
                "target_label": "no",
                "split": "test",
            }

    halves = []
    for offset in (0, 1):
        result = DatasetNodeExecutor().run(make_ctx(
            node_id=f"dataset-{offset}",
            inputs={
                "raw_dataset": raw_dataset,
                "raw_labels": raw_labels,
            },
            params={
                "sampling_mode": "split_label_stratified",
                "test_sampling_ratio": 0.5,
                "test_group_offset": offset,
                "group_by_task": True,
                "require_labels": True,
            },
        ))
        halves.append(set(result.outputs["samples"]))

    assert halves[0].isdisjoint(halves[1])
    assert halves[0] | halves[1] == set(raw_dataset)


def test_split_label_stratified_requires_source_labels(make_ctx):
    result = DatasetNodeExecutor().run(make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"sampling_ratio": 3, "sampling_mode": "split_label_stratified"},
    ))
    assert result.status == "error"
    assert "raw_labels" in result.error


def test_missing_raw_dataset_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "error"


def test_zero_items_after_sampling_gets_a_warning(make_ctx):
    ctx = make_ctx(inputs={"raw_dataset": _raw_dataset()}, params={"use_case_filter": ["nonexistent"]})
    result = DatasetNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["samples"] == {}
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
    ctx = make_ctx(
        inputs={"raw_dataset": _raw_dataset()},
        params={"use_case_filter": ["visual montage"], "aggregation_method": "mean"},
    )
    result = DatasetNodeExecutor().run(ctx)
    assert set(result.outputs["samples"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}
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
    assert set(result.outputs["samples"]) == {"prj-a::0::peanut", "prj-a::1::peanut"}
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
    assert set(result.outputs["samples"]) == {"prj-a::0::peanut"}
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
    assert set(result.outputs["samples"]) == {"prj-b::0::peanut", "prj-b::1::peanut"}
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
    assert set(result.outputs["samples"]) == {"prj-a::0::peanut"}
    assert result.outputs["labels"] == {}
    assert result.meta["n_pool_labeled"] == 1
    assert "none have human labels" in result.meta["warning"]
    assert "require_labels" in result.meta["warning"]
