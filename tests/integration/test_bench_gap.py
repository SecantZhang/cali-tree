"""Gap computation + report schema, with no network and no real data."""

from vejudge.benchmark.human_gap.runner import HumanGapBenchmark
from vejudge.benchmark.report import generate_gap_report
from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord


def _synthetic_rows():
    rows = []
    for i in range(5):
        rows.append(
            {
                "item_id": f"prj-x::{i}::peanut",
                "project": "prj-x",
                "model": "peanut",
                "use_case": "visual montage",
                "dimension": "video_addresses_prompt",
                "human": float(1 + (i % 5)),
                "judge_raw": float(1 + (i % 5)),
            }
        )
    return rows


def test_compute_gap_schema(tmp_path):
    bench = HumanGapBenchmark(model="peanut")
    rows = _synthetic_rows()
    human = {
        f"prj-x::{i}::peanut": AggregatedHumanRecord(
            item_id=f"prj-x::{i}::peanut", project="prj-x", prompt_idx=i, model="peanut"
        )
        for i in range(5)
    }
    gap = bench._compute_gap(rows, human, {}, {"limit": 5})

    pd = gap["per_dimension"]["video_addresses_prompt"]
    assert pd["n"] == 5
    assert pd["spearman"] is not None and pd["spearman"] > 0.99
    assert "use_case" in pd["by_category"] and "model" in pd["by_category"]
    assert "pairwise_preference_accuracy" in gap
    assert gap["calibration_error"] is None


def test_report_writes_files(tmp_path):
    bench = HumanGapBenchmark(model="peanut")
    rows = _synthetic_rows()
    gap = bench._compute_gap(rows, {}, {}, {})
    generate_gap_report(gap, rows, str(tmp_path))
    produced = {p.name for p in tmp_path.iterdir()}
    # xlsx if openpyxl present, else csv; chart only if matplotlib present
    assert ("gap_report.xlsx" in produced) or ("gap_report.csv" in produced)
