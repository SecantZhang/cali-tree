"""Eval Node executor — human-vs-judge agreement metrics.

Mirrors ``HumanGapBenchmark``'s gap computation, reusing the same shared functions the
CLI benchmark uses (``postprocessing.align.build_aligned_rows``,
``core.eval.report.per_dimension_agreement``) so both compute the gap identically.
Never gated by dry-run/--live — it makes no gateway calls of its own.
"""

from __future__ import annotations

from ...core.eval.report import per_dimension_agreement
from ...postprocessing.align import build_aligned_rows
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class EvalNodeExecutor(NodeExecutor):
    node_type = "eval"
    category = "node_eval"
    input_sockets = {"judge_result": "judge_result", "labels": "labels"}
    output_sockets = {"metrics_report": "metrics_report"}
    param_schema: dict = {}

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
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
                "`labels` output, not `dataset`)",
            )

        items = sorted(set(judge_result) & set(labels))
        rows = build_aligned_rows(items, labels, judge_result)
        report = {
            "n_items": len(items),
            "n_aligned_rows": len(rows),
            "per_dimension": per_dimension_agreement(rows),
        }
        ctx.run.write_json(f"eval_{ctx.node_id}.json", report)
        ctx.run.logger.info(
            "Eval[%s]: %d items, %d aligned rows", ctx.node_id, len(items), len(rows)
        )
        meta: dict[str, object] = {"n_items": len(items)}
        # A dry run's Judge Node produces no judge_result rows by design, so 0 items here
        # is expected and not worth flagging — only warn when a *live* run aligned nothing,
        # which usually means the Judge and human-label item ids never actually overlapped.
        if not ctx.dry_run and len(items) == 0:
            meta["warning"] = (
                "0 aligned items on a live run. The Judge Node's and the labels Dataset "
                "Node's item ids never overlapped — check both nodes' loader/project "
                "filters produce the same item id space."
            )
        return NodeRunResult(outputs={"metrics_report": report}, meta=meta)
