from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_eval.eval_node import EvalVideoNodeExecutor


def _labels():
    return {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut",
            project="prj-x",
            prompt_idx=i,
            model="peanut",
            use_case="visual montage",
            scores={"story_flow_voiceover": float(1 + (i % 5))},
        )
        for i in range(5)
    }


def _judge_results():
    return {
        f"prj-x::{i}::peanut": {"M5": {"parsed": {"score_1_to_5": 1 + (i % 5)}}}
        for i in range(5)
    }


def test_metrics_report_shape(make_ctx):
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalVideoNodeExecutor().run(ctx)

    assert result.status == "done"
    report = result.outputs["metrics_report"]
    assert report["n_items"] == 5
    pd = report["per_dimension"]["story_flow_voiceover"]
    assert pd["n"] == 5
    assert pd["spearman"] is not None and pd["spearman"] > 0.99


def test_only_video_dimensions_appear_in_the_report(make_ctx):
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalVideoNodeExecutor().run(ctx)
    dims = set(result.outputs["metrics_report"]["per_dimension"])
    assert "video_addresses_prompt" not in dims
    assert "story_flow_voiceover" in dims


def test_writes_eval_json_to_run_dir(make_ctx):
    ctx = make_ctx(
        node_id="eval_v1", inputs={"judge_result": _judge_results(), "labels": _labels()}
    )
    EvalVideoNodeExecutor().run(ctx)
    assert (ctx.run.run_dir / "eval_eval_v1.json").is_file()


def test_missing_judge_result_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"labels": _labels()})
    result = EvalVideoNodeExecutor().run(ctx)
    assert result.status == "error"


def test_missing_labels_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"judge_result": _judge_results()})
    result = EvalVideoNodeExecutor().run(ctx)
    assert result.status == "error"


def test_no_overlapping_items_on_a_live_run_gets_a_warning(make_ctx):
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    ctx = make_ctx(dry_run=False, inputs={"judge_result": _judge_results(), "labels": labels})
    result = EvalVideoNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "0 aligned items" in result.meta["warning"]


def test_live_run_with_overlapping_items_has_no_warning(make_ctx):
    ctx = make_ctx(dry_run=False, inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalVideoNodeExecutor().run(ctx)
    assert result.status == "done"
    assert "warning" not in result.meta
    assert "diagnostics" not in result.meta


def test_real_item_overlap_but_zero_aligned_rows_gets_diagnostics_not_silence(make_ctx):
    # Item ids genuinely overlap, but the judge side never produced M5 at all — every
    # video dimension that resolves to M5 ends up with n == 0.
    judge_result = {iid: {} for iid in _labels()}
    ctx = make_ctx(dry_run=False, inputs={"judge_result": judge_result, "labels": _labels()})
    result = EvalVideoNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 5
    assert "warning" not in result.meta
    diag = result.meta["diagnostics"]
    assert diag
    entry = next(d for d in diag if d["dimension"] == "story_flow_voiceover")
    assert "never produced" in entry["reason"]


def test_supports_partial_input_is_opted_in():
    assert EvalVideoNodeExecutor.supports_partial_input is True


def test_preview_writes_a_partial_json_not_the_authoritative_one(make_ctx):
    ctx = make_ctx(
        node_id="eval_v1", inputs={"judge_result": _judge_results(), "labels": _labels()},
    )
    ctx.is_preview = True
    result = EvalVideoNodeExecutor().run(ctx)

    assert result.status == "done"
    assert (ctx.run.run_dir / "eval_eval_v1.partial.json").is_file()
    assert not (ctx.run.run_dir / "eval_eval_v1.json").exists()
    assert result.outputs["metrics_report"]["n_items"] == 5
