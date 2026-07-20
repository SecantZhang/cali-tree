"""VE-Bench Source Node — loads every VE-Bench DB item (edit instruction + edited video +
source video) as a raw_dataset. A separate calibration track from the peanut sources; its
human MOS labels live under HUMAN_ANNOTATIONS_ROOT/vebench (see
``dl_vebench.materialize_vebench_labels``), so the shared Dataset node picks them up by
item id like any other source.
"""

from __future__ import annotations

from typing import Any

from ...database.dl_vebench import VeBenchLoader
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .warnings import zero_items_warning


@register
class VeBenchSourceNodeExecutor(NodeExecutor):
    node_type = "vebench_source"
    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {"raw_dataset": "raw_dataset"}
    param_schema: dict = {}

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        loader = VeBenchLoader()
        samples: dict[str, Any] = {}
        skipped: list[str] = []
        for iid in loader.list_items():
            try:
                samples[iid] = loader.load_sample(iid)
            except Exception as e:  # noqa: BLE001 - one bad item must not drop the rest
                skipped.append(iid)
                ctx.run.logger.warning(
                    "VeBenchSource[%s]: skipping '%s' (%s: %s)",
                    ctx.node_id, iid, type(e).__name__, e,
                )
        ctx.run.logger.info(
            "VeBenchSource[%s]: %d items%s",
            ctx.node_id, len(samples), f", skipped {len(skipped)}" if skipped else "",
        )
        meta: dict[str, Any] = {
            "n_items": len(samples), "loader": "vebench", "skipped_items": skipped,
        }
        if not samples:
            meta["warning"] = zero_items_warning("vebench")
        return NodeRunResult(outputs={"raw_dataset": samples}, meta=meta)
