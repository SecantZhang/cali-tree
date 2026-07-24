"""CRUD for saved workflow graphs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .... import config
from .. import run_manager, workflows_store
from ..run_registry import REGISTRY
from ..schemas import WorkflowIn, WorkflowOut, WorkflowRunSummary
from ..workflows_store import InvalidWorkflowName

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
def list_workflows() -> list[str]:
    return workflows_store.list_workflows()


@router.post("", response_model=WorkflowOut)
def save_workflow(body: WorkflowIn) -> WorkflowOut:
    try:
        return workflows_store.save_workflow(body.name, body.graph)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{name:path}/runs", response_model=list[WorkflowRunSummary])
def list_workflow_runs(name: str) -> list[WorkflowRunSummary]:
    """Prior runs of this saved workflow, newest first — lets the UI auto-offer Resume.

    A run with no in-flight handle for its directory AND no run_status.json (i.e. the
    server was restarted or crashed mid-run) is reported as "interrupted", distinct from
    a clean "stopped"/"error"/"done" — it never got a chance to record its own terminal
    outcome.
    """
    exps_root = config.LOGS_ROOT / "exps"
    if not exps_root.is_dir():
        return []

    summaries: list[WorkflowRunSummary] = []
    for run_dir in sorted(exps_root.glob("*-exps"), reverse=True):
        cfg = run_manager.load_run_config(run_dir)
        if not cfg or cfg.get("workflow_name") != name:
            continue
        run_id = run_dir.name[: -len("-exps")]

        # A resume gets its own run_id/handle sharing this same directory — check for one
        # actively in flight (covers both the original attempt and any resume of it)
        # before falling back to the last-completed status recorded on disk, which is
        # otherwise the only place a *finished* resume's outcome is visible (the original
        # run_id's own handle, if it still exists, never learns about it).
        active_handle = REGISTRY.find_active_for_dir(run_dir)
        if active_handle is not None:
            status = active_handle.status
        else:
            run_status = run_manager.load_run_status(run_dir)
            status = run_status["status"] if run_status else "interrupted"

        summaries.append(
            WorkflowRunSummary(
                run_id=run_id,
                status=status,
                dry_run=bool(cfg.get("dry_run", True)),
                allow_live=bool(cfg.get("allow_live", False)),
                n_checkpointed=run_manager.count_checkpointed(run_dir),
            )
        )
    return summaries


@router.get("/{name:path}", response_model=WorkflowOut)
def get_workflow(name: str) -> WorkflowOut:
    try:
        wf = workflows_store.load_workflow(name)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if wf is None:
        raise HTTPException(status_code=404, detail=f"No workflow named '{name}'")
    return wf


@router.delete("/{name:path}")
def delete_workflow(name: str) -> dict:
    try:
        deleted = workflows_store.delete_workflow(name)
    except InvalidWorkflowName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No workflow named '{name}'")
    return {"deleted": name}
