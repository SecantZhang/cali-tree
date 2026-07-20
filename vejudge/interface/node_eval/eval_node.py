"""Eval Node — human-vs-judge agreement metrics for one judge path.

Mirrors ``HumanGapBenchmark``'s gap computation, reusing the same shared functions the CLI
benchmark uses (``postprocessing.align.build_aligned_rows``,
``core.eval.report.per_dimension_agreement``) so both compute the gap identically. Never
gated by dry-run/--live — it makes no gateway calls of its own.

One generic node type (``eval``): it **auto-scopes** its dimensions to whatever the incoming
``judge_result`` actually covers, instead of a fixed modality frozenset — a builtin metric
resolves its dimensions via ``ALIGNMENT``; a custom judge carries its own target dimension.
So a single-metric Judge path feeds directly into its own Eval node, reporting exactly that
metric's dimension(s).
"""

from __future__ import annotations

from typing import Any

from ...postprocessing.align import (
    ALIGNMENT,
    build_aligned_rows,
    diagnose_missing_rows,
)
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


def dimensions_for_judge_result(judge_result: dict[str, Any]) -> frozenset[str]:
    """The human dimensions this judge_result can be aligned on: builtin metrics via the
    ``ALIGNMENT`` crosswalk, plus any custom entry's carried ``align.dimension``.
    """
    present_keys: set[str] = set()
    custom_dims: set[str] = set()
    for item in judge_result.values():
        if not isinstance(item, dict):
            continue
        for key, entry in item.items():
            present_keys.add(key)
            align = entry.get("align") if isinstance(entry, dict) else None
            if isinstance(align, dict) and align.get("dimension"):
                custom_dims.add(align["dimension"])
    builtin_dims = {d for d, (mid, _ext) in ALIGNMENT.items() if mid in present_keys}
    return frozenset(builtin_dims | custom_dims)


@register
class EvalNodeExecutor(NodeExecutor):
    node_type = "eval"
    category = "node_eval"
    input_sockets = {"judge_result": "judge_result", "labels": "labels"}
    output_sockets = {"metrics_report": "metrics_report"}
    param_schema: dict = {}
    # Opts into streaming batch-eval previews (see the Judge node's `batch_size` +
    # GraphExecutionEngine._emit_partial_previews) — recomputing the whole report from
    # scratch on each partial `judge_result` is deliberate: Spearman/Kendall/QWK are
    # rank-based statistics with no simple incremental update, and at this data scale (tens
    # of items) a full recompute is cheap regardless.
    supports_partial_input = True
    label = "Eval"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        from ...core.eval.rater_agreement import inter_rater_agreement
        from ...core.eval.report import per_dimension_agreement

        judge_result = ctx.inputs.get("judge_result")
        labels = ctx.inputs.get("labels")
        if judge_result is None:
            return NodeRunResult(
                status="error",
                error="Eval Node requires a 'judge_result' input (wire a Judge Node's "
                "`judge_result` output)",
            )
        if labels is None:
            return NodeRunResult(
                status="error",
                error="Eval Node requires a 'labels' input (wire a Dataset Node's "
                "`labels` output)",
            )

        dimensions = dimensions_for_judge_result(judge_result)
        items = sorted(set(judge_result) & set(labels))
        rows = build_aligned_rows(items, labels, judge_result, dimensions=dimensions)
        # Human ceiling: how far raters sit from their own item mean, per dimension. Read the
        # judge's per_dimension agreement against this — being within the inter-rater spread
        # is the noise floor. Sourced from the per-rater values kept on each label record.
        ceiling = {
            dim: {"self_mae": ra.self_mae, "pairwise_mae": ra.pairwise_mae,
                  "n_items": ra.n_items, "n_ratings": ra.n_ratings}
            for dim, ra in inter_rater_agreement(
                [getattr(labels[i], "raw_scores", {}) or {} for i in items],
                dimensions=dimensions,
            ).items()
        }
        report = {
            "n_items": len(items),
            "n_aligned_rows": len(rows),
            "per_dimension": per_dimension_agreement(rows, dimensions=dimensions),
            "human_ceiling": ceiling,
            # Raw per-item (human, judge_raw) pairs — the Eval secondary tab plots these
            # directly (a human-vs-judge scatter) which the aggregated stats can't reconstruct.
            "rows": rows,
        }

        if ctx.is_preview:
            ctx.run.write_json(f"eval_{ctx.node_id}.partial.json", report)
            return NodeRunResult(
                outputs={"metrics_report": report}, meta={"n_items": len(items)}
            )

        ctx.run.write_json(f"eval_{ctx.node_id}.json", report)
        ctx.run.logger.info(
            "%s[%s]: %d items, %d aligned rows",
            self.label, ctx.node_id, len(items), len(rows),
        )
        meta: dict[str, object] = {"n_items": len(items)}
        if not ctx.dry_run and len(items) == 0:
            meta["warning"] = (
                "0 aligned items on a live run. The Judge node's and the Dataset node's "
                "item ids never overlapped — check both sides' project/use_case/item-id "
                "filters produce the same item id space."
            )
        elif not ctx.dry_run and items and not any(
            dim_stats["n"] > 0 for dim_stats in report["per_dimension"].values()
        ):
            meta["diagnostics"] = diagnose_missing_rows(
                items, labels, judge_result, dimensions=dimensions
            )
        return NodeRunResult(outputs={"metrics_report": report}, meta=meta)
