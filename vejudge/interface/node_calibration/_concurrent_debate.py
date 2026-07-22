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
from threading import Semaphore
from typing import Any, Optional

from ...core.calibration.debate import DebateConfig, DebateRunner, to_calibrated_result
from ...core.calibration.debate.calibrated_result import _TENDENCY
from ...core.calibration.debate.schema import DebateTranscript
from ...core.calibration.debate.semantic_summary import (
    SUMMARY_VERSION,
    llm_summary,
    render_summary,
    rule_based_summary,
)
from ...core.prompts import d1_judge_debate, d2_human_proxy_debate
from ...lm_engine.lm_template import LMEngine
from ..server.registry import NodeRunContext


DEBATE_CHECKPOINT_VERSION = (
    f"d1-{d1_judge_debate.VERSION}-d2-{d2_human_proxy_debate.VERSION}-profile-v1-output-v2"
)


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
    item_config = replace(
        config,
        human_anchor_score=(human_ctx or {}).get("anchor_score"),
        human_raw_scores=(human_ctx or {}).get("raw_anchor_scores"),
    )
    debater = DebateRunner(
        metric_id=metric_id, judge_engine=judge_engine, proxy_engine=human_engine, config=item_config,
    )
    verdict = debater.run(sample, original_output)
    result = to_calibrated_result(verdict).to_dict()
    score_field = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
    result["score_provenance"] = {
        "metric_id": metric_id,
        "parsed_field": score_field,
        "raw_value": ((original_output.get("parsed") or {}).get(score_field)),
        "model": original_output.get("model"),
        "aggregation": (
            "mean_temperature_variants" if original_output.get("judge_variants") else "none"
        ),
        "judge_provenance": dict(original_output.get("judge_provenance") or {}),
    }
    result["judge_provenance"] = dict(original_output.get("judge_provenance") or {})
    result["judge_variants"] = list(original_output.get("judge_variants") or [])

    # Merged in HERE, before the caller's checkpoint.put() — not in a post-loop after
    # run_concurrent_debates returns, which is what caused the checkpoint-ordering bug:
    # ctx.checkpoint.put() serializes to disk immediately, so anything added to this
    # dict afterward (even though it mutates the same in-memory object, masking the bug
    # within one process) never reaches the persisted judge_results.jsonl, and is lost
    # on --continue / a server restart.
    human_scores: dict[str, dict[str, Any]] = (human_ctx or {}).get("human_scores") or {}
    final_score = result.get("final_score")
    result["human_scores"] = human_scores
    result["human_disagreement_profile"] = dict(
        result.get("human_disagreement_profile") or {}
    )
    result["human_gap"] = {}
    for dim, info in human_scores.items():
        if final_score is None:
            result["human_gap"][dim] = None
        elif info.get("score") is not None:
            result["human_gap"][dim] = abs(final_score - info["score"])
        elif info.get("scores"):
            result["human_gap"][dim] = [abs(final_score - s) for s in info["scores"]]
        else:
            result["human_gap"][dim] = None
    return result


def run_concurrent_debates(
    *,
    dataset: dict[str, Any],
    anchors: dict[str, dict[str, Any]],
    judge_engine: LMEngine,
    human_engine: LMEngine,
    summarizer_engine: Optional[LMEngine],
    use_llm_summarization: bool,
    summarizer_config_hash: str,
    summarizer_concurrency: int,
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
    ``{item_id: {"human_scores": {dim: {"score": float|None, "scores": list[float],
    "n": int}}, "anchor_score": float|None, "raw_anchor_scores": list[float]}}`` —
    precomputed by the caller (which owns the metric->human-dimension
    mapping) and merged into each item's result before it's checkpointed. Returns
    ``(per_item, meta)``; ``per_item`` is ``{item_id: CalibratedResult_dict}``.
    """
    per_item: dict[str, dict[str, Any]] = {}
    tasks = list(anchors)

    if ctx.progress_cb:
        ctx.progress_cb("calibration_progress_init", {"total": len(tasks)})

    item_timings: list[dict[str, Any]] = []

    summary_slots = Semaphore(max(1, summarizer_concurrency))

    def _apply_rule(result: dict[str, Any]) -> dict[str, Any]:
        semantic = rule_based_summary(
            DebateTranscript.from_dict(result["transcript"]),
            dict(result.get("failure_mode_summary") or {}), _TENDENCY,
        )
        return {
            **result,
            "optimized_prompt": render_summary(semantic),
            "semantic_summary": semantic.to_dict(),
            "summary_mode_requested": "rule_based",
            "summary_mode_used": "rule_based",
            "summary_version": SUMMARY_VERSION,
            "summary_error": None,
        }

    def _apply_requested_summary(item_id: str, result: dict[str, Any]) -> dict[str, Any]:
        rule_result = _apply_rule(result)
        if not use_llm_summarization:
            return rule_result
        if "all_turns_failed" in (result.get("flags") or []):
            return {
                **rule_result,
                "summary_mode_requested": "llm",
                "summary_mode_used": "rule_based_fallback",
                "summary_error": "debate_has_no_valid_turns",
            }
        summary_key = (
            f"{ctx.node_id}::{item_id}::calibration::{anchors[item_id]['metric_id']}::"
            f"{anchors[item_id].get('anchor_fingerprint', 'single')}::summary::"
            f"{DEBATE_CHECKPOINT_VERSION}::{SUMMARY_VERSION}::{summarizer_config_hash}"
        )
        if ctx.checkpoint.has(summary_key):
            return {**rule_result, **ctx.checkpoint.get(summary_key)}
        assert summarizer_engine is not None  # validated by the node before live calls
        with summary_slots:
            semantic, error = llm_summary(
                DebateTranscript.from_dict(result["transcript"]), summarizer_engine,
            )
        if semantic is None:
            return {
                **rule_result,
                "summary_mode_requested": "llm",
                "summary_mode_used": "rule_based_fallback",
                "summary_error": error or "unknown_summarizer_failure",
            }
        summary_fields = {
            "optimized_prompt": render_summary(semantic),
            "semantic_summary": semantic.to_dict(),
            "summary_mode_requested": "llm",
            "summary_mode_used": "llm",
            "summary_version": SUMMARY_VERSION,
            "summary_error": None,
        }
        ctx.checkpoint.put(summary_key, summary_fields)
        return {**rule_result, **summary_fields}

    def _run_task(item_id: str) -> tuple[str, dict[str, Any], float]:
        if ctx.progress_cb:
            ctx.progress_cb("calibration_item_start", {"item_id": item_id})
        t0 = time.perf_counter()
        ckpt_key = (
            f"{ctx.node_id}::{item_id}::calibration::{anchors[item_id]['metric_id']}::"
            f"{anchors[item_id].get('anchor_fingerprint', 'single')}::debate::"
            f"{DEBATE_CHECKPOINT_VERSION}"
        )
        if ctx.checkpoint.has(ckpt_key):
            result = ctx.checkpoint.get(ckpt_key)
        else:
            result = _calibrate_one(
                anchors[item_id], judge_engine, human_engine, config, dataset[item_id],
                human_ctx=(human_context or {}).get(item_id),
            )
            if "all_turns_failed" not in (result.get("flags") or []):
                # Base debate checkpoint is independent from the selected summary mode.
                ctx.checkpoint.put(ckpt_key, result)
        if "score_provenance" not in result:
            metric_id = anchors[item_id]["metric_id"]
            score_field = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
            result = {
                **result,
                "score_provenance": {
                    "metric_id": metric_id,
                    "parsed_field": score_field,
                    "raw_value": ((anchors[item_id].get("parsed") or {}).get(score_field)),
                    "model": anchors[item_id].get("model"),
                    "aggregation": (
                        "mean_temperature_variants"
                        if anchors[item_id].get("judge_variants") else "none"
                    ),
                    "judge_provenance": dict(
                        anchors[item_id].get("judge_provenance") or {}
                    ),
                },
                "judge_provenance": dict(anchors[item_id].get("judge_provenance") or {}),
                "judge_variants": list(anchors[item_id].get("judge_variants") or []),
            }
        result = _apply_requested_summary(item_id, result)
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

    meta: dict[str, Any] = {
        "n_items": len(anchors),
        "summary_mode_requested": "llm" if use_llm_summarization else "rule_based",
        "n_summary_fallbacks": sum(
            1 for result in per_item.values()
            if result.get("summary_mode_used") == "rule_based_fallback"
        ),
    }
    if item_timings:
        meta["item_timings"] = item_timings
    if stopped:
        meta["stopped"] = True
        meta["n_items_done"] = len(per_item)
        meta["n_items_total"] = len(anchors)
    return per_item, meta
