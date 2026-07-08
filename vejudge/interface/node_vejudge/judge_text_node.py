"""Text Judge Node executor — runs the text-modality metrics (M1, M3) over a dataset.

Split from the old single Judge Node along the modality boundary that already existed
internally (separate text/video engine configs, separate concurrency knobs). See
``judge_video_node.py`` for its video counterpart and ``_concurrent_judging.py`` for the
shared execution engine both wrap. Engine config (kind/model/temperature/concurrency)
comes from a required upstream LM Engine Node (``lm_engine_node.py``) rather than this
node's own params — see that module's docstring for why its output is a plain config dict,
not a live engine.
"""

from __future__ import annotations

from typing import Any

from ...core.judge.registry import TEXT_JUDGES
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from ._concurrent_judging import run_concurrent_judging


@register
class TextJudgeNodeExecutor(NodeExecutor):
    node_type = "judge_text"
    category = "node_vejudge"
    input_sockets = {"dataset": "dataset", "engine_config": "engine_config"}
    output_sockets = {"judge_result": "judge_result"}
    param_schema = {
        "metrics": {"type": "list[enum]", "options": list(TEXT_JUDGES), "default": None},
        "batch_size": {"type": "number", "default": 1, "min": 1},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        dataset = ctx.inputs.get("dataset")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Text Judge Node requires a 'dataset' input (wire a Dataset Node's "
                "`dataset` output)",
            )
        engine_config = ctx.inputs.get("engine_config")
        if engine_config is None:
            return NodeRunResult(
                status="error",
                error="Text Judge Node requires an 'engine_config' input (wire an LM "
                "Engine Node's `engine_config` output)",
            )

        metrics = p.get("metrics") or list(TEXT_JUDGES)
        unknown = [m for m in metrics if m not in TEXT_JUDGES]
        if unknown:
            return NodeRunResult(
                status="error", error=f"Unknown or non-text metric id(s): {unknown}"
            )

        if ctx.dry_run:
            return _dry_run_result(dataset, metrics)

        try:
            require_live(
                ctx.allow_live, context=f"Text Judge Node over {len(dataset)} item(s)"
            )
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        temp_kw: dict[str, Any] = {} if engine_config.get("temperature") is None else {
            "temperature": engine_config["temperature"]
        }
        engine = get_engine(
            engine_config.get("engine_kind", "gpt"), history=ctx.run.history,
            model=engine_config.get("model"), creds=load_creds(),
            max_tokens=int(engine_config.get("max_tokens") or 4096), **temp_kw,
        )
        per_item, meta = run_concurrent_judging(
            dataset=dataset,
            metrics=metrics,
            engine=engine,
            concurrency=max(1, int(engine_config.get("concurrency") or 1)),
            batch_size=max(1, int(p.get("batch_size") or 1)),
            ctx=ctx,
        )
        return NodeRunResult(outputs={"judge_result": per_item}, meta=meta)


def _dry_run_result(dataset: dict[str, Any], metrics: list[str]) -> NodeRunResult:
    n_items = len(dataset)
    return NodeRunResult(
        outputs={"judge_result": {}},
        meta={
            "dry_run": True,
            "n_items": n_items,
            "estimated_calls": {"text_judge_calls": len(metrics) * n_items},
        },
    )
