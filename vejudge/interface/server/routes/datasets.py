"""Read-only dataset browsing: the left-panel Datasets tab + Dataset Node secondary tab."""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ....database.dl_human_annotations import aggregate_annotations, load_human_annotations
from ....database.dl_imagenhub import ImagenHubLoader
from ....database.dl_peanut_eval import PeanutEvalLoader
from ....database.dl_peanut_eval.loader import parse_item_id, use_case_for

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# This route is the left-panel Datasets tab's read-only browser (per interface.md,
# independent of any one graph/node) — it talks to the loaders directly, not through a
# node executor, so this list lives here rather than on any particular node type.
LOADER_KINDS = {"peanut_eval", "human_annotations", "imagenhub"}


@router.get("/loaders")
def list_loaders() -> list[str]:
    return sorted(LOADER_KINDS)


@router.get("/{loader}/items")
def list_items(
    loader: str, model: str = "peanut", project: Optional[str] = Query(None)
) -> dict:
    if loader == "peanut_eval":
        items = PeanutEvalLoader(
            model=model, projects=[project] if project else None
        ).list_items()
        return {"items": sorted(items)}
    if loader == "human_annotations":
        records = load_human_annotations(
            models=[model], projects=[project] if project else None
        )
        use_case_by_project = {r.project: use_case_for(r.project) for r in records}
        aggregated = aggregate_annotations(records, use_case_lookup=use_case_by_project)
        return {"items": sorted(aggregated)}
    if loader == "imagenhub":
        try:
            return {"items": ImagenHubLoader().list_items()}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail=f"Unknown loader '{loader}'")


@router.get("/{loader}/items/{item_id}")
def get_item(loader: str, item_id: str, model: str = "peanut") -> dict:
    if loader == "peanut_eval":
        try:
            return PeanutEvalLoader(model=model).load_sample(item_id)
        except Exception as e:  # noqa: BLE001 - unknown/malformed item id -> 404
            raise HTTPException(status_code=404, detail=str(e)) from e
    if loader == "human_annotations":
        # item ids share one "<project>::<idx>::<model>" scheme across both loaders.
        project, _prompt_idx, model_from_id = parse_item_id(item_id)
        records = load_human_annotations(models=[model_from_id], projects=[project])
        aggregated = aggregate_annotations(
            records, use_case_lookup={project: use_case_for(project)}
        )
        agg = aggregated.get(item_id)
        if agg is None:
            raise HTTPException(status_code=404, detail=f"No item '{item_id}'")
        return asdict(agg)
    if loader == "imagenhub":
        try:
            loader_impl = ImagenHubLoader()
            sample = loader_impl.load_sample(item_id)
            sample["human_label"] = loader_impl.load_label(item_id)
            return sample
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail=f"Unknown loader '{loader}'")
