"""Dataset Node executor — wraps a ``DataLoader`` (``dl_peanut_eval`` or
``dl_human_annotations``), per ``interface.md``'s Dataset Node spec.

Produces the ``dataset`` socket (item_id -> JudgeSample dict) for ``peanut_eval``, or the
``labels`` socket (item_id -> AggregatedHumanRecord) for ``human_annotations`` — only one
socket is populated per run, chosen by the ``loader`` param.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ...database.dl_human_annotations import aggregate_annotations, load_human_annotations
from ...database.dl_peanut_eval import PeanutEvalLoader
from ...database.dl_peanut_eval.loader import parse_item_id, use_case_for
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register
from .sampling import select_items

LOADER_KINDS = {"peanut_eval", "human_annotations"}


@register
class DatasetNodeExecutor(NodeExecutor):
    node_type = "dataset"
    category = "node_db"
    input_sockets: dict[str, str] = {}
    output_sockets = {"dataset": "dataset", "labels": "labels"}
    param_schema = {
        "loader": {"type": "enum", "options": sorted(LOADER_KINDS), "default": "peanut_eval"},
        "model": {"type": "string", "default": "peanut"},
        "projects": {"type": "list[string]", "default": None},
        "sampling_ratio": {"type": "number", "default": 1.0, "min": 0.0, "max": 1.0},
        "sampling_mode": {
            "type": "enum", "options": ["full", "unified", "stratified"], "default": "full",
        },
        "use_case_filter": {"type": "list[string]", "default": None},
        "item_id_pattern": {"type": "string", "default": None},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        loader_kind = p.get("loader", "peanut_eval")
        if loader_kind not in LOADER_KINDS:
            return NodeRunResult(
                status="error",
                error=f"Unknown loader '{loader_kind}'. Options: {sorted(LOADER_KINDS)}",
            )
        if loader_kind == "peanut_eval":
            return self._run_peanut_eval(p, ctx)
        return self._run_human_annotations(p, ctx)

    def _selected_items(
        self, all_items: list[str], item_use_case: dict[str, str], p: dict[str, Any]
    ) -> list[str]:
        items = _apply_filters(
            all_items,
            use_case_filter=p.get("use_case_filter"),
            item_id_pattern=p.get("item_id_pattern"),
            item_use_case=item_use_case,
        )
        return select_items(
            items,
            ratio=float(p.get("sampling_ratio", 1.0)),
            mode=p.get("sampling_mode", "full"),
            use_case_lookup=item_use_case,
        )

    def _run_peanut_eval(self, p: dict[str, Any], ctx: NodeRunContext) -> NodeRunResult:
        model = p.get("model", "peanut")
        loader = PeanutEvalLoader(model=model, projects=p.get("projects") or None)
        all_items = loader.list_items()
        item_use_case = {iid: use_case_for(parse_item_id(iid)[0]) for iid in all_items}
        items = self._selected_items(all_items, item_use_case, p)

        samples: dict[str, Any] = {}
        skipped: list[str] = []
        for iid in items:
            try:
                samples[iid] = loader.load_sample(iid)
            except Exception as e:  # noqa: BLE001 - one bad item must not drop the rest
                skipped.append(iid)
                ctx.run.logger.warning(
                    "Dataset[%s]: skipping '%s' (%s: %s)",
                    ctx.node_id, iid, type(e).__name__, e,
                )

        ctx.run.logger.info(
            "Dataset[%s]: %d items (peanut_eval, model=%s)%s",
            ctx.node_id, len(samples), model,
            f", skipped {len(skipped)}" if skipped else "",
        )
        meta: dict[str, Any] = {
            "n_items": len(samples), "loader": "peanut_eval", "skipped_items": skipped,
        }
        if not samples:
            meta["warning"] = _zero_items_warning("peanut_eval")
        return NodeRunResult(outputs={"dataset": samples}, meta=meta)

    def _run_human_annotations(self, p: dict[str, Any], ctx: NodeRunContext) -> NodeRunResult:
        model = p.get("model", "peanut")
        projects = p.get("projects") or None
        records = load_human_annotations(models=[model], projects=projects)
        use_case_by_project = {r.project: use_case_for(r.project) for r in records}
        aggregated = aggregate_annotations(records, use_case_lookup=use_case_by_project)

        item_use_case = {iid: agg.use_case for iid, agg in aggregated.items()}
        items = self._selected_items(list(aggregated.keys()), item_use_case, p)

        labels = {iid: aggregated[iid] for iid in items}
        ctx.run.logger.info(
            "Dataset[%s]: %d items (human_annotations, model=%s)",
            ctx.node_id, len(items), model,
        )
        meta: dict[str, Any] = {"n_items": len(items), "loader": "human_annotations"}
        if not labels:
            meta["warning"] = _zero_items_warning("human_annotations")
        return NodeRunResult(outputs={"labels": labels}, meta=meta)


def _zero_items_warning(loader_kind: str) -> str:
    return (
        f"Matched 0 items for loader '{loader_kind}'. Check the project/use_case/item_id "
        "filters, and that VEJUDGE_REPO_ROOT (or VEJUDGE_DATA_ROOT/VEJUDGE_EVALUATION_ROOT) "
        "points at a real data checkout — a run can silently do nothing otherwise."
    )


def _apply_filters(
    items: list[str],
    *,
    use_case_filter: Optional[list[str]],
    item_id_pattern: Optional[str],
    item_use_case: dict[str, str],
) -> list[str]:
    out = items
    if use_case_filter:
        allowed = set(use_case_filter)
        out = [i for i in out if item_use_case.get(i) in allowed]
    if item_id_pattern:
        rx = re.compile(item_id_pattern)
        out = [i for i in out if rx.search(i)]
    return out
