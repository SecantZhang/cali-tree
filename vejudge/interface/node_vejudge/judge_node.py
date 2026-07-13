"""Judge Node — the generic judge: ``judge_spec`` + ``engine_config`` + ``samples`` ->
``judge_result``.

Replaces the old modality-split Text/Video Judge nodes: the wired ``judge_spec`` (from a
Judge Prompt node) now carries the metric identity and modality, so one node type covers
both. A builtin spec runs the existing M1-M6 judge; a custom spec runs its free-text prompt
(see ``judge_spec.py`` / ``_concurrent_judging.py``). Modality decides video attachment and
the "no rendered video" skip gate. Each node runs one spec across items (its own
parallelization pool); cross-metric parallelism is across sibling Judge nodes.
"""

from __future__ import annotations

from typing import Any

from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from ._concurrent_judging import run_concurrent_judging
from .judge_spec import spec_key, spec_modality

# Modality-appropriate engine default when the wired engine_config doesn't pin an engine_kind.
_DEFAULT_ENGINE_KIND = {"text": "gpt", "video": "gemini"}


@register
class JudgeNodeExecutor(NodeExecutor):
    node_type = "judge"
    category = "node_vejudge"
    input_sockets = {
        "samples": "samples",
        "engine_config": "engine_config",
        "judge_spec": "judge_spec",
        # Optional: a cl_adversarial node's per-item calibrated results. When wired,
        # each item's own `optimized_prompt` is injected as that item's extra_context
        # (builtin specs only — see _concurrent_judging.py).
        "calibration": "calibration_results",
    }
    output_sockets = {"judge_result": "judge_result"}
    param_schema = {
        "batch_size": {"type": "number", "default": 1, "min": 1},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        dataset = ctx.inputs.get("samples")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Judge Node requires a 'samples' input (wire a Dataset Node's "
                "`samples` output)",
            )
        engine_config = ctx.inputs.get("engine_config")
        if engine_config is None:
            return NodeRunResult(
                status="error",
                error="Judge Node requires an 'engine_config' input (wire an LM Engine "
                "Node's `engine_config` output)",
            )
        spec = ctx.inputs.get("judge_spec")
        if spec is None:
            return NodeRunResult(
                status="error",
                error="Judge Node requires a 'judge_spec' input (wire a Judge Prompt Node's "
                "`judge_spec` output)",
            )
        calibration = ctx.inputs.get("calibration")  # optional

        modality = spec_modality(spec)
        label = spec.get("label") or spec_key(spec)

        if ctx.dry_run:
            return NodeRunResult(
                outputs={"judge_result": {}},
                meta={
                    "dry_run": True,
                    "n_items": len(dataset),
                    "spec": label,
                    "estimated_calls": {"judge_calls": len(dataset)},
                },
            )

        try:
            require_live(ctx.allow_live, context=f"Judge Node '{label}' over {len(dataset)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        temp_kw: dict[str, Any] = {} if engine_config.get("temperature") is None else {
            "temperature": engine_config["temperature"]
        }
        engine = get_engine(
            engine_config.get("engine_kind") or _DEFAULT_ENGINE_KIND.get(modality, "gpt"),
            history=ctx.run.history,
            model=engine_config.get("model"), creds=load_creds(),
            max_tokens=int(engine_config.get("max_tokens") or 4096), **temp_kw,
        )

        def _should_skip(sample: dict[str, Any]) -> bool:
            # Video-modality judges auto-skip an item with no rendered video.
            if modality != "video":
                return False
            return not bool((sample.get("output") or {}).get("output_video_path"))

        per_item, meta = run_concurrent_judging(
            dataset=dataset,
            spec=spec,
            engine=engine,
            concurrency=max(1, int(engine_config.get("concurrency") or 1)),
            batch_size=max(1, int(p.get("batch_size") or 1)),
            ctx=ctx,
            should_skip=_should_skip if modality == "video" else None,
            calibration=calibration,
        )
        meta["spec"] = label
        return NodeRunResult(outputs={"judge_result": per_item}, meta=meta)
