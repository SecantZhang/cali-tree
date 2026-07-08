from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_eval.eval_node import EvalNodeExecutor


def _labels():
    return {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut",
            project="prj-x",
            prompt_idx=i,
            model="peanut",
            use_case="visual montage",
            scores={"video_addresses_prompt": float(1 + (i % 5))},
        )
        for i in range(5)
    }


def _judge_results():
    return {
        f"prj-x::{i}::peanut": {"M3": {"parsed": {"score_1_to_5": 1 + (i % 5)}}}
        for i in range(5)
    }


def test_metrics_report_shape(make_ctx):
    ctx = make_ctx(inputs={"judge_result_text": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    report = result.outputs["metrics_report"]
    assert report["n_items"] == 5
    pd = report["per_dimension"]["video_addresses_prompt"]
    assert pd["n"] == 5
    assert pd["spearman"] is not None and pd["spearman"] > 0.99
    assert "use_case" in pd["by_category"]


def test_metrics_report_includes_raw_rows_for_charting(make_ctx):
    # The scatter plot in the Eval secondary tab needs the raw (human, judge_raw) pairs
    # per item — the aggregated per_dimension stats alone can't reconstruct them.
    ctx = make_ctx(inputs={"judge_result_text": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    rows = result.outputs["metrics_report"]["rows"]
    assert len(rows) == 5
    row = next(r for r in rows if r["item_id"] == "prj-x::0::peanut")
    assert row["dimension"] == "video_addresses_prompt"
    assert row["human"] == 1.0
    assert row["judge_raw"] == 1.0


def test_writes_eval_json_to_run_dir(make_ctx):
    ctx = make_ctx(
        node_id="eval1", inputs={"judge_result_text": _judge_results(), "labels": _labels()}
    )
    EvalNodeExecutor().run(ctx)
    assert (ctx.run.run_dir / "eval_eval1.json").is_file()


def test_missing_both_judge_result_inputs_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "error"


def test_missing_labels_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"judge_result_text": _judge_results()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "error"


def test_video_only_judge_result_works_without_text(make_ctx):
    # A text Judge Node isn't required to be wired at all — a video-only graph is a
    # normal, supported shape (mirrors run/run_text_only.sh's inverse).
    ctx = make_ctx(inputs={"judge_result_video": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 5


def test_merges_text_and_video_judge_results_per_item(make_ctx):
    text = {"prj-x::0::peanut": {"M3": {"parsed": {"score_1_to_5": 4}}}}
    video = {"prj-x::0::peanut": {"M2": {"parsed": {"score_1_to_5": 5}}}}
    ctx = make_ctx(inputs={"judge_result_text": text, "judge_result_video": video, "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 1


def test_merge_does_not_lose_items_only_present_on_one_side(make_ctx):
    text = {"prj-x::0::peanut": {"M3": {"parsed": {"score_1_to_5": 4}}}}
    video = {"prj-x::1::peanut": {"M2": {"parsed": {"score_1_to_5": 5}}}}
    ctx = make_ctx(inputs={"judge_result_text": text, "judge_result_video": video, "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 2  # both items aligned, disjoint metrics


def test_no_overlapping_items_yields_empty_report(make_ctx):
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    # Default make_ctx is dry_run=True — a dry-run Judge Node never produces judge_result
    # rows by design, so 0 aligned items here is expected and must NOT be flagged.
    ctx = make_ctx(inputs={"judge_result_text": _judge_results(), "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "warning" not in result.meta


def test_no_overlapping_items_on_a_live_run_gets_a_warning(make_ctx):
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    ctx = make_ctx(dry_run=False, inputs={"judge_result_text": _judge_results(), "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "0 aligned items" in result.meta["warning"]


def test_live_run_with_overlapping_items_has_no_warning(make_ctx):
    ctx = make_ctx(dry_run=False, inputs={"judge_result_text": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert "warning" not in result.meta
    assert "diagnostics" not in result.meta


def test_real_item_overlap_but_zero_aligned_rows_gets_diagnostics_not_silence(make_ctx):
    # Item ids genuinely overlap (so the "0 aligned items" warning wouldn't fire), but the
    # judge side never produced M3 at all — every dimension ends up with n == 0 anyway.
    # This is exactly the "why is the Eval tab empty" case that used to have no explanation.
    judge_result = {iid: {} for iid in _labels()}
    ctx = make_ctx(dry_run=False, inputs={"judge_result_text": judge_result, "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 5  # real item-id overlap
    assert "warning" not in result.meta
    diag = result.meta["diagnostics"]
    assert diag
    entry = next(d for d in diag if d["dimension"] == "video_addresses_prompt")
    assert "never produced" in entry["reason"]
    assert entry["count"] == 5


def test_supports_partial_input_is_opted_in():
    assert EvalNodeExecutor.supports_partial_input is True


def test_preview_writes_a_partial_json_not_the_authoritative_one(make_ctx):
    ctx = make_ctx(
        node_id="eval1", inputs={"judge_result_text": _judge_results(), "labels": _labels()},
    )
    ctx.is_preview = True
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert (ctx.run.run_dir / "eval_eval1.partial.json").is_file()
    assert not (ctx.run.run_dir / "eval_eval1.json").exists()
    # Same report shape as an authoritative run against the same (here, full) inputs.
    assert result.outputs["metrics_report"]["n_items"] == 5


def test_preview_recomputes_from_scratch_against_a_partial_judge_result(make_ctx):
    # Only 2 of the 5 items have any judge_result yet — a real mid-run snapshot shape.
    partial_judge_result = {k: v for k, v in list(_judge_results().items())[:2]}
    ctx = make_ctx(inputs={"judge_result_text": partial_judge_result, "labels": _labels()})
    ctx.is_preview = True
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 2


def test_preview_never_sets_the_zero_items_live_warning(make_ctx):
    # A preview mid-run showing 0 aligned items yet is expected (nothing has completed),
    # not worth the same warning the authoritative live-run result would raise.
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    ctx = make_ctx(dry_run=False, inputs={"judge_result_text": _judge_results(), "labels": labels})
    ctx.is_preview = True
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "warning" not in result.meta
