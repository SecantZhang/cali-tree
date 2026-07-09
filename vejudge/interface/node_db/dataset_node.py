"""Dataset Node executor — samples/filters an already-loaded ``raw_dataset`` stream and
joins matching human-annotation labels for exactly the resulting item set.

Per the Data Source / Dataset split: loading lives one step upstream (Peanut Source Node,
or a future source node for another model), this node owns sampling/filtering —
``raw_dataset`` is a distinct socket type from this node's own ``samples`` output
specifically so a source's raw output can never be wired directly into a Judge node,
forcing sampling to always be an explicit step. ``samples`` is deliberately not named
``dataset`` — that name collided with the node's own name and with the sibling ``labels``
output, making the two outputs easy to conflate.

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
    output_sockets = {"samples": "samples", "labels": "labels"}
    param_schema = {
        "sampling_ratio": {"type": "number", "default": 1.0, "min": 0.0, "max": 1.0},
        "sampling_mode": {
            "type": "enum", "options": ["unified", "stratified"], "default": "unified",
        },
        "use_case_filter": {"type": "list[string]", "default": None},
        "item_id_pattern": {"type": "string", "default": None},
        # Off by default so existing full/dry runs (sampling_ratio=1.0, or any run that
        # isn't feeding an Eval node) are unaffected. When set, the sampling pool is
        # restricted to items with a human label *before* ratio/mode is applied, so a small
        # sample can never land on 0 overlap with Eval by bad luck (see the "0 aligned
        # items" failure this guards against — a live run's Dataset sample missed every
        # labeled item even though 17/54 peanut items have one).
        "require_labels": {"type": "bool", "default": False},
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
        pool = apply_filters(
            list(raw_dataset),
            use_case_filter=p.get("use_case_filter"),
            item_id_pattern=p.get("item_id_pattern"),
            item_use_case=item_use_case,
        )

        # Computed before sampling (not just against the final selected items) so both the
        # `require_labels` guarantee and the coverage diagnostic below see the same
        # pre-sampling pool.
        records = load_human_annotations()
        use_case_by_project = {r.project: use_case_for(r.project) for r in records}
        aggregated = aggregate_annotations(records, use_case_lookup=use_case_by_project)
        n_pool_labeled = sum(1 for iid in pool if iid in aggregated)

        if p.get("require_labels"):
            pool = [iid for iid in pool if iid in aggregated]

        items = select_items(
            pool,
            ratio=float(p.get("sampling_ratio", 1.0)),
            mode=p.get("sampling_mode", "unified"),
            use_case_lookup=item_use_case,
        )

        samples: dict[str, Any] = {iid: raw_dataset[iid] for iid in items}
        labels: dict[str, Any] = {iid: aggregated[iid] for iid in items if iid in aggregated}

        ctx.run.logger.info(
            "Dataset[%s]: %d / %d item(s) selected, %d with human labels",
            ctx.node_id, len(samples), len(raw_dataset), len(labels),
        )
        meta: dict[str, Any] = {
            "n_items": len(samples),
            "n_raw_items": len(raw_dataset),
            "n_labels": len(labels),
            "n_pool_labeled": n_pool_labeled,
        }
        if not samples:
            meta["warning"] = zero_items_warning("dataset")
        elif not p.get("require_labels") and not labels and n_pool_labeled > 0:
            meta["warning"] = (
                f"Sampled {len(samples)} item(s), none have human labels, though "
                f"{n_pool_labeled}/{len(pool)} item(s) in the pre-sampling pool do. Enable "
                "'require_labels' on this Dataset node (or raise sampling_ratio) to "
                "guarantee overlap with a downstream Eval node."
            )
        return NodeRunResult(outputs={"samples": samples, "labels": labels}, meta=meta)
