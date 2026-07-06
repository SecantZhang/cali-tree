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
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    report = result.outputs["metrics_report"]
    assert report["n_items"] == 5
    pd = report["per_dimension"]["video_addresses_prompt"]
    assert pd["n"] == 5
    assert pd["spearman"] is not None and pd["spearman"] > 0.99
    assert "use_case" in pd["by_category"]


def test_writes_eval_json_to_run_dir(make_ctx):
    ctx = make_ctx(
        node_id="eval1", inputs={"judge_result": _judge_results(), "labels": _labels()}
    )
    EvalNodeExecutor().run(ctx)
    assert (ctx.run.run_dir / "eval_eval1.json").is_file()


def test_missing_judge_result_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "error"


def test_missing_labels_input_is_a_node_error(make_ctx):
    ctx = make_ctx(inputs={"judge_result": _judge_results()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "error"


def test_no_overlapping_items_yields_empty_report(make_ctx):
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    # Default make_ctx is dry_run=True — a dry-run Judge Node never produces judge_result
    # rows by design, so 0 aligned items here is expected and must NOT be flagged.
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "warning" not in result.meta


def test_no_overlapping_items_on_a_live_run_gets_a_warning(make_ctx):
    labels = {"other::0::peanut": AggregatedHumanRecord(
        item_id="other::0::peanut", project="other", prompt_idx=0, model="peanut",
    )}
    ctx = make_ctx(dry_run=False, inputs={"judge_result": _judge_results(), "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 0
    assert "0 aligned items" in result.meta["warning"]


def test_live_run_with_overlapping_items_has_no_warning(make_ctx):
    ctx = make_ctx(dry_run=False, inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert "warning" not in result.meta
