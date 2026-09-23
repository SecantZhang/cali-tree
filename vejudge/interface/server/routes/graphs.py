"""POST /api/graph/validate — edge/type-checking + topological sort, no execution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ... import node_types  # noqa: F401 - import side effect
from ..graph import GraphError, topological_sort, validate_edges
from ..registry import node_type_infos
from ..schemas import GraphIn, to_graph_spec

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.post("/validate")
def validate_graph(graph: GraphIn) -> dict:
    spec = to_graph_spec(graph)
    try:
        validate_edges(spec, node_type_infos())
        order = topological_sort(spec)
    except GraphError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"valid": True, "order": order}
