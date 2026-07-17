"""Shared concurrent-debate engine for the ``cl_adversarial`` node.

Mirrors ``node_vejudge._concurrent_judging``'s shape (checkpointing, per-item progress
events, streaming batch-eval semantics) but drives a bounded judge-vs-human-proxy
debate per item instead of a single judge call. The anchor score for each item comes
from an upstream Judge node's already-computed result (``anchors``), never recomputed
here.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any, Optional

from ...core.calibration.debate import DebateConfig, DebateRunner, to_calibrated_result
from ...lm_engine.lm_template import LMEngine
from ..server.registry import NodeRunContext


def _calibrate_one(
    original_output: dict[str, Any],
    judge_engine: LMEngine,
    human_engine: LMEngine,
    config: DebateConfig,
    sample: dict[str, Any],
    human_ctx: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    metric_id = original_output["metric_id"]
    # Per-item anchor score (mirrors how metric_id is already resolved per item, not
    # once for the whole run) — dataclasses.replace() so the caller's shared `config`
    # object is never mutated across items.
    item_config = replace(config, human_anchor_score=(human_ctx or {}).get("anchor_score"))
    debater = DebateRunner(
        metric_id=metric_id, judge_engine=judge_engine, proxy_engine=human_engine, config=item_config,
    )
    verdict = debater.run(sample, original_output)
    result = to_calibrated_result(verdict).to_dict()

    # Merged in HERE, before the caller's checkpoint.put() — not in a post-loop after
    # run_concurrent_debates returns, which is what caused the checkpoint-ordering bug:
    # ctx.checkpoint.put() serializes to disk immediately, so anything added to this
    # dict afterward (even though it mutates the same in-memory object, masking the bug
    # within one process) never reaches the persisted judge_results.jsonl, and is lost
    # on --continue / a server restart.
    human_scores: dict[str, dict[str, Any]] = (human_ctx or {}).get("human_scores") or {}
    final_score = result.get("final_score")
    result["human_scores"] = human_scores
    result["human_gap"] = {
        dim: (
            abs(final_score - info["score"])
            if final_score is not None and info.get("score") is not None
            else None
        )
        for dim, info in human_scores.items()
    }
    return result


def run_concurrent_debates(
    *,
    dataset: dict[str, Any],
    anchors: dict[str, dict[str, Any]],
    judge_engine: LMEngine,
    human_engine: LMEngine,
    config: DebateConfig,
    concurrency: int,
    batch_size: int,
    ctx: NodeRunContext,
    human_context: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Run a bounded debate over every item that has a usable anchor, checkpointing +
    streaming as it goes.

    ``anchors`` is ``{item_id: judge_dict}`` — the caller's already-filtered map of
    items with a usable (non-skipped, non-errored, parsed) upstream judge result; only
    these items are candidates. ``human_context`` (optional), if given, is
    ``{item_id: {"human_scores": {dim: {"score": float|None, "n": int}}, "anchor_score":
    float|None}}`` — precomputed by the caller (which owns the metric->human-dimension
    mapping) and merged into each item's result before it's checkpointed. Returns
    ``(per_item, meta)``; ``per_item`` is ``{item_id: CalibratedResult_dict}``.
    """
    per_item: dict[str, dict[str, Any]] = {}
    tasks: list[str] = []
    for item_id in anchors:
        ckpt_key = f"{item_id}::calibration::{anchors[item_id]['metric_id']}"
        if ctx.checkpoint.has(ckpt_key):
            per_item[item_id] = ctx.checkpoint.get(ckpt_key)
            continue
        tasks.append(item_id)

    if ctx.progress_cb:
        ctx.progress_cb("calibration_progress_init", {"total": len(tasks)})

    item_timings: list[dict[str, Any]] = []

    def _run_task(item_id: str) -> tuple[str, dict[str, Any], float]:
        if ctx.progress_cb:
            ctx.progress_cb("calibration_item_start", {"item_id": item_id})
        t0 = time.perf_counter()
        result = _calibrate_one(
            anchors[item_id], judge_engine, human_engine, config, dataset[item_id],
            human_ctx=(human_context or {}).get(item_id),
        )
        return item_id, result, round((time.perf_counter() - t0) * 1000, 1)

    stopped = False
    newly_complete_count = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_run_task, i) for i in tasks]
        for fut in as_completed(futs):
            if fut.cancelled():
                continue
            item_id, result, ms = fut.result()
            per_item[item_id] = result
            item_timings.append({"item_id": item_id, "ms": ms})
            # Only persist a clean end-state so a total-failure item retries on --continue
            # (matches _concurrent_judging.py's "only persist success" convention).
            if "all_turns_failed" not in (result.get("flags") or []):
                ckpt_key = f"{item_id}::calibration::{anchors[item_id]['metric_id']}"
                ctx.checkpoint.put(ckpt_key, result)
            if ctx.progress_cb:
                ctx.progress_cb("calibration_item_done", {"item_id": item_id})

            newly_complete_count += 1
            if ctx.on_batch and newly_complete_count % batch_size == 0:
                ctx.on_batch("calibration_results", dict(per_item))

            if ctx.should_stop and ctx.should_stop() and not stopped:
                stopped = True
                for f in futs:
                    if not f.done():
                        f.cancel()

    meta: dict[str, Any] = {"n_items": len(anchors)}
    if item_timings:
        meta["item_timings"] = item_timings
    if stopped:
        meta["stopped"] = True
        meta["n_items_done"] = len(per_item)
        meta["n_items_total"] = len(anchors)
    return per_item, meta
