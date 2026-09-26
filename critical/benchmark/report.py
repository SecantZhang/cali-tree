"""Human-readable gap reports: a metrics table (xlsx/csv) + per-dimension charts.

All heavy deps are optional — if openpyxl/matplotlib are absent the report degrades to
CSV and skips charts, so a benchmark run never fails on reporting.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _dimension_table(gap: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dim, d in gap.get("per_dimension", {}).items():
        rows.append(
            {
                "dimension": dim,
                "judge_signal": d.get("judge_signal"),
                "n": d.get("n"),
                "spearman": d.get("spearman"),
                "kendall": d.get("kendall"),
                "mae": d.get("mae"),
                "qwk": d.get("qwk"),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_xlsx(path: Path, rows: list[dict[str, Any]]) -> bool:
    try:
        from openpyxl import Workbook
    except ImportError:
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "gap_by_dimension"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h) for h in headers])
    wb.save(path)
    return True


def _chart(path: Path, rows: list[dict[str, Any]]) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    if not rows:
        return False

    dims = [r["dimension"] for r in rows]
    spearman = [r["spearman"] if r["spearman"] is not None else 0.0 for r in rows]
    mae = [r["mae"] if r["mae"] is not None else 0.0 for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.barh(dims, spearman, color="#4C78A8")
    ax1.set_title("Spearman (human vs judge)")
    ax1.set_xlim(-1, 1)
    ax1.axvline(0, color="gray", lw=0.8)
    ax2.barh(dims, mae, color="#E45756")
    ax2.set_title("MAE (1-5 scale)")
    ax2.set_xlim(0, 4)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def generate_gap_report(
    gap: dict[str, Any], aligned_rows: list[dict[str, Any]], output_dir: str
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = _dimension_table(gap)

    if not _write_xlsx(out / "gap_report.xlsx", rows):
        _write_csv(out / "gap_report.csv", rows)
    _chart(out / "chart_gap_by_dimension.png", rows)
