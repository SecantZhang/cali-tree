"""Calibration Adversarial Node — a bounded judge-vs-human-proxy debate over a dataset.

Produces a per-item ``CalibratedResult`` (see
``core.calibration.debate.calibrated_result``): each item's own debate transcript,
distilled reasoning, and an ``optimized_prompt`` addendum a downstream Judge Node can
inject (via its optional ``calibration`` input) to re-score *that same item* with the
debate's own feedback in view. This node computes its own anchor judge score per item —
there is no upstream Judge node in this wiring.
"""

from __future__ import annotations

from typing import Any

from ...core.calibration.debate import DebateConfig
from ...core.judge.registry import ALL_JUDGES
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


@register
class ClAdversarialNodeExecutor(NodeExecutor):
    node_type = "cl_adversarial"
    category = "node_calibration"
    input_sockets = {
        "samples": "samples",
        "labels": "labels",
        "judge_engine": "engine_config",
        "human_engine": "engine_config",
    }
    output_sockets = {"calibration_results": "calibration_results"}
    param_schema = {
        "metric_id": {"type": "enum", "options": ALL_JUDGES, "default": "M4"},
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
    supports_partial_input = True

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        dataset = ctx.inputs.get("samples")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Calibration Node requires a 'samples' input (wire a Dataset Node's "
                "`samples` output)",
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

        metric_id = p.get("metric_id") or "M4"
        if metric_id not in JUDGE_METRICS:
            return NodeRunResult(status="error", error=f"Unknown metric '{metric_id}'")
        modality = JUDGE_METRICS[metric_id].modality

        max_rounds = max(1, int(p.get("max_rounds") or 4))
        config = DebateConfig(
            epsilon=float(p.get("epsilon")) if p.get("epsilon") is not None else 0.25,
            max_rounds=max_rounds,
            retrieval_enabled=bool(p.get("retrieval_enabled", True)),
        )

        if ctx.dry_run:
            # 1 anchor judge call + up to max_rounds*2 debate turns, per item.
            calls_per_item = 1 + max_rounds * 2
            return NodeRunResult(
                outputs={"calibration_results": {}},
                meta={
                    "dry_run": True,
                    "n_items": len(dataset),
                    "metric_id": metric_id,
                    "estimated_calls": {"max_calls": len(dataset) * calls_per_item},
                },
            )

        try:
            require_live(
                ctx.allow_live,
                context=f"Calibration Node '{metric_id}' over {len(dataset)} item(s)",
            )
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

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
            metric_id=metric_id,
            judge_engine=judge_engine,
            human_engine=human_engine,
            config=config,
            concurrency=concurrency,
            batch_size=max(1, int(p.get("batch_size") or 1)),
            ctx=ctx,
        )

        override = p.get("human_dimension_override") or None
        dims = [override] if override else _DIMENSIONS_FOR_METRIC.get(metric_id, [])
        for item_id, result in per_item.items():
            agg = labels.get(item_id) if labels else None
            result["human_scores"] = (
                {d: agg.scores.get(d) for d in dims} if agg and dims else {}
            )

        meta["metric_id"] = metric_id
        return NodeRunResult(outputs={"calibration_results": per_item}, meta=meta)
