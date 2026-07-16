"""Shared base for the per-model eval Source nodes (Peanut / Coconut / Grapenut).

Each model renders to its own on-disk layout (see ``dl_peanut_eval.video_resolver`` +
``config.MODEL_LAYOUT``), but loads through the same ``PeanutEvalLoader`` and produces the
same ``raw_dataset`` output. So there is **one** base executor with the loading logic and a
``MODEL`` class attribute; the three registered node types are thin subclasses. Multiple of
them wire into a single Dataset node (its ``raw_dataset`` is a fan-in socket), which merges
their pools — item ids are ``project::idx::model`` so the models never collide.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ...database.dl_peanut_eval import PeanutEvalLoader
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult
from .warnings import zero_items_warning


class EvalSourceNodeExecutor(NodeExecutor):
    """Loads every rendered item for a single model. Not registered directly — subclass it,
    set ``node_type`` + ``MODEL``, and apply ``@register``."""

    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {"raw_dataset": "raw_dataset"}
    param_schema = {
        "projects": {"type": "list[string]", "default": None},
    }
    MODEL: ClassVar[str] = ""

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        loader = PeanutEvalLoader(model=self.MODEL, projects=ctx.params.get("projects") or None)

        samples: dict[str, Any] = {}
        skipped: list[str] = []
        for iid in loader.list_items():
            try:
                samples[iid] = loader.load_sample(iid)
            except Exception as e:  # noqa: BLE001 - one bad item must not drop the rest
                skipped.append(iid)
                ctx.run.logger.warning(
                    "%s[%s]: skipping '%s' (%s: %s)",
                    type(self).__name__, ctx.node_id, iid, type(e).__name__, e,
                )

        ctx.run.logger.info(
            "%s[%s]: %d items (model=%s)%s",
            type(self).__name__, ctx.node_id, len(samples), self.MODEL,
            f", skipped {len(skipped)}" if skipped else "",
        )
        meta: dict[str, Any] = {
            "n_items": len(samples), "loader": "peanut_eval", "model": self.MODEL,
            "skipped_items": skipped,
        }
        if not samples:
            meta["warning"] = zero_items_warning("peanut_eval")
        return NodeRunResult(outputs={"raw_dataset": samples}, meta=meta)
