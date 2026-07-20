"""Alignment Report Node — presents a judge's human-alignment (from an upstream Eval node's
``metrics_report``) the way video-quality-assessment papers do: per-dimension **SRCC / PLCC /
KRCC** + MAE, next to the **inter-rater human ceiling** and the **published VE-Bench
baselines**, so "where does our judge land" is legible at a glance.

Pure presentation — it re-surfaces an already-computed report (the Eval node did the
correlations), makes no gateway calls, and is never gated by dry-run/--live. Mirrors the
Rule Comparison node's "read a report, frame it" role, but for judge-vs-human correlation
against a benchmark instead of the rule-tree MAE comparison.
"""

from __future__ import annotations

from typing import Any

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

# Published VE-Bench reference (Adv. Eng. Informatics 58, 2023, Table 2) — SRCC/PLCC on the
# 1,170-item human-MOS set. Shown as reference context so our judge's number reads directly
# against the paper's rows (zero-shot metrics → trained VE-Bench QA).
VEBENCH_BASELINES: list[dict[str, Any]] = [
    {"method": "CLIP-F", "kind": "zero-shot", "srcc": 0.228, "plcc": 0.186},
    {"method": "PickScore", "kind": "zero-shot", "srcc": 0.227, "plcc": 0.245},
    {"method": "DOVER", "kind": "VQA model", "srcc": 0.612, "plcc": 0.630},
    {"method": "FastVQA", "kind": "VQA model", "srcc": 0.633, "plcc": 0.633},
    {"method": "StableVQA", "kind": "VQA model", "srcc": 0.689, "plcc": 0.678},
    {"method": "VE-Bench QA", "kind": "trained on VE-Bench", "srcc": 0.742, "plcc": 0.733},
]


def _band(srcc: float) -> str:
    """Where an SRCC lands relative to the VE-Bench reference bands."""
    if srcc < 0.30:
        return "at the zero-shot baseline level (CLIP-F / PickScore ~0.23)"
    if srcc < 0.60:
        return "above the zero-shot baselines, below the specialized VQA models"
    if srcc < 0.72:
        return "in the specialized-VQA range (DOVER/FastVQA/StableVQA 0.61–0.69)"
    return "at or above the trained VE-Bench QA metric (0.74)"


@register
class AlignmentReportNodeExecutor(NodeExecutor):
    node_type = "alignment_report"
    category = "node_eval"
    input_sockets = {"metrics_report": "metrics_report"}
    output_sockets = {"comparison": "metrics_report"}
    param_schema: dict = {}
    label = "Alignment Report"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        report = ctx.inputs.get("metrics_report")
        if report is None:
            return NodeRunResult(
                status="error",
                error="Alignment Report Node requires a 'metrics_report' input (wire an Eval "
                "node's `metrics_report` output).",
            )

        per_dim = report.get("per_dimension") or {}
        ceiling = report.get("human_ceiling") or {}
        rows: list[dict[str, Any]] = []
        for dim, d in per_dim.items():
            if not isinstance(d, dict) or (d.get("n") or 0) <= 0:
                continue  # only dimensions with aligned human+judge rows
            c = ceiling.get(dim) or {}
            rows.append({
                "dimension": dim,
                "n": d.get("n"),
                "srcc": d.get("spearman"),
                "plcc": d.get("pearson"),
                "krcc": d.get("kendall"),
                "mae": d.get("mae"),
                # Inter-rater ceiling (mean |rater - item mean|), when raters disagree — the
                # noise floor the judge's MAE should be read against.
                "human_ceiling_mae": c.get("self_mae"),
            })

        # Verdict on the strongest dimension by SRCC (the headline agreement number).
        scored = [r for r in rows if isinstance(r.get("srcc"), (int, float))]
        verdict = "No aligned dimensions yet — run the judge + Eval on labeled items first."
        if scored:
            best = max(scored, key=lambda r: r["srcc"])
            verdict = (
                f"Best dimension '{best['dimension']}': SRCC {best['srcc']:.3f} — "
                + _band(float(best["srcc"]))
                + " (vs the VE-Bench published table)."
            )

        out = {
            "rows": rows,
            "verdict": verdict,
            "baselines": VEBENCH_BASELINES,
            "n_items": report.get("n_items"),
        }
        ctx.run.write_json(f"alignment_report_{ctx.node_id}.json", out)
        ctx.run.logger.info("%s[%s]: %s", self.label, ctx.node_id, verdict)
        return NodeRunResult(outputs={"comparison": out}, meta={"n_dimensions": len(rows)})
