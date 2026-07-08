"""Dataset Node executor — samples/filters an already-loaded ``raw_dataset`` stream and
joins matching human-annotation labels for exactly the resulting item set.

Per the Data Source / Dataset split: loading lives one step upstream (Peanut Source Node,
or a future source node for another model), this node owns sampling/filtering —
``raw_dataset`` is a distinct socket type from ``dataset`` specifically so a source's raw
output can never be wired directly into a Judge node, forcing sampling to always be an
explicit step.

Human annotation labels are looked up by item id for this node's own sampled items rather
than sampled independently by a separate node: human annotation records use the identical
``project::prompt_idx::model`` item id format as the peanut side (see
``dl_human_annotations.loader.HumanAnnotationRecord.item_id`` and
``dl_peanut_eval.loader.parse_item_id``), so an earlier design that sampled each side on
its own (a standalone Human Annotations node with its own ratio/mode params) could silently
select a different item set on each branch — this node's sampling now runs once, and labels
are a lookup against that one set, guaranteeing judge results and human labels always
describe the same items by construction.
"""

from __future__ import annotations

from typing import Any

from ...database.dl_human_annotations import aggregate_annotations, load_human_annotations
from ...database.dl_peanut_eval.loader import use_case_for
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .sampling import apply_filters, select_items
from .warnings import zero_items_warning


@register
class DatasetNodeExecutor(NodeExecutor):
    node_type = "dataset"
    category = "node_db"
    input_sockets = {"raw_dataset": "raw_dataset"}
    output_sockets = {"dataset": "dataset", "labels": "labels"}
    param_schema = {
        "sampling_ratio": {"type": "number", "default": 1.0, "min": 0.0, "max": 1.0},
        "sampling_mode": {
            "type": "enum", "options": ["unified", "stratified"], "default": "unified",
        },
        "use_case_filter": {"type": "list[string]", "default": None},
        "item_id_pattern": {"type": "string", "default": None},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        raw_dataset = ctx.inputs.get("raw_dataset")
        if raw_dataset is None:
            return NodeRunResult(
                status="error",
                error="Dataset Node requires a 'raw_dataset' input (wire a source node's "
                "`raw_dataset` output, e.g. a Peanut Source Node)",
            )

        # Every JudgeSample already carries its own `use_case` (set by the source loader
        # via the same `use_case_for` lookup) — no need to re-derive it from the item id.
        item_use_case = {
            iid: sample.get("use_case", "unknown") for iid, sample in raw_dataset.items()
        }
        items = apply_filters(
            list(raw_dataset),
            use_case_filter=p.get("use_case_filter"),
            item_id_pattern=p.get("item_id_pattern"),
            item_use_case=item_use_case,
        )
        items = select_items(
            items,
            ratio=float(p.get("sampling_ratio", 1.0)),
            mode=p.get("sampling_mode", "unified"),
            use_case_lookup=item_use_case,
        )

        dataset: dict[str, Any] = {iid: raw_dataset[iid] for iid in items}

        records = load_human_annotations()
        use_case_by_project = {r.project: use_case_for(r.project) for r in records}
        aggregated = aggregate_annotations(records, use_case_lookup=use_case_by_project)
        labels: dict[str, Any] = {iid: aggregated[iid] for iid in items if iid in aggregated}

        ctx.run.logger.info(
            "Dataset[%s]: %d / %d item(s) selected, %d with human labels",
            ctx.node_id, len(dataset), len(raw_dataset), len(labels),
        )
        meta: dict[str, Any] = {
            "n_items": len(dataset),
            "n_raw_items": len(raw_dataset),
            "n_labels": len(labels),
        }
        if not dataset:
            meta["warning"] = zero_items_warning("dataset")
        return NodeRunResult(outputs={"dataset": dataset, "labels": labels}, meta=meta)
