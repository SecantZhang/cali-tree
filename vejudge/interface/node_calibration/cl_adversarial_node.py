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

from statistics import mean
from typing import Any, Optional

from ...core.calibration.debate import DebateConfig, render_corpus_calibration_prompt
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS, AggregatedHumanRecord
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ...postprocessing.align import ALIGNMENT
from ..server.registry import NodeRunContext, NodeRunResult, register
from ._concurrent_debate import run_concurrent_debates
from ._templates import CalibrationProducerNode

# Modality-appropriate engine default for the judge role (mirrors judge_node.py). The
# human-proxy role is always plain text regardless of metric modality — debate turns
# never attach video media (see core.calibration.debate.runner.DebateTurnRunner).
_DEFAULT_ENGINE_KIND = {"text": "gpt", "video": "gemini"}

# M1 (Assembly Failure) and M2 (Render Failure) are binary pass/fail gates — their judge
# prompts (core.prompts.m1_assembly_failure / m2_render_failure) return a `failure`/
# `severity` verdict, never a `score_1_to_5`. The debate mechanism (core.prompts.
# d1_judge_debate / d2_human_proxy_debate) is built entirely around revising a numeric
# score, so these two metrics can never produce a usable anchor — checked explicitly so
# that shows up as a clear error, not "no usable anchor" once every item's entry is
# filtered out downstream for the same underlying reason.
_SCORE_BASED_METRICS = {"M3", "M4", "M5", "M6"}

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


def _resolve_human_context(
    agg: Optional[AggregatedHumanRecord], dims: list[str],
) -> dict[str, Any]:
    """Per-item human comparison data: the raw per-dimension scores (with rater count,
    for reliability — n=1 is weaker evidence than n=3-4) plus a single collapsed
    ``anchor_score`` used both for the always-on ``human_gap`` and as the optional
    grounded-debate target.

    The anchor is a **rater-count-weighted** mean over whichever mapped dimensions have
    data: a dimension rated by more annotators contributes proportionally more, so a
    flimsy n=1 dimension doesn't sway the target as much as a solid n=6 one. Weighting
    by the ``n`` already carried in ``score_counts`` needs no invented per-dimension
    weights, and it's the natural estimate of "the humans' overall score" for a holistic
    metric like M5 whose single judge score maps to several human facets at once. The
    per-dimension breakdown is preserved separately in ``human_scores``/``human_gap`` so
    the collapse never hides a per-aspect miss.

    Gating on ``score is not None`` (not ``n > 0``) matches ``AggregatedHumanRecord``'s
    own invariant that a dimension's score is None iff its rater count is 0 — no
    dependency on every caller populating score_counts correctly.
    """
    if not agg or not dims:
        return {"human_scores": {}, "anchor_score": None}
    human_scores = {d: {"score": agg.scores.get(d), "n": agg.score_counts.get(d, 0)} for d in dims}
    contributing = [
        (v["score"], v["n"]) for v in human_scores.values() if v["score"] is not None
    ]
    total_weight = sum(n for _score, n in contributing)
    if total_weight > 0:
        anchor_score = sum(score * n for score, n in contributing) / total_weight
    elif contributing:
        # Defensive: scores present but every n == 0 (shouldn't happen given the
        # aggregate invariant above) — fall back to an unweighted mean rather than
        # divide by zero.
        anchor_score = mean(score for score, _n in contributing)
    else:
        anchor_score = None
    return {"human_scores": human_scores, "anchor_score": anchor_score}


@register
class ClAdversarialNodeExecutor(CalibrationProducerNode):
    # Agent Calibration role — inherits the producer I/O contract (samples + judge_result +
    # labels + judge/human engines -> calibration_results + general_calibration) from
    # CalibrationProducerNode; see node_calibration._templates.
    node_type = "cl_adversarial"
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
        # Opt-in: when a real human aggregate score exists for an item, the debate's
        # own convergence requires closing the gap to it, not just self-stability —
        # see core.calibration.debate.runner.DebateRunner.run. Off by default: this
        # changes what the debate optimizes for, so it must be a deliberate choice,
        # not a silent default. An item with no usable human anchor falls back to
        # today's blind behavior automatically, regardless of this setting.
        "ground_in_human_labels": {"type": "boolean", "default": False},
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
            ground_in_human_labels=bool(p.get("ground_in_human_labels", False)),
        )

        if ctx.dry_run:
            # Up to max_rounds*2 debate turns per item — no anchor call, that's the
            # upstream Judge node's cost, already paid (or estimated) there.
            calls_per_item = max_rounds * 2
            return NodeRunResult(
                outputs={"calibration_results": {}, "general_calibration": ""},
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
        # `set(judge_result) & set(labels)` pattern).
        overlap = sorted(set(dataset) & set(judge_result))

        # The metric being calibrated is a property of the *wired judge_spec*, not of any
        # one item — checked against the first entry we can find regardless of that
        # item's own skip/error status, so a structural incompatibility (wrong node type
        # wired, or a metric with no numeric score) gets its own clear error instead of
        # being swallowed into "no usable anchor" once every item's entry is filtered out
        # below for the same underlying reason.
        metric_id = None
        for item_id in overlap:
            entry_dict = judge_result[item_id]
            if entry_dict:
                metric_id = next(iter(entry_dict.values())).get("metric_id")
                break
        if metric_id is not None and metric_id not in JUDGE_METRICS:
            return NodeRunResult(
                status="error",
                error="Calibration Node only supports builtin M1-M6 judge results today; "
                f"got metric_id '{metric_id}' from the wired judge_result (likely a "
                "custom Judge Prompt spec).",
            )
        if metric_id is not None and metric_id not in _SCORE_BASED_METRICS:
            return NodeRunResult(
                status="error",
                error=f"Calibration Node only supports score-based judge metrics "
                f"({', '.join(sorted(_SCORE_BASED_METRICS))}); '{metric_id}' "
                f"({JUDGE_METRICS[metric_id].metric}) is a binary pass/fail gate with no "
                "numeric score to calibrate — wire a Judge Node using a score-based "
                "metric instead.",
            )

        # Now drop any item whose single metric-key entry has no usable score
        # (skipped/errored/unparsed) — the metric itself is already confirmed compatible
        # above, so anything excluded here is a genuine per-item anomaly.
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

        # Precomputed BEFORE run_concurrent_debates — not in a post-loop after it
        # returns, which is what caused the checkpoint-ordering bug (the post-loop's
        # result was mutated in place after _concurrent_debate.py had already
        # checkpointed the same dict to disk). Dimension resolution
        # (_DIMENSIONS_FOR_METRIC/human_dimension_override) stays this node's own
        # concern — _concurrent_debate.py/runner.py remain dimension-agnostic, dealing
        # only in one opaque score_1_to_5 (or its collapsed anchor_score here).
        override = p.get("human_dimension_override") or None
        human_context: dict[str, dict[str, Any]] = {}
        for item_id, entry in anchors.items():
            dims = [override] if override else _DIMENSIONS_FOR_METRIC.get(entry["metric_id"], [])
            agg = labels.get(item_id) if labels else None
            human_context[item_id] = _resolve_human_context(agg, dims)

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
            human_context=human_context,
        )

        meta["n_items_no_judge_result"] = n_no_judge_result
        meta["n_items_unusable_anchor"] = n_unusable_anchor
        # One item-independent calibration note distilling the failure modes that recur
        # across this run's items — the generalizing artifact, meant to be applied to
        # *unseen* items (unlike each per-item optimized_prompt, which re-judges its own
        # item). Surfaced in meta rather than as a socket for now; a downstream Judge
        # could inject it dataset-wide instead of per-item.
        general = render_corpus_calibration_prompt(per_item.values())
        meta["general_optimized_prompt"] = general  # kept in meta for the secondary tab
        return NodeRunResult(
            outputs={"calibration_results": per_item, "general_calibration": general},
            meta=meta,
        )
