"""Per-dimension human-vs-judge agreement, broken down by category.

Extracted from ``benchmark/human_gap/runner.py::HumanGapBenchmark._compute_gap`` so the
CLI benchmark and the interface's Eval Node executor share one implementation.
"""

from __future__ import annotations

from typing import Any, Optional

from ...postprocessing.align import ALIGNMENT, JUDGE_SIGNAL_LABEL
from . import metrics as M


def per_dimension_agreement(
    rows: list[dict[str, Any]], *, dimensions: Optional[frozenset[str]] = None
) -> dict[str, Any]:
    """One agreement report per human dimension in ``ALIGNMENT``, from aligned rows.

    ``rows`` is the shape produced by ``postprocessing.align.build_aligned_rows``:
    ``{item_id, project, model, use_case, dimension, human, judge_raw}``. ``dimensions``
    restricts the report to a subset of ``ALIGNMENT`` (e.g. one modality's dimensions) —
    ``None`` (the default) covers all of them, matching the CLI benchmark's unified report.
    """
    per_dimension: dict[str, Any] = {}
    dims = dimensions if dimensions is not None else ALIGNMENT
    for dim in dims:
        drows = [r for r in rows if r["dimension"] == dim]
        h = [r["human"] for r in drows]
        j = [r["judge_raw"] for r in drows]
        per_dimension[dim] = {
            "judge_signal": JUDGE_SIGNAL_LABEL.get(dim, dim),
            "n": len(drows),
            "spearman": M.spearman(h, j),
            "pearson": M.pearson(h, j),
            "kendall": M.kendall(h, j),
            "mae": M.mae(h, j),
            "rmse": M.rmse(h, j),
            "qwk": M.quadratic_weighted_kappa(h, j),
            "by_category": {
                "use_case": M.by_category(
                    drows, category_key="use_case", metric_fn=M.spearman,
                    x_key="human", y_key="judge_raw",
                ),
                "model": M.by_category(
                    drows, category_key="model", metric_fn=M.spearman,
                    x_key="human", y_key="judge_raw",
                ),
            },
        }
    return per_dimension
