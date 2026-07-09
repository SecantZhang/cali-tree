"""POST/GET /api/runs — start a graph run and report its status.

Dry-run/--live gating is enforced inside the Judge Node executor itself (server-side,
not just here) — this route only rejects a structurally invalid graph before spending a
thread on it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import run_manager
from ..graph import GraphError, ancestors_closure, topological_sort, validate_edges
from ..registry import node_type_infos
from ..run_registry import REGISTRY, RunHandle
from ..schemas import GraphIn, NodeResultOut, RunRequest, RunStatusOut, to_graph_spec

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _status_out(handle: RunHandle) -> RunStatusOut:
    node_results = {}
    if handle.result is not None:
        node_results = {
            nid: NodeResultOut(status=r.status, error=r.error, meta=r.meta, outputs=r.outputs)
            for nid, r in handle.result.node_results.items()
        }
    return RunStatusOut(
        run_id=handle.run_id,
        status=handle.status,
        error=handle.result.error if handle.result else None,
        node_results=node_results,
        order=handle.result.order if handle.result else [],
    )


@router.post("", response_model=RunStatusOut)
def create_run(req: RunRequest) -> RunStatusOut:
    if req.resume_from is not None:
        return _create_resumed_run(req.resume_from)

    if req.graph is None:
        raise HTTPException(status_code=400, detail="graph is required")
    spec = to_graph_spec(req.graph)

    target_node_id = req.target_node_id
    seed_results = None

    if req.run_mode == "ancestors":
        if not target_node_id:
            raise HTTPException(
                status_code=400, detail="target_node_id is required when run_mode='ancestors'"
            )
        try:
            spec = ancestors_closure(spec, target_node_id)
        except GraphError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        # The reduced graph is executed like any other whole-graph run below — the
        # executor needs no target/seed once the reduction has already happened here.
        target_node_id = None
    elif req.run_mode == "self_only":
        if not target_node_id:
            raise HTTPException(
                status_code=400, detail="target_node_id is required when run_mode='self_only'"
            )
        if not req.seed_run_id:
            raise HTTPException(
                status_code=400, detail="seed_run_id is required when run_mode='self_only'"
            )
        seed_handle = REGISTRY.get(req.seed_run_id)
        if seed_handle is None or seed_handle.result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No completed prior run '{req.seed_run_id}' to re-run from",
            )
        seed_results = seed_handle.result.node_results
        try:
            ancestor_ids = {n.id for n in ancestors_closure(spec, target_node_id).nodes}
        except GraphError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        ancestor_ids.discard(target_node_id)
        missing = sorted(ancestor_ids - set(seed_results))
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Prior run '{req.seed_run_id}' doesn't cover this node's dependencies "
                f"{missing} — run the full ancestor chain first (e.g. via Run).",
            )

    try:
        validate_edges(spec, node_type_infos())
        topological_sort(spec)
    except GraphError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    handle = REGISTRY.start(
        spec, dry_run=req.dry_run, allow_live=req.allow_live, workflow_name=req.workflow_name,
        target_node_id=target_node_id, seed_results=seed_results,
    )
    return _status_out(handle)


def _create_resumed_run(resume_from: str) -> RunStatusOut:
    """Reconstructs the graph/config from the prior run's own saved files — never from
    whatever the client currently has on its canvas, so an edited graph can't silently mix
    two configurations against one checkpoint (see interface v2 plan, Stage A2)."""
    run_dir = run_manager.run_dir_for(resume_from)
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"No run '{resume_from}' to resume")

    graph_json = run_manager.load_workflow_graph(run_dir)
    if graph_json is None:
        raise HTTPException(
            status_code=400, detail=f"Run '{resume_from}' has no saved graph to resume"
        )
    cfg = run_manager.load_run_config(run_dir) or {}

    if not REGISTRY.try_claim_resume_dir(run_dir):
        raise HTTPException(
            status_code=409, detail=f"Run '{resume_from}' is already being resumed elsewhere"
        )
    try:
        spec = to_graph_spec(GraphIn(**graph_json))
        validate_edges(spec, node_type_infos())
        topological_sort(spec)
    except GraphError as e:
        REGISTRY.release_resume_dir(run_dir)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        REGISTRY.release_resume_dir(run_dir)
        raise

    # Once the background thread actually starts, its own finally block owns releasing the
    # claim when the resumed run reaches a terminal state — only a failure before that
    # point (e.g. start_run() itself raising) needs releasing here.
    try:
        handle = REGISTRY.start(
            spec,
            dry_run=cfg.get("dry_run", True),
            allow_live=cfg.get("allow_live", False),
            resume_from=run_dir,
            workflow_name=cfg.get("workflow_name"),
        )
    except Exception:
        REGISTRY.release_resume_dir(run_dir)
        raise
    return _status_out(handle)


@router.post("/{run_id}/stop", response_model=RunStatusOut)
def stop_run(run_id: str) -> RunStatusOut:
    handle = REGISTRY.get(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    if not REGISTRY.request_stop(run_id):
        raise HTTPException(
            status_code=409, detail=f"Run '{run_id}' is not running (status={handle.status})"
        )
    return _status_out(handle)


@router.get("", response_model=list[str])
def list_runs() -> list[str]:
    return REGISTRY.list_ids()


@router.get("/{run_id}", response_model=RunStatusOut)
def get_run(run_id: str) -> RunStatusOut:
    handle = REGISTRY.get(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    return _status_out(handle)
