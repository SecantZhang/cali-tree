"""Per-dimension human-vs-judge agreement, broken down by category.

Extracted from ``benchmark/human_gap/runner.py::HumanGapBenchmark._compute_gap`` so the
CLI benchmark and the interface's Eval Node executor share one implementation.
"""

from __future__ import annotations

from typing import Any

from ...postprocessing.align import ALIGNMENT, JUDGE_SIGNAL_LABEL
from . import metrics as M


def per_dimension_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One agreement report per human dimension in ``ALIGNMENT``, from aligned rows.

    ``rows`` is the shape produced by ``postprocessing.align.build_aligned_rows``:
    ``{item_id, project, model, use_case, dimension, human, judge_raw}``.
    """
    per_dimension: dict[str, Any] = {}
    for dim in ALIGNMENT:
        drows = [r for r in rows if r["dimension"] == dim]
        h = [r["human"] for r in drows]
        j = [r["judge_raw"] for r in drows]
        per_dimension[dim] = {
            "judge_signal": JUDGE_SIGNAL_LABEL[dim],
            "n": len(drows),
            "spearman": M.spearman(h, j),
            "kendall": M.kendall(h, j),
            "mae": M.mae(h, j),
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
