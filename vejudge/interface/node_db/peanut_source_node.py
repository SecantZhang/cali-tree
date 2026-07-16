"""Peanut Source Node executor — loads every raw item from the ``peanut_eval`` loader.

Per the Data Source / Dataset split: this node owns *loading* only (which model, which
projects) — sampling/filtering is the Dataset Node's job, one step downstream, so the
same source can feed multiple differently-sampled Dataset nodes without re-loading.

Loads every item's full ``JudgeSample`` up front (not deferred until after sampling) — a
deliberate simplification over the old combined Dataset Node's "cheap-list-then-sample-
then-load" order. Revisit if a large enough item count makes this measurably slow.
"""

from __future__ import annotations

from typing import Any

from ...database.dl_peanut_eval import PeanutEvalLoader
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .warnings import zero_items_warning


@register
class PeanutSourceNodeExecutor(NodeExecutor):
    node_type = "peanut_source"
    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {"raw_dataset": "raw_dataset"}
    param_schema = {
        "model": {"type": "string", "default": "peanut"},
        # Load several models at once (e.g. ["peanut","coconut","grapenut"]). When set it
        # overrides `model`; item ids are `project::idx::model`, so the merged set has no
        # collisions. Empty/unset → the single `model`.
        "models": {"type": "list[string]", "default": None},
        "projects": {"type": "list[string]", "default": None},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        models = [m for m in (p.get("models") or []) if m] or [p.get("model", "peanut")]
        projects = p.get("projects") or None

        samples: dict[str, Any] = {}
        skipped: list[str] = []
        for model in models:
            loader = PeanutEvalLoader(model=model, projects=projects)
            for iid in loader.list_items():
                try:
                    samples[iid] = loader.load_sample(iid)
                except Exception as e:  # noqa: BLE001 - one bad item must not drop the rest
                    skipped.append(iid)
                    ctx.run.logger.warning(
                        "PeanutSource[%s]: skipping '%s' (%s: %s)",
                        ctx.node_id, iid, type(e).__name__, e,
                    )

        ctx.run.logger.info(
            "PeanutSource[%s]: %d items (models=%s)%s",
            ctx.node_id, len(samples), ",".join(models),
            f", skipped {len(skipped)}" if skipped else "",
        )
        meta: dict[str, Any] = {
            "n_items": len(samples), "loader": "peanut_eval", "skipped_items": skipped,
        }
        if not samples:
            meta["warning"] = zero_items_warning("peanut_eval")
        return NodeRunResult(outputs={"raw_dataset": samples}, meta=meta)
