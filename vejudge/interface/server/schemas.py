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


class NodeIn(BaseModel):
    id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


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
    graph: GraphIn
    dry_run: bool = True
    allow_live: bool = False


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
