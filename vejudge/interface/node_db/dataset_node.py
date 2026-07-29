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
from .sampling import apply_filters, select_items, select_split_label_items
from .warnings import zero_items_warning


@register
class DatasetNodeExecutor(NodeExecutor):
    node_type = "dataset"
    category = "node_db"
    input_sockets = {"raw_dataset": "raw_dataset", "raw_labels": "raw_labels"}
    # Fan-in: multiple source nodes (e.g. Peanut/Coconut/Grapenut) can wire into
    # `raw_dataset`; their item pools are merged (item ids are model-namespaced, so no
    # collision). The executor delivers the inputs as a list of raw_dataset dicts.
    multi_input_sockets = frozenset({"raw_dataset", "raw_labels"})
    output_sockets = {"samples": "samples", "labels": "labels"}
    param_schema = {
        # Dual-purpose size control: a value ≤ 1 is a fraction (0.5 = 50%), a value > 1 is an
        # absolute item count (5 = five items). The `full_dataset` toggle below overrides it.
        "sampling_ratio": {"type": "number", "default": 1.0, "min": 0.0},
        # Explicit "use the entire dataset (100%)" switch — disambiguates the number field so a
        # user never has to wonder whether "1" means the whole set or a single item. When on,
        # `sampling_ratio` is ignored.
        "full_dataset": {"type": "bool", "default": False},
        "sampling_mode": {
            "type": "enum",
            "options": ["unified", "stratified", "split_label_stratified"],
            "default": "unified",
        },
        # Optional split-specific fractions for calibration datasets. When either is set,
        # these take precedence over the single global ratio for that split. This permits
        # using all scarce official training data while evaluating on a bounded held-out
        # subset.
        "train_sampling_ratio": {
            "type": "number", "default": None, "min": 0.0, "max": 1.0,
        },
        "test_sampling_ratio": {
            "type": "number", "default": None, "min": 0.0, "max": 1.0,
        },
        # Rotate grouped held-out task IDs before deterministic selection. At a 50%
        # ratio, offsets 0 and 1 are exact complementary task halves.
        "test_group_offset": {
            "type": "number", "default": 0, "min": 0,
        },
        # Keep all editor outputs sharing a task UID together whenever split-specific
        # sampling is active.
        "group_by_task": {"type": "bool", "default": True},
        "use_case_filter": {"type": "list[string]", "default": None},
        "item_id_pattern": {"type": "string", "default": None},
        # Off by default so existing full/dry runs (sampling_ratio=1.0, or any run that
        # isn't feeding an Eval node) are unaffected. When set, the sampling pool is
        # restricted to items with a human label *before* ratio/mode is applied, so a small
        # sample can never land on 0 overlap with Eval by bad luck (see the "0 aligned
        # items" failure this guards against — a live run's Dataset sample missed every
        # labeled item even though 17/54 peanut items have one).
        "require_labels": {"type": "bool", "default": False},
        # How multiple annotators' scores for the same video are combined into the `labels`
        # output. mean (default) / median / max / min collapse to one point estimate per
        # dimension; "none" does no aggregation — `scores` is left empty and the individual
        # per-annotator ratings are exposed in `raw_scores` (Eval then scores the judge against
        # each rater; calibration nodes require an aggregated method).
        "aggregation_method": {
            "type": "enum",
            "options": ["mean", "median", "max", "min", "none"],
            "default": "none",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        raw = ctx.inputs.get("raw_dataset")
        if raw is None:
            return NodeRunResult(
                status="error",
                error="Dataset Node requires a 'raw_dataset' input (wire a source node's "
                "`raw_dataset` output, e.g. a Peanut Source Node)",
            )
        # Fan-in delivers a list of raw_dataset dicts (one per wired source); merge them
        # into one pool. Item ids are model-namespaced so sources never collide. A plain
        # dict (a single non-fan-in caller, e.g. a direct unit test) is accepted as-is.
        if isinstance(raw, list):
            raw_dataset: dict = {}
            for part in raw:
                if isinstance(part, dict):
                    raw_dataset.update(part)
        else:
            raw_dataset = raw

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

        # A labeled source (ImagenHub) can supply its own labels through the optional
        # raw_labels socket. Legacy video sources omit it and retain the existing human
        # annotation lookup unchanged.
        raw_labels = ctx.inputs.get("raw_labels")
        if raw_labels is not None:
            if isinstance(raw_labels, list):
                aggregated: dict[str, Any] = {}
                for part in raw_labels:
                    if isinstance(part, dict):
                        aggregated.update(part)
            else:
                aggregated = raw_labels
        else:
            records = load_human_annotations()
            use_case_by_project = {r.project: use_case_for(r.project) for r in records}
            aggregated = aggregate_annotations(
                records,
                use_case_lookup=use_case_by_project,
                method=p.get("aggregation_method") or "none",
            )
        n_pool_labeled = sum(1 for iid in pool if iid in aggregated)

        if p.get("require_labels"):
            pool = [iid for iid in pool if iid in aggregated]

        # `sampling_ratio` is dual-purpose: > 1 is an absolute item count, ≤ 1 is a fraction.
        # The `full_dataset` toggle overrides both with the whole (filtered) pool.
        raw_size = float(p.get("sampling_ratio", 1.0))
        if p.get("full_dataset"):
            ratio, count = 1.0, None
        elif raw_size > 1:
            ratio, count = 1.0, int(raw_size)
        else:
            ratio, count = raw_size, None

        sampling_mode = p.get("sampling_mode", "unified")
        if sampling_mode == "split_label_stratified":
            if not raw_labels:
                return NodeRunResult(
                    status="error",
                    error=(
                        "split_label_stratified sampling requires a connected raw_labels "
                        "input with split and target_label metadata"
                    ),
                )
            train_ratio_raw = p.get("train_sampling_ratio")
            test_ratio_raw = p.get("test_sampling_ratio")
            split_ratios = (
                None
                if train_ratio_raw is None and test_ratio_raw is None
                else {
                    "train": (
                        ratio
                        if train_ratio_raw is None
                        else float(train_ratio_raw)
                    ),
                    "test": (
                        ratio
                        if test_ratio_raw is None
                        else float(test_ratio_raw)
                    ),
                }
            )
            group_lookup = (
                {
                    item_id: str(
                        raw_dataset[item_id].get("task_uid")
                        or item_id.split("::", 1)[0]
                    )
                    for item_id in pool
                }
                if split_ratios is not None
                and bool(p.get("group_by_task", True))
                else None
            )
            items = select_split_label_items(
                pool,
                ratio=ratio,
                count=count,
                split_ratios=split_ratios,
                group_lookup=group_lookup,
                split_group_offsets={
                    "test": int(p.get("test_group_offset") or 0),
                },
                split_lookup={
                    item_id: str(raw_dataset[item_id].get("split") or "unknown")
                    for item_id in pool
                },
                label_lookup={
                    item_id: str(
                        (aggregated.get(item_id) or {}).get("target_label") or "unknown"
                    )
                    for item_id in pool
                },
            )
        else:
            items = select_items(
                pool,
                ratio=ratio,
                count=count,
                mode=sampling_mode,
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
        if any(
            sample.get("split") in {"train", "test"}
            for sample in samples.values()
        ):
            meta["split_counts"] = {
                split: sum(
                    sample.get("split") == split
                    for sample in samples.values()
                )
                for split in ("train", "test")
            }
            meta["task_counts"] = {
                split: len({
                    str(
                        sample.get("task_uid")
                        or item_id.split("::", 1)[0]
                    )
                    for item_id, sample in samples.items()
                    if sample.get("split") == split
                })
                for split in ("train", "test")
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
