"""Load optional unit-level human annotations from JSONL."""

from __future__ import annotations

from ...database.unit_annotations import load_unit_annotations
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class UnitLabelsNodeExecutor(NodeExecutor):
    node_type = "unit_labels"
    category = "node_db"
    input_sockets: dict = {}
    output_sockets = {"unit_labels": "unit_labels"}
    param_schema = {
        "path": {"type": "string", "default": ""},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        path = str(ctx.params.get("path") or "").strip()
        if not path:
            return NodeRunResult(
                outputs={"unit_labels": []},
                meta={"n_annotations": 0, "note": "No unit annotation file configured."},
            )
        try:
            records = load_unit_annotations(path)
        except (FileNotFoundError, ValueError, OSError) as error:
            return NodeRunResult(status="error", error=str(error))
        return NodeRunResult(
            outputs={"unit_labels": records},
            meta={
                "n_annotations": len(records),
                "n_items": len({record["item_id"] for record in records}),
            },
        )
