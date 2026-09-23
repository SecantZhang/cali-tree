"""Shared concurrent-judging engine for the generic Judge node.

Runs one ``judge_spec`` (a single metric/prompt) across every item through a
``ThreadPoolExecutor``, with checkpointing, per-item progress events, and streaming
batch-eval (`ctx.on_batch`) semantics. Cross-metric parallelism now lives *across* sibling
Judge nodes (one spec each) rather than inside a single node's item×metric loop — each node
still parallelizes across items here.

Builtin specs delegate to the existing ``core.judge.Judge`` (via ``make_judge``); custom
specs run through ``judge_spec.run_custom_judge``. Either way one judge result dict per item
is filed under ``spec_key(spec)``.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from ...core.judge.registry import make_judge
from ...lm_engine.lm_template import LMEngine
from ..server.registry import NodeRunContext
from .judge_spec import run_custom_judge, spec_key, spec_modality


def _judge_one(
    spec: dict[str, Any],
    engine: LMEngine,
    sample: dict[str, Any],
    *,
    extra_context: Optional[str] = None,
) -> dict[str, Any]:
    if spec.get("kind") == "builtin":
        return make_judge(spec["metric_id"], engine).run(sample, extra_context=extra_context)
    return run_custom_judge(spec, engine, sample)


def run_concurrent_judging(
    *,
    dataset: dict[str, Any],
    spec: dict[str, Any],
    engine: LMEngine,
    concurrency: int,
    batch_size: int,
    ctx: NodeRunContext,
    should_skip: Optional[Callable[[dict[str, Any]], bool]] = None,
    calibration: Optional[dict[str, dict[str, Any]]] = None,
    general_calibration: Optional[str] = None,
    judge_provenance: Optional[dict[str, Any]] = None,
    checkpoint_variant: Optional[str] = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Run ``spec`` over every item, checkpointing + streaming as it goes.

    ``should_skip(sample)`` (optional) marks an item as skipped-without-calling (e.g. the
    "no rendered video for this item" gate for a video-modality spec) rather than submitting
    it. Returns ``(per_item, meta)``; ``per_item`` is ``{item_id: {metric_key: judge_dict}}``
    so it stays shape-compatible with the multi-metric result Eval already consumes.

    ``calibration`` (optional), if given, is a ``cl_adversarial`` node's
    ``calibration_results`` output (``{item_id: CalibratedResult_dict}``) — each item's own
    ``optimized_prompt`` is looked up and passed through as ``extra_context`` for *that
    item's* builtin judge call.

    ``general_calibration`` (optional) is a single item-independent calibration note (a
    ``cl_adversarial`` node's ``general_calibration`` output — the corpus prompt) applied
    to *every* item's ``extra_context``. When both are given they're concatenated (the
    general note first, then the item's own).
    """
    key = spec_key(spec)
    # Prefixed with the node id, not just item_id+metric: two Judge nodes can legitimately
    # run the identical judge_spec over the identical items in one graph (e.g. a baseline
    # Judge feeding an Adversarial Calibration node, and a second Judge with `calibration`
    # wired to compare against) — a shared run-wide CheckpointStore keyed only by
    # item_id+metric would let the second node silently reuse the first's cached
    # (uncalibrated) result and never actually apply its own extra_context.
    ckpt_prefix = f"{ctx.node_id}::{checkpoint_variant}::" if checkpoint_variant else f"{ctx.node_id}::"
    per_item: dict[str, dict[str, Any]] = {iid: {} for iid in dataset}
    tasks: list[str] = []
    for item_id, sample in dataset.items():
        ckpt_key = f"{ckpt_prefix}{item_id}::{key}"
        if ctx.checkpoint.has(ckpt_key):
            per_item[item_id][key] = ctx.checkpoint.get(ckpt_key)
            continue
        if should_skip and should_skip(sample):
            per_item[item_id][key] = {
                "judge": key, "metric_id": key, "parsed": None, "skipped": True,
            }
            continue
        tasks.append(item_id)

    if ctx.progress_cb:
        ctx.progress_cb("judge_progress_init", {"total": len(tasks)})

    item_timings: list[dict[str, Any]] = []

    def _run_task(item_id: str) -> tuple[str, dict[str, Any], float]:
        if ctx.progress_cb:
            ctx.progress_cb("judge_item_start", {"item_id": item_id})
        per_item_ctx = (calibration or {}).get(item_id, {}).get("optimized_prompt")
        # General (dataset-wide) note first, then this item's own — either may be absent.
        parts = [p for p in (general_calibration, per_item_ctx) if p]
        extra_context = "\n\n".join(parts) if parts else None
        t0 = time.perf_counter()
        result = _judge_one(spec, engine, dataset[item_id], extra_context=extra_context)
        result["judge_provenance"] = dict(judge_provenance or {})
        return item_id, result, round((time.perf_counter() - t0) * 1000, 1)

    stopped = False
    newly_complete_count = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_run_task, i) for i in tasks]
        for fut in as_completed(futs):
            if fut.cancelled():
                continue
            item_id, result, ms = fut.result()
            per_item[item_id][key] = result
            item_timings.append({"item_id": item_id, "ms": ms})
            if not result.get("error") and not result.get("skipped"):
                ctx.checkpoint.put(f"{ckpt_prefix}{item_id}::{key}", result)
            if ctx.progress_cb:
                ctx.progress_cb("judge_metric", {"item_id": item_id, "metric_id": key})

            # One spec per node → an item is "complete" as soon as its single result lands.
            # The snapshot only contains items actually judged so far — Eval aligns on key
            # presence, so a not-yet-judged placeholder would overstate the aligned count.
            newly_complete_count += 1
            if ctx.on_batch and newly_complete_count % batch_size == 0:
                snapshot = {iid: dict(m) for iid, m in per_item.items() if m}
                ctx.on_batch("judge_result", snapshot)

            # Graceful stop: let in-flight tasks finish + checkpoint; cancel anything queued.
            if ctx.should_stop and ctx.should_stop() and not stopped:
                stopped = True
                for f in futs:
                    if not f.done():
                        f.cancel()

    meta: dict[str, Any] = {"n_items": len(dataset)}
    if item_timings:
        meta["item_timings"] = item_timings
    if stopped:
        n_done = sum(1 for item in per_item.values() if item)
        meta["stopped"] = True
        meta["n_items_done"] = n_done
        meta["n_items_total"] = len(dataset)

    return per_item, meta
