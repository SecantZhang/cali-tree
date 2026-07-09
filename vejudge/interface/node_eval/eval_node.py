"""Eval Node executors — human-vs-judge agreement metrics, split by modality.

Mirrors ``HumanGapBenchmark``'s gap computation, reusing the same shared functions the
CLI benchmark uses (``postprocessing.align.build_aligned_rows``,
``core.eval.report.per_dimension_agreement``) so both compute the gap identically. Never
gated by dry-run/--live — it makes no gateway calls of its own.

Two node types, Eval Text (``eval_text``) and Eval Video (``eval_video``), each scoped to
one modality's dimensions (``postprocessing.align.TEXT_DIMENSIONS``/``VIDEO_DIMENSIONS``,
which partition ``ALIGNMENT`` with zero overlap) so a Judge node's single ``judge_result``
output feeds directly into the matching Eval node — no more merging two `judge_result_*`
inputs into one dict, since each Eval node now only ever sees one modality's Judge output.
"""

from __future__ import annotations

from typing import ClassVar

from ...core.eval.report import per_dimension_agreement
from ...postprocessing.align import (
    TEXT_DIMENSIONS,
    VIDEO_DIMENSIONS,
    build_aligned_rows,
    diagnose_missing_rows,
)
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


class _EvalNodeExecutorBase(NodeExecutor):
    category = "node_eval"
    input_sockets = {"judge_result": "judge_result", "labels": "labels"}
    output_sockets = {"metrics_report": "metrics_report"}
    param_schema: dict = {}
    # Opts into streaming batch-eval previews (see judge nodes' `batch_size` +
    # GraphExecutionEngine._emit_partial_previews) — recomputing the whole report from
    # scratch on each partial `judge_result` is deliberate, not just simplest: Spearman/
    # Kendall/QWK are rank-based statistics with no simple incremental-sufficient-statistic
    # update, and at this data scale (tens of items) a full recompute is cheap regardless.
    supports_partial_input = True

    # Set by each concrete subclass.
    label: ClassVar[str]
    dimensions: ClassVar[frozenset[str]]

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        judge_result = ctx.inputs.get("judge_result")
        labels = ctx.inputs.get("labels")
        if judge_result is None:
            return NodeRunResult(
                status="error",
                error=f"{self.label} Node requires a 'judge_result' input (wire a Judge "
                "Node's `judge_result` output)",
            )
        if labels is None:
            return NodeRunResult(
                status="error",
                error=f"{self.label} Node requires a 'labels' input (wire a Dataset "
                "Node's `labels` output)",
            )

        items = sorted(set(judge_result) & set(labels))
        rows = build_aligned_rows(items, labels, judge_result, dimensions=self.dimensions)
        report = {
            "n_items": len(items),
            "n_aligned_rows": len(rows),
            "per_dimension": per_dimension_agreement(rows, dimensions=self.dimensions),
            # Raw per-item (human, judge_raw) pairs, not just the aggregated per-dimension
            # stats above — the interface's Eval secondary tab plots these directly (a
            # human-vs-judge scatter), which the aggregated stats alone can't reconstruct.
            "rows": rows,
        }

        if ctx.is_preview:
            # Overwritten in place (one file per node, not one per batch) — this is a
            # live-preview snapshot, not part of the run's authoritative record.
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
        # A dry run's Judge nodes produce no judge_result rows by design, so 0 items here
        # is expected and not worth flagging — only warn when a *live* run aligned nothing,
        # which usually means the Judge and human-label item ids never actually overlapped.
        if not ctx.dry_run and len(items) == 0:
            meta["warning"] = (
                "0 aligned items on a live run. The Judge node's and the Dataset node's "
                "item ids never overlapped — check both sides' project/use_case/item-id "
                "filters produce the same item id space."
            )
        elif not ctx.dry_run and items and not any(
            dim_stats["n"] > 0 for dim_stats in report["per_dimension"].values()
        ):
            # Real item-id overlap, but every dimension still ended up with n == 0 —
            # build_aligned_rows silently skips a row for several distinct reasons (see
            # diagnose_missing_rows' docstring), none of which is otherwise visible; this
            # is exactly the "why is the Eval tab empty" case a live run can hit even with
            # a correctly-overlapping item space.
            meta["diagnostics"] = diagnose_missing_rows(
                items, labels, judge_result, dimensions=self.dimensions
            )
        return NodeRunResult(outputs={"metrics_report": report}, meta=meta)


@register
class EvalTextNodeExecutor(_EvalNodeExecutorBase):
    node_type = "eval_text"
    label = "Eval Text"
    dimensions = TEXT_DIMENSIONS


@register
class EvalVideoNodeExecutor(_EvalNodeExecutorBase):
    node_type = "eval_video"
    label = "Eval Video"
    dimensions = VIDEO_DIMENSIONS
