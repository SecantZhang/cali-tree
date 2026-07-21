"""Pydantic wire-format models for the HTTP/WS API.

Deliberately separate from ``graph.NodeSpec``/``EdgeSpec``/``GraphSpec`` (the internal,
pydantic-free execution model already used and tested by ``executor.py``): these are
the request/response DTOs at the API boundary, converted to/from the internal model by
``to_graph_spec``/``from_graph_spec``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

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
    # Also wire-layer only, same as position/size above — purely cosmetic "what this node
    # looked like last time" state (status dot, collapsed, stale-flag, manual resize
    # memory), restored on load so reopening a saved workflow looks the same as when it was
    # saved. Never touched by graph.NodeSpec/execution — deliberately not a substitute for
    # real run state, which already has its own independent mechanism (workflow_name
    # tagging + GET /api/workflows/{name}/runs).
    status: Optional[str] = None
    error: Optional[str] = None
    collapsed: Optional[bool] = None
    expanded_size: Optional[SizeIn] = None
    stale: Optional[bool] = None
    # Locked = its result is frozen and reused (seeded) on every run instead of recomputed.
    # Wire-layer only for persistence round-trip; execution reads the run request's
    # `locked_node_ids`, not this (to_graph_spec drops it).
    locked: Optional[bool] = None


class EdgeIn(BaseModel):
    source: str
    source_socket: str
    target: str
    target_socket: str


class GroupIn(BaseModel):
    # A purely-visual canvas group (ComfyUI-style). Never touched by execution — persisted so
    # a saved workflow keeps its grouping/layout. Without this field on GraphIn, a `groups`
    # array in the POST body would be silently dropped (models default to extra="ignore").
    id: str
    title: str = ""
    position: PositionIn
    size: SizeIn


class GraphIn(BaseModel):
    nodes: list[NodeIn] = Field(default_factory=list)
    edges: list[EdgeIn] = Field(default_factory=list)
    groups: list[GroupIn] = Field(default_factory=list)


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
    subcategory: Optional[str] = None
    multi_input_sockets: list[str] = []
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
    # Per-node Run/Re-run (see NodeChrome.tsx's ▶/↻ buttons). `target_node_id` names the
    # node the button was clicked on; `run_mode` selects the scope: "ancestors" reduces the
    # submitted `graph` to that node's ancestor closure and runs it fresh (Run), "self_only"
    # runs *only* that node, seeding every other node's inputs from `seed_run_id`'s own
    # already-completed results (Re-run). `None` (the default) preserves today's
    # whole-graph behavior — every existing caller is unaffected.
    target_node_id: Optional[str] = None
    run_mode: Optional[Literal["ancestors", "self_only"]] = None
    seed_run_id: Optional[str] = None
    # Locked nodes: their results are reused (seeded from `seed_run_id`) and not recomputed,
    # so every run starts past the lock frontier. Composes with run_mode. Requires
    # `seed_run_id` (validated in routes/runs.py) to cover every locked id.
    locked_node_ids: list[str] = Field(default_factory=list)


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
    # This run's actual execution order/scope, once known (empty while still running or on
    # a structural pre-execution error) — see GraphRunResult.order's docstring for why this
    # is on the REST response too, not just the `run_order` WS event.
    order: list[str] = Field(default_factory=list)


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
    status: str  # "running" | "done" | "error" | "stopped" | legacy "stopping"
    dry_run: bool
    allow_live: bool
    n_checkpointed: int  # how many (item, metric) results are already in judge_results.jsonl


class DiskRunSummary(BaseModel):
    """A past run discovered on disk under logs/exps (for the Runs browser)."""
    run_id: str
    workflow_name: Optional[str] = None
    status: str
    finished_at: Optional[str] = None
    n_checkpointed: int = 0
    n_nodes: Optional[int] = None


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


class EngineHealthCheckIn(BaseModel):
    # Mirrors the LM Engine Node's params. `model` is optional — a null model falls back to
    # the text default inside `health.check_endpoint`, same as the CLI health check.
    engine_kind: str = "gpt"
    model: Optional[str] = None
    # A real endpoint ping is a billable gateway call, so it's gated exactly like every other
    # live path in this app — the frontend must pass True (after its own confirm) or the route
    # refuses with a 400, no call made.
    allow_live: bool = False


class EndpointHealthOut(BaseModel):
    url: str
    ok: bool
    status: Optional[int] = None  # HTTP status, or null when the request never completed
    latency: float
    error: Optional[str] = None


class EngineHealthCheckOut(BaseModel):
    endpoints: list[EndpointHealthOut] = Field(default_factory=list)
