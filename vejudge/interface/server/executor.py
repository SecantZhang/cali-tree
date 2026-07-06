"""Graph execution engine: sequential topological execution of Dataset/Judge/Eval nodes.

Runs the whole graph inline (blocking). The caller (the FastAPI run route, once it
exists) is responsible for running this on a background thread so it doesn't block the
event loop, since node executors make blocking ``lm_engine`` calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ...checkpoint import CheckpointStore
from ...logging.exp_logger import ExperimentRun
from .. import node_types  # noqa: F401 - import side effect: registers dataset/judge/eval
from .graph import GraphError, GraphSpec, NodeSpec, topological_sort, validate_edges
from .registry import NODE_EXECUTORS, NodeRunContext, NodeRunResult, node_type_infos

ProgressCb = Callable[[str, dict[str, Any]], None]


@dataclass
class GraphRunResult:
    status: str  # "done" | "error"
    node_results: dict[str, NodeRunResult] = field(default_factory=dict)
    error: Optional[str] = None


class GraphExecutionEngine:
    """Validates, topo-sorts, then runs a graph node-by-node against real inputs/outputs."""

    def __init__(
        self,
        graph: GraphSpec,
        *,
        run: ExperimentRun,
        checkpoint: CheckpointStore,
        dry_run: bool = True,
        allow_live: bool = False,
        progress_cb: Optional[ProgressCb] = None,
    ) -> None:
        self.graph = graph
        self.run = run
        self.checkpoint = checkpoint
        self.dry_run = dry_run
        self.allow_live = allow_live
        self.progress_cb = progress_cb

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_cb:
            self.progress_cb(event, payload)

    def execute(self) -> GraphRunResult:
        try:
            validate_edges(self.graph, node_type_infos())
            order = topological_sort(self.graph)
        except GraphError as e:
            return GraphRunResult(status="error", error=str(e))

        nodes_by_id = {n.id: n for n in self.graph.nodes}
        # incoming[node_id] = [(target_socket, source_node_id, source_socket), ...]
        incoming: dict[str, list[tuple[str, str, str]]] = {n.id: [] for n in self.graph.nodes}
        for e in self.graph.edges:
            incoming[e.target].append((e.target_socket, e.source, e.source_socket))

        node_results: dict[str, NodeRunResult] = {}
        overall_status = "done"

        for node_id in order:
            node = nodes_by_id[node_id]
            self._emit("node_status", {"node_id": node_id, "status": "running"})
            result = self._run_node(node, node_id, incoming[node_id], node_results)
            node_results[node_id] = result

            if result.status == "error":
                overall_status = "error"
                self.run.logger.warning(
                    "Node '%s' (%s) failed: %s", node_id, node.type, result.error
                )
            self._emit(
                "node_status",
                {"node_id": node_id, "status": result.status, "error": result.error},
            )

        return GraphRunResult(status=overall_status, node_results=node_results)

    def _run_node(
        self,
        node: NodeSpec,
        node_id: str,
        incoming: list[tuple[str, str, str]],
        node_results: dict[str, NodeRunResult],
    ) -> NodeRunResult:
        inputs: dict[str, Any] = {}
        for target_socket, src_id, src_socket in incoming:
            src_result = node_results.get(src_id)
            if (
                src_result is None
                or src_result.status == "error"
                or src_socket not in src_result.outputs
            ):
                return NodeRunResult(
                    status="error",
                    error=f"Upstream node '{src_id}' did not produce output '{src_socket}'",
                )
            inputs[target_socket] = src_result.outputs[src_socket]

        executor_cls = NODE_EXECUTORS[node.type]
        ctx = NodeRunContext(
            node_id=node_id,
            params=dict(node.params),
            inputs=inputs,
            run=self.run,
            checkpoint=self.checkpoint,
            dry_run=self.dry_run,
            allow_live=self.allow_live,
            progress_cb=lambda event, payload, _nid=node_id: self._emit(
                event, {**payload, "node_id": _nid}
            ),
        )
        try:
            return executor_cls().run(ctx)
        except Exception as e:  # noqa: BLE001 - one node's bug must not crash the whole run
            return NodeRunResult(status="error", error=f"{type(e).__name__}: {e}")
