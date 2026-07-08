"""Eval Node executor — human-vs-judge agreement metrics.

Mirrors ``HumanGapBenchmark``'s gap computation, reusing the same shared functions the
CLI benchmark uses (``postprocessing.align.build_aligned_rows``,
``core.eval.report.per_dimension_agreement``) so both compute the gap identically.
Never gated by dry-run/--live — it makes no gateway calls of its own.
"""

from __future__ import annotations

from typing import Any

from ...core.eval.report import per_dimension_agreement
from ...postprocessing.align import build_aligned_rows, diagnose_missing_rows
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


def _merge_judge_results(
    text: dict[str, dict[str, Any]], video: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Unions the Text and Video Judge nodes' per-item metric dicts.

    Text/video metric ids are disjoint (M1/M3 vs M2/M4/M5/M6), so a plain per-item merge
    never loses either side's results even when both are wired.
    """
    merged: dict[str, dict[str, Any]] = {}
    for iid in set(text) | set(video):
        merged[iid] = {**text.get(iid, {}), **video.get(iid, {})}
    return merged


@register
class EvalNodeExecutor(NodeExecutor):
    node_type = "eval"
    category = "node_eval"
    input_sockets = {
        "judge_result_text": "judge_result",
        "judge_result_video": "judge_result",
        "labels": "labels",
    }
    output_sockets = {"metrics_report": "metrics_report"}
    param_schema: dict = {}
    # Opts into streaming batch-eval previews (see judge nodes' `batch_size` +
    # GraphExecutionEngine._emit_partial_previews) — recomputing the whole report from
    # scratch on each partial `judge_result` is deliberate, not just simplest: Spearman/
    # Kendall/QWK are rank-based statistics with no simple incremental-sufficient-statistic
    # update, and at this data scale (tens of items) a full recompute is cheap regardless.
    supports_partial_input = True

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        judge_result_text = ctx.inputs.get("judge_result_text")
        judge_result_video = ctx.inputs.get("judge_result_video")
        labels = ctx.inputs.get("labels")
        # Both judge_result inputs are optional (a text-only or video-only graph is a
        # normal, supported shape — see run/run_text_only.sh) — only erroring if neither
        # is wired at all.
        if judge_result_text is None and judge_result_video is None:
            return NodeRunResult(
                status="error",
                error="Eval Node requires at least one of 'judge_result_text'/"
                "'judge_result_video' (wire a Text and/or Video Judge Node's "
                "`judge_result` output)",
            )
        if labels is None:
            return NodeRunResult(
                status="error",
                error="Eval Node requires a 'labels' input (wire a Human Annotations "
                "Node's `labels` output)",
            )

        judge_result = _merge_judge_results(judge_result_text or {}, judge_result_video or {})

        items = sorted(set(judge_result) & set(labels))
        rows = build_aligned_rows(items, labels, judge_result)
        report = {
            "n_items": len(items),
            "n_aligned_rows": len(rows),
            "per_dimension": per_dimension_agreement(rows),
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
            "Eval[%s]: %d items, %d aligned rows", ctx.node_id, len(items), len(rows)
        )
        meta: dict[str, object] = {"n_items": len(items)}
        # A dry run's Judge nodes produce no judge_result rows by design, so 0 items here
        # is expected and not worth flagging — only warn when a *live* run aligned nothing,
        # which usually means the Judge and human-label item ids never actually overlapped.
        if not ctx.dry_run and len(items) == 0:
            meta["warning"] = (
                "0 aligned items on a live run. The Judge node(s)' and the Human "
                "Annotations Node's item ids never overlapped — check both sides' "
                "project/use_case/item-id filters produce the same item id space."
            )
        elif not ctx.dry_run and items and not any(
            dim_stats["n"] > 0 for dim_stats in report["per_dimension"].values()
        ):
            # Real item-id overlap, but every dimension still ended up with n == 0 —
            # build_aligned_rows silently skips a row for several distinct reasons (see
            # diagnose_missing_rows' docstring), none of which is otherwise visible; this
            # is exactly the "why is the Eval tab empty" case a live run can hit even with
            # a correctly-overlapping item space.
            meta["diagnostics"] = diagnose_missing_rows(items, labels, judge_result)
        return NodeRunResult(outputs={"metrics_report": report}, meta=meta)
