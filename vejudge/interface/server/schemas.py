"""Pydantic wire-format models for the HTTP/WS API.

Deliberately separate from ``graph.NodeSpec``/``EdgeSpec``/``GraphSpec`` (the internal,
pydantic-free execution model already used and tested by ``executor.py``): these are
the request/response DTOs at the API boundary, converted to/from the internal model by
``to_graph_spec``/``from_graph_spec``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from . import graph as graph_mod


class PositionIn(BaseModel):
    x: float
    y: float


class SizeIn(BaseModel):
    width: float
    height: float


class NodeIn(BaseModel):
    id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    # Wire-layer only — canvas layout, never touched by graph.NodeSpec/execution (see
    # module docstring). Optional so older saved workflows (no layout yet) still load.
    position: Optional[PositionIn] = None
    size: Optional[SizeIn] = None


class EdgeIn(BaseModel):
    source: str
    source_socket: str
    target: str
    target_socket: str


class GraphIn(BaseModel):
    nodes: list[NodeIn] = Field(default_factory=list)
    edges: list[EdgeIn] = Field(default_factory=list)


def to_graph_spec(g: GraphIn) -> graph_mod.GraphSpec:
    return graph_mod.GraphSpec(
        nodes=[graph_mod.NodeSpec(id=n.id, type=n.type, params=n.params) for n in g.nodes],
        edges=[
            graph_mod.EdgeSpec(
                source=e.source, source_socket=e.source_socket,
                target=e.target, target_socket=e.target_socket,
            )
            for e in g.edges
        ],
    )


def from_graph_spec(g: graph_mod.GraphSpec) -> GraphIn:
    return GraphIn(
        nodes=[NodeIn(id=n.id, type=n.type, params=dict(n.params)) for n in g.nodes],
        edges=[
            EdgeIn(
                source=e.source, source_socket=e.source_socket,
                target=e.target, target_socket=e.target_socket,
            )
            for e in g.edges
        ],
    )


class NodeTypeOut(BaseModel):
    type: str
    category: str
    input_sockets: dict[str, str]
    output_sockets: dict[str, str]
    param_schema: dict[str, Any]


class RunRequest(BaseModel):
    # Either a graph to run fresh, or resume_from (a prior run_id) — never both. When
    # resuming, the graph is reconstructed server-side from that run's own saved
    # workflow_graph.json, never from whatever the client sends (see run_manager.py).
    graph: Optional[GraphIn] = None
    dry_run: bool = True
    allow_live: bool = False
    resume_from: Optional[str] = None
    workflow_name: Optional[str] = None


class NodeResultOut(BaseModel):
    status: str
    error: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class RunStatusOut(BaseModel):
    run_id: str
    status: str
    error: Optional[str] = None
    node_results: dict[str, NodeResultOut] = Field(default_factory=dict)


class WorkflowIn(BaseModel):
    name: str
    graph: GraphIn


class WorkflowOut(BaseModel):
    name: str
    graph: GraphIn
    created_at: str
    updated_at: str


class WorkflowRunSummary(BaseModel):
    run_id: str
    status: str  # "running" | "stopping" | "done" | "error" | "stopped" | "interrupted"
    dry_run: bool
    allow_live: bool
    n_checkpointed: int  # how many (item, metric) results are already in judge_results.jsonl


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class CredentialsIn(BaseModel):
    token: str
    base_url: str
    mirror_url: Optional[str] = None


class CredentialsStatusOut(BaseModel):
    configured: bool
    source: str  # "manual" | "env" | "file" | "none"
    base_url: Optional[str] = None  # safe to echo — never the token
