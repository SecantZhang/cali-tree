from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.interface.node_eval.eval_node import EvalNodeExecutor


def _labels(dim="video_addresses_prompt"):
    return {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut",
            project="prj-x",
            prompt_idx=i,
            model="peanut",
            use_case="visual montage",
            scores={dim: float(1 + (i % 5))},
        )
        for i in range(5)
    }


def _judge_results(metric="M3"):
    return {
        f"prj-x::{i}::peanut": {metric: {"parsed": {"score_1_to_5": 1 + (i % 5)}}}
        for i in range(5)
    }


def _none_labels(dim="video_addresses_prompt", n_raters=3):
    """Labels from a Dataset node with aggregation_method="none": no aggregate `scores`,
    per-rater values in `raw_scores`, tagged aggregation="none"."""
    return {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut", project="prj-x", prompt_idx=i, model="peanut",
            use_case="visual montage", aggregation="none",
            scores={dim: None},
            raw_scores={dim: [float(1 + (i % 5))] * n_raters},
            n_annotators=n_raters,
        )
        for i in range(5)
    }


def test_none_aggregation_scores_judge_against_each_rater(make_ctx):
    # 5 items × 3 raters → one aligned row per rater (15), not one per item (5).
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": _none_labels(n_raters=3)})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    report = result.outputs["metrics_report"]
    assert report["aggregation"] == "none"
    assert report["n_items"] == 5
    assert report["n_aligned_rows"] == 15  # per-rater rows
    assert report["per_dimension"]["video_addresses_prompt"]["n"] == 15


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


def test_auto_scopes_to_the_incoming_metric_only(make_ctx):
    # A single-metric M3 judge_result → only M3's dimension (video_addresses_prompt) appears.
    ctx = make_ctx(inputs={"judge_result": _judge_results("M3"), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert set(result.outputs["metrics_report"]["per_dimension"]) == {"video_addresses_prompt"}


def test_auto_scopes_to_a_video_metric(make_ctx):
    # An M5 judge_result auto-scopes to M5's (video-modality) dimensions, not M3's.
    labels = {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut", project="prj-x", prompt_idx=i, model="peanut",
            use_case="visual montage",
            scores={"story_flow_visuals": float(1 + (i % 5))},
        )
        for i in range(5)
    }
    ctx = make_ctx(inputs={"judge_result": _judge_results("M5"), "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    dims = set(result.outputs["metrics_report"]["per_dimension"])
    assert "story_flow_visuals" in dims
    assert "video_addresses_prompt" not in dims  # M3's dimension, not present here


def test_aligns_a_custom_spec_by_its_carried_dimension(make_ctx):
    # A custom judge result carries its own align: {dimension, score_path} — Eval uses it
    # even though the spec id is not in the builtin ALIGNMENT crosswalk.
    judge_result = {
        f"prj-x::{i}::peanut": {
            "my_custom": {
                "parsed": {"score_1_to_5": 1 + (i % 5)},
                "align": {"dimension": "story_flow_voiceover", "score_path": "score_1_to_5"},
            }
        }
        for i in range(5)
    }
    labels = {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut", project="prj-x", prompt_idx=i, model="peanut",
            use_case="visual montage", scores={"story_flow_voiceover": float(1 + (i % 5))},
        )
        for i in range(5)
    }
    ctx = make_ctx(inputs={"judge_result": judge_result, "labels": labels})
    result = EvalNodeExecutor().run(ctx)
    pd = result.outputs["metrics_report"]["per_dimension"]
    assert set(pd) == {"story_flow_voiceover"}
    assert pd["story_flow_voiceover"]["n"] == 5


def test_metrics_report_includes_raw_rows_for_charting(make_ctx):
    ctx = make_ctx(inputs={"judge_result": _judge_results(), "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)

    rows = result.outputs["metrics_report"]["rows"]
    assert len(rows) == 5
    row = next(r for r in rows if r["item_id"] == "prj-x::0::peanut")
    assert row["dimension"] == "video_addresses_prompt"
    assert row["human"] == 1.0
    assert row["judge_raw"] == 1.0


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
    assert "diagnostics" not in result.meta


def test_real_item_overlap_but_zero_aligned_rows_gets_diagnostics_not_silence(make_ctx):
    judge_result = {iid: {"M3": {"parsed": {}}} for iid in _labels()}
    ctx = make_ctx(dry_run=False, inputs={"judge_result": judge_result, "labels": _labels()})
    result = EvalNodeExecutor().run(ctx)
    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 5  # real item-id overlap
    assert "warning" not in result.meta
    diag = result.meta["diagnostics"]
    assert diag


def test_supports_partial_input_is_opted_in():
    assert EvalNodeExecutor.supports_partial_input is True


def test_preview_writes_a_partial_json_not_the_authoritative_one(make_ctx):
    ctx = make_ctx(
        node_id="eval1", inputs={"judge_result": _judge_results(), "labels": _labels()},
    )
    ctx.is_preview = True
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert (ctx.run.run_dir / "eval_eval1.partial.json").is_file()
    assert not (ctx.run.run_dir / "eval_eval1.json").exists()
    assert result.outputs["metrics_report"]["n_items"] == 5


def test_preview_recomputes_from_scratch_against_a_partial_judge_result(make_ctx):
    partial_judge_result = {k: v for k, v in list(_judge_results().items())[:2]}
    ctx = make_ctx(inputs={"judge_result": partial_judge_result, "labels": _labels()})
    ctx.is_preview = True
    result = EvalNodeExecutor().run(ctx)

    assert result.status == "done"
    assert result.outputs["metrics_report"]["n_items"] == 2
