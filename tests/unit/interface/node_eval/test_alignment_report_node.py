"""Alignment Report node: re-frames an Eval node's metrics_report as per-dimension
SRCC/PLCC/KRCC + human ceiling + a verdict against the published VE-Bench baselines. Pure
display — no gateway calls."""

from vejudge.interface.node_eval.alignment_report_node import (
    VEBENCH_BASELINES,
    AlignmentReportNodeExecutor,
)


def _report(**dims):
    return {"n_items": 5, "per_dimension": dims,
            "human_ceiling": {"edit_quality": {"self_mae": 1.1}}}


def test_missing_input_is_a_node_error(make_ctx):
    res = AlignmentReportNodeExecutor().run(make_ctx(inputs={}))
    assert res.status == "error" and "metrics_report" in res.error


def test_builds_srcc_plcc_krcc_rows_with_human_ceiling(make_ctx):
    report = _report(edit_quality={
        "n": 120, "spearman": 0.545, "pearson": 0.508, "kendall": 0.415, "mae": 2.79, "qwk": 0.1,
    })
    res = AlignmentReportNodeExecutor().run(make_ctx(inputs={"metrics_report": report}))
    assert res.status == "done"
    comp = res.outputs["comparison"]
    row = comp["rows"][0]
    assert row["dimension"] == "edit_quality"
    assert (row["srcc"], row["plcc"], row["krcc"]) == (0.545, 0.508, 0.415)
    assert row["human_ceiling_mae"] == 1.1
    assert comp["baselines"] is VEBENCH_BASELINES
    # Verdict places 0.545 above zero-shot, below VQA models.
    assert "above the zero-shot" in comp["verdict"]


def test_skips_dimensions_with_no_aligned_rows(make_ctx):
    report = _report(edit_quality={"n": 0, "spearman": None, "pearson": None, "kendall": None})
    res = AlignmentReportNodeExecutor().run(make_ctx(inputs={"metrics_report": report}))
    assert res.outputs["comparison"]["rows"] == []
    assert "No aligned dimensions" in res.outputs["comparison"]["verdict"]


def test_band_thresholds(make_ctx):
    def band_for(srcc):
        r = AlignmentReportNodeExecutor().run(make_ctx(inputs={"metrics_report": _report(
            d={"n": 10, "spearman": srcc, "pearson": srcc, "kendall": srcc})}))
        return r.outputs["comparison"]["verdict"]
    assert "zero-shot baseline level" in band_for(0.2)
    assert "specialized-VQA range" in band_for(0.65)
    assert "trained VE-Bench QA" in band_for(0.8)
