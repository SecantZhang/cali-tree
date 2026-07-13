"""Calibration Adversarial Node — a bounded judge-vs-human-proxy debate over a dataset.

Produces a per-item ``CalibratedResult`` (see
``core.calibration.debate.calibrated_result``): each item's own debate transcript,
distilled reasoning, and an ``optimized_prompt`` addendum a downstream Judge Node can
inject (via its optional ``calibration`` input) to re-score *that same item* with the
debate's own feedback in view. The anchor score comes from an upstream Judge Node's
``judge_result`` — this node never computes its own; wiring is
`Judge (baseline) -> Adversarial Calibration -> Judge (calibrated)`.
"""

from __future__ import annotations

from typing import Any

from ...core.calibration.debate import DebateConfig
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ...postprocessing.align import ALIGNMENT
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from ._concurrent_debate import run_concurrent_debates

# Modality-appropriate engine default for the judge role (mirrors judge_node.py). The
# human-proxy role is always plain text regardless of metric modality — debate turns
# never attach video media (see core.calibration.debate.runner.DebateTurnRunner).
_DEFAULT_ENGINE_KIND = {"text": "gpt", "video": "gemini"}

# Reverse of postprocessing.align.ALIGNMENT: metric_id -> human dimensions it maps to.
# M1/M2/M4 have no entry (no human dimension directly measures them) — the node surfaces
# that explicitly rather than guessing, unless human_dimension_override is set.
_DIMENSIONS_FOR_METRIC: dict[str, list[str]] = {}
for _dim, (_mid, _extractor) in ALIGNMENT.items():
    _DIMENSIONS_FOR_METRIC.setdefault(_mid, []).append(_dim)


def _usable_anchor(entry: dict[str, Any]) -> bool:
    if not entry or entry.get("skipped") or entry.get("error") or not entry.get("parsed"):
        return False
    # `parsed` can be a non-empty dict that's still missing the actual score key (e.g. a
    # judge response that validated but didn't carry a numeric score) — extract_original_
    # score() already tolerates that by returning None, but a None anchor score later
    # crashes calibrated_result.py's formatting. Exclude it here instead, same as any
    # other unusable anchor, rather than let a doomed debate spend real LM calls on it.
    parsed = entry["parsed"]
    metric_id = entry.get("metric_id")
    score_key = "overall_av_sync_score" if metric_id == "M6" else "score_1_to_5"
    score = parsed.get(score_key)
    return isinstance(score, (int, float)) and not isinstance(score, bool)


@register
class ClAdversarialNodeExecutor(NodeExecutor):
    node_type = "cl_adversarial"
    category = "node_calibration"
    input_sockets = {
        "samples": "samples",
        "judge_result": "judge_result",
        "labels": "labels",
        "judge_engine": "engine_config",
        "human_engine": "engine_config",
    }
    output_sockets = {"calibration_results": "calibration_results"}
    param_schema = {
        "epsilon": {"type": "number", "default": 0.25},
        "max_rounds": {"type": "number", "default": 4, "min": 1},
        "retrieval_enabled": {"type": "boolean", "default": True},
        "batch_size": {"type": "number", "default": 1, "min": 1},
        # "" (default) = auto-detect via ALIGNMENT; a non-empty value overrides it for
        # metrics (M1/M2/M4) with no direct human-dimension mapping.
        "human_dimension_override": {
            "type": "enum", "options": ["", *HUMAN_DIMENSIONS], "default": "",
        },
    }
    # Deliberately NOT opted into streaming batch-eval previews (see
    # NodeExecutor.supports_partial_input's docstring: "only a node whose run() is cheap
    # and safe to call repeatedly" — only EvalNodeExecutor should set this True). This
    # node's run() drives a real, live, multi-round judge-vs-human-proxy debate, the
    # opposite of cheap. Previously this was left True (inherited unmodified from before
    # this node consumed an upstream judge_result), so every time the upstream Judge node
    # finished one more item and called ctx.on_batch, the executor synchronously re-ran a
    # full, real debate over the in-flight partial judge_result as a "preview" — real,
    # billable LM calls, blocking the Judge node's own run() from returning for the
    # entire span it showed as "running" in the UI, long after its own real work (one
    # anchor call per item) was actually done.

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        dataset = ctx.inputs.get("samples")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Calibration Node requires a 'samples' input (wire a Dataset Node's "
                "`samples` output)",
            )
        judge_result = ctx.inputs.get("judge_result")
        if judge_result is None:
            return NodeRunResult(
                status="error",
                error="Calibration Node requires a 'judge_result' input (wire a Judge "
                "Node's `judge_result` output — this node calibrates an existing judge "
                "score, it doesn't compute its own)",
            )
        judge_engine_config = ctx.inputs.get("judge_engine")
        if judge_engine_config is None:
            return NodeRunResult(
                status="error",
                error="Calibration Node requires a 'judge_engine' input (wire an LM Engine "
                "Node's `engine_config` output)",
            )
        human_engine_config = ctx.inputs.get("human_engine")
        if human_engine_config is None:
            return NodeRunResult(
                status="error",
                error="Calibration Node requires a 'human_engine' input (wire a second LM "
                "Engine Node's `engine_config` output)",
            )
        labels = ctx.inputs.get("labels")  # optional — only used for display/comparison

        max_rounds = max(1, int(p.get("max_rounds") or 4))
        config = DebateConfig(
            epsilon=float(p.get("epsilon")) if p.get("epsilon") is not None else 0.25,
            max_rounds=max_rounds,
            retrieval_enabled=bool(p.get("retrieval_enabled", True)),
        )

        if ctx.dry_run:
            # Up to max_rounds*2 debate turns per item — no anchor call, that's the
            # upstream Judge node's cost, already paid (or estimated) there.
            calls_per_item = max_rounds * 2
            return NodeRunResult(
                outputs={"calibration_results": {}},
                meta={
                    "dry_run": True,
                    "n_items": len(dataset),
                    "estimated_calls": {"max_calls": len(dataset) * calls_per_item},
                },
            )

        try:
            require_live(
                ctx.allow_live,
                context=f"Calibration Node over {len(dataset)} item(s)",
            )
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        # Reconcile samples against the upstream judge_result (mirrors eval_node.py's
        # `set(judge_result) & set(labels)` pattern), then drop any item whose single
        # metric-key entry has no usable score (skipped/errored/unparsed).
        overlap = sorted(set(dataset) & set(judge_result))
        anchors: dict[str, dict[str, Any]] = {}
        for item_id in overlap:
            entry_dict = judge_result[item_id]
            if not entry_dict:
                continue
            # Fan-in is disallowed on this socket, so exactly one metric-key per item.
            entry = next(iter(entry_dict.values()))
            if _usable_anchor(entry):
                anchors[item_id] = entry

        n_no_judge_result = len(dataset) - len(overlap)
        n_unusable_anchor = len(overlap) - len(anchors)

        if not anchors:
            return NodeRunResult(
                status="error",
                error="No usable 'judge_result' entries overlap with 'samples' — "
                f"{n_no_judge_result} item(s) have no judge_result entry at all, "
                f"{n_unusable_anchor} have one but it's skipped/errored/unparsed. Check "
                "the upstream Judge Node actually ran successfully for these items.",
            )

        unsupported = {
            entry["metric_id"] for entry in anchors.values()
            if entry.get("metric_id") not in JUDGE_METRICS
        }
        if unsupported:
            return NodeRunResult(
                status="error",
                error="Calibration Node only supports builtin M1-M6 judge results today; "
                f"got metric_id(s) {sorted(unsupported)} from the wired judge_result "
                "(likely a custom Judge Prompt spec).",
            )

        modality = JUDGE_METRICS[next(iter(anchors.values()))["metric_id"]].modality

        def _build_engine(engine_config: dict[str, Any], default_kind: str):
            temp_kw: dict[str, Any] = {} if engine_config.get("temperature") is None else {
                "temperature": engine_config["temperature"]
            }
            return get_engine(
                engine_config.get("engine_kind") or default_kind,
                history=ctx.run.history,
                model=engine_config.get("model"), creds=load_creds(),
                max_tokens=int(engine_config.get("max_tokens") or 4096), **temp_kw,
            )

        judge_engine = _build_engine(judge_engine_config, _DEFAULT_ENGINE_KIND.get(modality, "gpt"))
        human_engine = _build_engine(human_engine_config, "gpt")

        concurrency = max(1, int(judge_engine_config.get("concurrency") or 1))
        per_item, meta = run_concurrent_debates(
            dataset=dataset,
            anchors=anchors,
            judge_engine=judge_engine,
            human_engine=human_engine,
            config=config,
            concurrency=concurrency,
            batch_size=max(1, int(p.get("batch_size") or 1)),
            ctx=ctx,
        )

        override = p.get("human_dimension_override") or None
        for item_id, result in per_item.items():
            item_metric_id = anchors.get(item_id, {}).get("metric_id") or result.get("metric_id")
            dims = [override] if override else _DIMENSIONS_FOR_METRIC.get(item_metric_id, [])
            agg = labels.get(item_id) if labels else None
            result["human_scores"] = (
                {d: agg.scores.get(d) for d in dims} if agg and dims else {}
            )

        meta["n_items_no_judge_result"] = n_no_judge_result
        meta["n_items_unusable_anchor"] = n_unusable_anchor
        return NodeRunResult(outputs={"calibration_results": per_item}, meta=meta)
