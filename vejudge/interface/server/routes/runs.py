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
from ..schemas import (
    DiskRunSummary,
    GraphIn,
    NodeResultOut,
    RunRequest,
    RunStatusOut,
    to_graph_spec,
)

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

    # Locked nodes are seeded from a prior run and skipped — layered on top of whatever scope
    # run_mode selected. Only ids that survive into the (possibly reduced) spec matter.
    spec_ids = {n.id for n in spec.nodes}
    seed_node_ids = {nid for nid in req.locked_node_ids if nid in spec_ids}
    if seed_node_ids:
        if not req.seed_run_id:
            raise HTTPException(
                status_code=400, detail="seed_run_id is required when there are locked nodes"
            )
        if seed_results is None:
            seed_handle = REGISTRY.get(req.seed_run_id)
            if seed_handle is None or seed_handle.result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No completed prior run '{req.seed_run_id}' to reuse locked results from",
                )
            seed_results = seed_handle.result.node_results
        missing = sorted(seed_node_ids - set(seed_results))
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Prior run '{req.seed_run_id}' has no result for locked node(s) {missing} "
                "— run them before locking.",
            )

    try:
        validate_edges(spec, node_type_infos())
        topological_sort(spec)
    except GraphError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    handle = REGISTRY.start(
        spec, dry_run=req.dry_run, allow_live=req.allow_live, workflow_name=req.workflow_name,
        target_node_id=target_node_id, seed_results=seed_results,
        seed_node_ids=seed_node_ids or None,
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


# Declared BEFORE "/{run_id}" so "/disk" isn't captured as a run_id.
@router.get("/disk", response_model=list[DiskRunSummary])
def list_disk_runs() -> list[DiskRunSummary]:
    """Past interface runs found on disk under logs/exps (survives server restart)."""
    return [DiskRunSummary(**r) for r in run_manager.list_disk_runs()]


@router.get("/{run_id}/graph")
def get_run_graph(run_id: str) -> dict:
    """The saved workflow_graph.json for a past run, to load into a tab (no canvas layout)."""
    run_dir = run_manager.run_dir_for(run_id)
    graph = run_manager.load_workflow_graph(run_dir)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"No saved graph for run '{run_id}'")
    return graph


@router.get("/{run_id}", response_model=RunStatusOut)
def get_run(run_id: str) -> RunStatusOut:
    handle = REGISTRY.get(run_id)
    if handle is not None:
        return _status_out(handle)
    # Not in the in-memory registry (e.g. after a restart) — reconstruct from the run dir so
    # a past run's statuses + outputs can hydrate the UI (see run_manager.reconstruct_node_results).
    run_dir = run_manager.run_dir_for(run_id)
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    reco = run_manager.reconstruct_node_results(run_dir)
    overall = (run_manager.load_run_status(run_dir) or {}).get("status", "interrupted")
    return RunStatusOut(
        run_id=run_id,
        status=overall,
        error=(run_manager.load_run_status(run_dir) or {}).get("error"),
        node_results={
            nid: NodeResultOut(**r) for nid, r in reco.get("node_results", {}).items()
        },
        order=reco.get("order", []),
    )
