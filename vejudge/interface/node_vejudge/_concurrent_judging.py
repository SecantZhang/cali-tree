"""Shared concurrent-judging engine for the Text/Video Judge node executors.

Both nodes run (item, metric) calls through one `ThreadPoolExecutor` against their own
single engine, with identical checkpointing, per-item progress events, and streaming
batch-eval (`ctx.on_batch`) semantics — only the metric list, engine, concurrency knob,
and (optionally) a per-(metric, sample) skip gate differ per caller. Ported from the old
single Judge Node's dual-pool implementation (`benchmark/human_gap/runner.py`'s
`_run_judges_concurrent` has the same shape); with the text/video split, each caller only
ever needs one pool, not two run side by side.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from ...core.judge.registry import make_judge
from ...lm_engine.lm_template import LMEngine
from ..server.registry import NodeRunContext


def run_concurrent_judging(
    *,
    dataset: dict[str, Any],
    metrics: list[str],
    engine: LMEngine,
    concurrency: int,
    batch_size: int,
    ctx: NodeRunContext,
    should_skip: Optional[Callable[[str, dict[str, Any]], bool]] = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Runs every (item, metric) pair, checkpointing + streaming as it goes.

    ``should_skip(metric_id, sample)`` (optional) marks a pair as skipped-without-calling
    (e.g. the Video Judge Node's "no rendered video for this item" gate) rather than
    submitting it as a task. Returns ``(per_item, meta)`` — the same shape the caller
    builds its `NodeRunResult` from directly.
    """
    per_item: dict[str, dict[str, Any]] = {iid: {} for iid in dataset}
    tasks: list[tuple[str, str]] = []
    for item_id, sample in dataset.items():
        for mid in metrics:
            key = f"{item_id}::{mid}"
            if ctx.checkpoint.has(key):
                per_item[item_id][mid] = ctx.checkpoint.get(key)
                continue
            if should_skip and should_skip(mid, sample):
                per_item[item_id][mid] = {
                    "judge": mid, "metric_id": mid, "parsed": None, "skipped": True,
                }
                continue
            tasks.append((item_id, mid))

    if ctx.progress_cb:
        ctx.progress_cb("judge_progress_init", {"total": len(tasks)})

    started_items: set[str] = set()
    started_lock = threading.Lock()

    def _emit_item_start(item_id: str) -> None:
        # Under concurrency, several items can have tasks in flight at once — this fires
        # once per item, the moment a worker actually picks up its first task (not at
        # submission time, when every item's tasks get queued up front).
        with started_lock:
            if item_id in started_items:
                return
            started_items.add(item_id)
        if ctx.progress_cb:
            ctx.progress_cb("judge_item_start", {"item_id": item_id})

    def _run_task(item_id: str, metric_id: str) -> tuple[str, str, dict[str, Any]]:
        _emit_item_start(item_id)
        judge = make_judge(metric_id, engine)
        return item_id, metric_id, judge.run(dataset[item_id])

    stopped = False
    newly_complete_count = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_run_task, i, m) for i, m in tasks]
        for fut in as_completed(futs):
            if fut.cancelled():
                continue
            item_id, metric_id, result = fut.result()
            per_item[item_id][metric_id] = result
            if not result.get("error") and not result.get("skipped"):
                ctx.checkpoint.put(f"{item_id}::{metric_id}", result)
            if ctx.progress_cb:
                ctx.progress_cb(
                    "judge_metric", {"item_id": item_id, "metric_id": metric_id}
                )

            # Batch membership is a function of *completion* order, not submission order
            # — under concurrency, items can finish their last pending metric in any
            # order, so the Nth item to reach `len(metrics)` here is the Nth item counted.
            # The snapshot only contains items that are actually fully judged so far — Eval
            # Node aligns purely on key presence, so including a not-yet-judged placeholder
            # would make every preview claim more items are aligned than really are.
            if len(per_item[item_id]) == len(metrics):
                newly_complete_count += 1
                if ctx.on_batch and newly_complete_count % batch_size == 0:
                    snapshot = {
                        iid: dict(m) for iid, m in per_item.items() if len(m) == len(metrics)
                    }
                    ctx.on_batch("judge_result", snapshot)

            # Graceful stop: let anything already picked up by a worker finish and get
            # checkpointed; anything still queued is cancelled outright. Missing (item,
            # metric) pairs simply show up as "pending" again on Resume.
            if ctx.should_stop and ctx.should_stop() and not stopped:
                stopped = True
                for f in futs:
                    if not f.done():
                        f.cancel()

    meta: dict[str, Any] = {"n_items": len(dataset)}
    if stopped:
        n_done = sum(1 for item in per_item.values() if len(item) == len(metrics))
        meta["stopped"] = True
        meta["n_items_done"] = n_done
        meta["n_items_total"] = len(dataset)

    return per_item, meta
