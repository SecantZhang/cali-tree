"""CRUD for saved workflow graphs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import workflows_store
from ..schemas import WorkflowIn, WorkflowOut
from ..workflows_store import InvalidWorkflowName

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
def list_workflows() -> list[str]:
    return workflows_store.list_workflows()


@router.get("/{name}", response_model=WorkflowOut)
def get_workflow(name: str) -> WorkflowOut:
    try:
        wf = workflows_store.load_workflow(name)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if wf is None:
        raise HTTPException(status_code=404, detail=f"No workflow named '{name}'")
    return wf


@router.post("", response_model=WorkflowOut)
def save_workflow(body: WorkflowIn) -> WorkflowOut:
    try:
        return workflows_store.save_workflow(body.name, body.graph)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{name}")
def delete_workflow(name: str) -> dict:
    try:
        deleted = workflows_store.delete_workflow(name)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No workflow named '{name}'")
    return {"deleted": name}
