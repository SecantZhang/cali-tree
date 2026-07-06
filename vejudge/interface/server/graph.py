"""Graph model: node/edge specs, socket type-checking, and topological execution order.

Pure data + pure functions — no I/O, no dependency on the node-executor registry, so it's
testable with synthetic node types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeSpec:
    id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    source_socket: str
    target: str
    target_socket: str


@dataclass(frozen=True)
class GraphSpec:
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]


@dataclass(frozen=True)
class NodeTypeInfo:
    """The socket shape of a node type, decoupled from its executor's runtime code."""

    input_sockets: dict[str, str]
    output_sockets: dict[str, str]


class GraphError(ValueError):
    """A graph fails validation: unknown node/type/socket, type mismatch, or a cycle."""


def validate_edges(graph: GraphSpec, node_types: dict[str, NodeTypeInfo]) -> None:
    """Raise ``GraphError`` on the first structural problem found; otherwise return None."""
    node_by_id = {n.id: n for n in graph.nodes}
    if len(node_by_id) != len(graph.nodes):
        raise GraphError("Duplicate node ids in graph")

    for n in graph.nodes:
        if n.type not in node_types:
            raise GraphError(f"Unknown node type '{n.type}' on node '{n.id}'")

    seen_targets: set[tuple[str, str]] = set()
    for e in graph.edges:
        src = node_by_id.get(e.source)
        tgt = node_by_id.get(e.target)
        if src is None:
            raise GraphError(f"Edge references unknown source node '{e.source}'")
        if tgt is None:
            raise GraphError(f"Edge references unknown target node '{e.target}'")

        src_type = node_types.get(src.type)
        tgt_type = node_types.get(tgt.type)
        if src_type is None:
            raise GraphError(f"Unknown node type '{src.type}' on node '{src.id}'")
        if tgt_type is None:
            raise GraphError(f"Unknown node type '{tgt.type}' on node '{tgt.id}'")

        if e.source_socket not in src_type.output_sockets:
            raise GraphError(
                f"Node '{src.id}' ({src.type}) has no output socket '{e.source_socket}'"
            )
        if e.target_socket not in tgt_type.input_sockets:
            raise GraphError(
                f"Node '{tgt.id}' ({tgt.type}) has no input socket '{e.target_socket}'"
            )

        src_socket_type = src_type.output_sockets[e.source_socket]
        tgt_socket_type = tgt_type.input_sockets[e.target_socket]
        if src_socket_type != tgt_socket_type:
            raise GraphError(
                f"Type mismatch: {src.id}.{e.source_socket} ({src_socket_type}) -> "
                f"{tgt.id}.{e.target_socket} ({tgt_socket_type})"
            )

        key = (e.target, e.target_socket)
        if key in seen_targets:
            raise GraphError(
                f"Input socket '{e.target_socket}' on node '{e.target}' already has an "
                "incoming edge (fan-in is not supported)"
            )
        seen_targets.add(key)


def topological_sort(graph: GraphSpec) -> list[str]:
    """Kahn's algorithm, deterministic tie-break by node id. Raises ``GraphError`` on a cycle."""
    node_ids = [n.id for n in graph.nodes]
    if len(set(node_ids)) != len(node_ids):
        raise GraphError("Duplicate node ids in graph")

    indegree = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in graph.edges:
        adjacency[e.source].append(e.target)
        indegree[e.target] += 1

    ready = sorted(nid for nid, d in indegree.items() if d == 0)
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        newly_ready = []
        for nxt in adjacency[nid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                newly_ready.append(nxt)
        ready = sorted(ready + newly_ready)

    if len(order) != len(node_ids):
        remaining = sorted(set(node_ids) - set(order))
        raise GraphError(f"Graph has a cycle involving: {remaining}")
    return order
