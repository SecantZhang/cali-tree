"""Judge Node executor — runs M1-M6 over a ``dataset`` input.

Per ``interface.md``, the (out-of-scope-for-this-branch) "LM Engine Node" configuration
is folded directly into this node's own params: a text-engine group and a video-engine
group, mirroring ``HumanGapBenchmark``'s ``text_engine_kind/video_engine_kind/
text_model/video_model/temperature`` fields.
"""

from __future__ import annotations

from typing import Any

from ...core.judge.registry import ALL_JUDGES, JUDGE_MODALITY
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ...workflow import JudgeEngines, run_judges_for_sample
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class JudgeNodeExecutor(NodeExecutor):
    node_type = "judge"
    category = "node_vejudge"
    input_sockets = {"dataset": "dataset"}
    output_sockets = {"judge_result": "judge_result"}
    param_schema = {
        "metrics": {"type": "list[enum]", "options": list(ALL_JUDGES), "default": None},
        "skip_video": {"type": "bool", "default": False},
        "text_engine_kind": {"type": "enum", "options": ["gpt", "qwen"], "default": "gpt"},
        "text_model": {"type": "string", "default": None},
        "video_engine_kind": {"type": "enum", "options": ["gemini"], "default": "gemini"},
        "video_model": {"type": "string", "default": None},
        "temperature": {"type": "number", "default": None},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        dataset = ctx.inputs.get("dataset")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Judge Node requires a 'dataset' input (wire a Dataset Node's "
                "`dataset` output, not `labels`)",
            )

        metrics = p.get("metrics") or list(ALL_JUDGES)
        unknown = [m for m in metrics if m not in JUDGE_MODALITY]
        if unknown:
            return NodeRunResult(status="error", error=f"Unknown metric id(s): {unknown}")

        if ctx.dry_run:
            return _dry_run_result(dataset, metrics)

        try:
            require_live(ctx.allow_live, context=f"Judge Node over {len(dataset)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        temp_kw: dict[str, Any] = {} if p.get("temperature") is None else {
            "temperature": p["temperature"]
        }
        creds = load_creds()
        engines = JudgeEngines(
            text=get_engine(
                p.get("text_engine_kind", "gpt"), history=ctx.run.history,
                model=p.get("text_model"), creds=creds, **temp_kw,
            ),
            video=get_engine(
                p.get("video_engine_kind", "gemini"), history=ctx.run.history,
                model=p.get("video_model"), creds=creds, **temp_kw,
            ),
        )
        skip_video = bool(p.get("skip_video", False))

        # Pre-pass: split cached vs. pending per item, and compute the true total number
        # of (item, metric) calls that will actually fire this run (excluding metrics
        # run_judges_for_sample will itself skip: video modality with skip_video or no
        # output_video_path) — that total drives the progress bar, so it must match
        # exactly what will trigger a "judge_metric" event below.
        cached_by_item: dict[str, dict[str, Any]] = {}
        pending_by_item: dict[str, list[str]] = {}
        total = 0
        for item_id, sample in dataset.items():
            cached = {
                mid: ctx.checkpoint.get(f"{item_id}::{mid}")
                for mid in metrics
                if ctx.checkpoint.has(f"{item_id}::{mid}")
            }
            pending = [mid for mid in metrics if mid not in cached]
            cached_by_item[item_id] = cached
            pending_by_item[item_id] = pending
            has_video = bool((sample.get("output") or {}).get("output_video_path"))
            total += sum(
                1 for mid in pending
                if not (JUDGE_MODALITY[mid] == "video" and (skip_video or not has_video))
            )
        if ctx.progress_cb:
            ctx.progress_cb("judge_progress_init", {"total": total})

        per_item: dict[str, dict[str, Any]] = {}
        for item_id, sample in dataset.items():
            cached = cached_by_item[item_id]
            pending = pending_by_item[item_id]
            new_results: dict[str, Any] = {}
            if pending:
                if ctx.progress_cb:
                    ctx.progress_cb("judge_item_start", {"item_id": item_id})
                new_results = run_judges_for_sample(
                    sample, engines, judges=pending, skip_video=skip_video,
                    logger=ctx.run.logger,
                    progress_cb=lambda mid, _iid=item_id: ctx.progress_cb(
                        "judge_metric", {"item_id": _iid, "metric_id": mid}
                    ) if ctx.progress_cb else None,
                )
                for mid, res in new_results.items():
                    if not res.get("error") and not res.get("skipped"):
                        ctx.checkpoint.put(f"{item_id}::{mid}", res)
            per_item[item_id] = {**cached, **new_results}

        return NodeRunResult(
            outputs={"judge_result": per_item}, meta={"n_items": len(dataset)}
        )


def _dry_run_result(dataset: dict[str, Any], metrics: list[str]) -> NodeRunResult:
    video_calls = sum(1 for m in metrics if JUDGE_MODALITY[m] == "video")
    text_calls = len(metrics) - video_calls
    n_items = len(dataset)
    return NodeRunResult(
        outputs={"judge_result": {}},
        meta={
            "dry_run": True,
            "n_items": n_items,
            "estimated_calls": {
                "video_judge_calls": video_calls * n_items,
                "text_judge_calls": text_calls * n_items,
            },
        },
    )
