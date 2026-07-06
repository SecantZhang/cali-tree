"""POST/GET /api/runs — start a graph run and report its status.

Dry-run/--live gating is enforced inside the Judge Node executor itself (server-side,
not just here) — this route only rejects a structurally invalid graph before spending a
thread on it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..graph import GraphError, topological_sort, validate_edges
from ..registry import node_type_infos
from ..run_registry import REGISTRY, RunHandle
from ..schemas import NodeResultOut, RunRequest, RunStatusOut, to_graph_spec

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
    )


@router.post("", response_model=RunStatusOut)
def create_run(req: RunRequest) -> RunStatusOut:
    spec = to_graph_spec(req.graph)
    try:
        validate_edges(spec, node_type_infos())
        topological_sort(spec)
    except GraphError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    handle = REGISTRY.start(spec, dry_run=req.dry_run, allow_live=req.allow_live)
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
