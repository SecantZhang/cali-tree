"""Graph execution engine: sequential topological execution of Dataset/Judge/Eval nodes.

Runs the whole graph inline (blocking). The interface registry invokes it inside a
dedicated spawned worker process so blocking ``lm_engine`` calls neither block FastAPI nor
prevent immediate hard cancellation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ...checkpoint import CheckpointStore
from ...logging.exp_logger import ExperimentRun
from .. import node_types  # noqa: F401 - import side effect: registers dataset/judge/eval
from .graph import GraphError, GraphSpec, NodeSpec, topological_sort, validate_edges
from .registry import NODE_EXECUTORS, NodeRunContext, NodeRunResult, node_type_infos

ProgressCb = Callable[[str, dict[str, Any]], None]
NodeResultCb = Callable[[str, "NodeRunResult"], None]


@dataclass
class GraphRunResult:
    status: str  # "done" | "error" | "stopped"
    node_results: dict[str, NodeRunResult] = field(default_factory=dict)
    error: Optional[str] = None
    # This run's actual execution order/scope (Jupyter-style order badge — see
    # NodeChrome.tsx). Also carried here, not just as the `run_order` WS event, so a run
    # that finishes before the frontend's websocket even connects (common for a tiny/dry
    # run) still has a way to learn it, via the plain REST response.
    order: list[str] = field(default_factory=list)


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
        node_result_cb: Optional[NodeResultCb] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        # Per-node Re-run (self_only mode — see schemas.RunRequest): when both are set,
        # `graph` stays the FULL graph (so this node's real upstream edges still resolve),
        # but only `target_node_id` actually executes — `seed_results` pre-populates every
        # other node's outputs from a prior run, standing in for a real execution. Per-node
        # Run (ancestors mode) needs no engine changes at all: the caller (routes/runs.py)
        # just passes an already-reduced `graph` (see graph.ancestors_closure) and leaves
        # these two None, so it runs like any other whole-graph execution.
        target_node_id: Optional[str] = None,
        seed_results: Optional[dict[str, NodeRunResult]] = None,
        # Locked nodes: any node id in this set is *seeded* from `seed_results` (its prior
        # result reused) and NOT executed — every run starts past the lock frontier. A
        # generalization of the self_only single-target skip to an arbitrary set; the two
        # compose (self_only reduces `order` to the target, then locked ids are filtered out
        # of whatever remains). Requires `seed_results` to cover every id here (the route
        # validates that up front).
        seed_node_ids: Optional[set[str]] = None,
    ) -> None:
        self.graph = graph
        self.run = run
        self.checkpoint = checkpoint
        self.dry_run = dry_run
        self.allow_live = allow_live
        self.progress_cb = progress_cb
        self.node_result_cb = node_result_cb
        self.should_stop = should_stop
        self.target_node_id = target_node_id
        self.seed_results = seed_results
        self.seed_node_ids = seed_node_ids or set()

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self.progress_cb:
            self.progress_cb(event, payload)

    def execute(self) -> GraphRunResult:
        try:
            validate_edges(self.graph, node_type_infos())
            order = topological_sort(self.graph)
        except GraphError as e:
            return GraphRunResult(status="error", error=str(e))

        # Re-run (self_only): only the target node actually executes — everything else's
        # output comes from `seed_results` instead, so this run's real scope is just that
        # one node. `run_order` is emitted against the actual execution order (after this
        # reduction, not before) so the frontend's order badge reflects what this specific
        # run actually did, per-node — a Run (ancestors mode) or a normal whole-graph run
        # never hits this branch, so their emitted order is the full (possibly
        # already-reduced-by-the-caller) topological order.
        if self.seed_results is not None and self.target_node_id is not None:
            order = [self.target_node_id]
        # Locked nodes are seeded (their prior output is already in `node_results` below) and
        # never executed — so a global run, or a per-node Run whose ancestor closure includes
        # locked nodes, starts at the first unlocked node past the lock frontier.
        if self.seed_node_ids:
            order = [n for n in order if n not in self.seed_node_ids]
        self._emit("run_order", {"order": order})

        nodes_by_id = {n.id: n for n in self.graph.nodes}
        # incoming[node_id] = [(target_socket, source_node_id, source_socket), ...]
        incoming: dict[str, list[tuple[str, str, str]]] = {n.id: [] for n in self.graph.nodes}
        # outgoing[node_id] = [(source_socket, target_node_id, target_socket), ...] — the
        # mirror of `incoming`, used only to find a node's direct downstream neighbors for
        # streaming batch-eval previews (see `_run_node`'s `on_batch` closure).
        outgoing: dict[str, list[tuple[str, str, str]]] = {n.id: [] for n in self.graph.nodes}
        for e in self.graph.edges:
            incoming[e.target].append((e.target_socket, e.source, e.source_socket))
            outgoing[e.source].append((e.source_socket, e.target, e.target_socket))

        node_results: dict[str, NodeRunResult] = dict(self.seed_results or {})
        overall_status = "done"
        # Wall-clock origin for per-node timing: each node records its elapsed run time and
        # its start offset from here, so the Timing tab can lay out a whole-run waterfall.
        run_start = time.perf_counter()

        for i, node_id in enumerate(order):
            if self.should_stop and self.should_stop():
                # Cooperative path for direct/non-process callers. Interface runs normally
                # stop by terminating their isolated worker, so they do not wait here.
                for remaining_id in order[i:]:
                    node_results[remaining_id] = NodeRunResult(status="stopped")
                    self._emit("node_status", {"node_id": remaining_id, "status": "stopped"})
                if overall_status != "error":
                    overall_status = "stopped"
                break

            node = nodes_by_id[node_id]
            self._emit("node_status", {"node_id": node_id, "status": "running"})
            result = self._run_node(
                node, node_id, incoming, outgoing, node_results, nodes_by_id, run_start
            )
            node_results[node_id] = result
            if self.node_result_cb:
                # The process-backed interface runner uses this private callback to copy
                # each fully completed node result back to the parent. If a later node is
                # hard-killed, already-finished outputs remain available for inspection
                # and safe locked-node reuse instead of being reduced to status-only data.
                self.node_result_cb(node_id, result)

            if result.status == "error":
                overall_status = "error"
                self.run.logger.warning(
                    "Node '%s' (%s) failed: %s", node_id, node.type, result.error
                )
            elif result.status == "stopped" and overall_status != "error":
                overall_status = "stopped"
            self._emit(
                "node_status",
                {"node_id": node_id, "status": result.status, "error": result.error,
                 "elapsed_ms": result.meta.get("elapsed_ms")},
            )

        return GraphRunResult(status=overall_status, node_results=node_results, order=order)

    def _run_node(
        self,
        node: NodeSpec,
        node_id: str,
        incoming_map: dict[str, list[tuple[str, str, str]]],
        outgoing_map: dict[str, list[tuple[str, str, str]]],
        node_results: dict[str, NodeRunResult],
        nodes_by_id: dict[str, NodeSpec],
        run_start: float = 0.0,
    ) -> NodeRunResult:
        incoming = incoming_map[node_id]
        executor_cls = NODE_EXECUTORS[node.type]
        multi = executor_cls.multi_input_sockets
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
            value = src_result.outputs[src_socket]
            # A fan-in socket collects every incoming edge's value into a list (order =
            # edge order); a normal socket takes the single value (last edge wins, but
            # validate_edges already forbids >1 edge on a non-multi socket).
            if target_socket in multi:
                inputs.setdefault(target_socket, []).append(value)
            else:
                inputs[target_socket] = value

        def on_batch(source_socket: str, value: Any, _nid: str = node_id) -> None:
            # The calling node's own in-flight snapshot, not just downstream previews
            # (below) — lets e.g. the Judge Node's own secondary tab render a live,
            # updating view (a score histogram) of its own partial results, not only the
            # final result once the whole node finishes.
            self._emit("partial_result", {"node_id": _nid, "outputs": {source_socket: value}, "meta": {}})
            self._emit_partial_previews(
                _nid, source_socket, value, incoming_map, outgoing_map, node_results, nodes_by_id
            )

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
            should_stop=self.should_stop,
            on_batch=on_batch,
        )
        t0 = time.perf_counter()
        try:
            result = executor_cls().run(ctx)
        except Exception as e:  # noqa: BLE001 - one node's bug must not crash the whole run
            result = NodeRunResult(status="error", error=f"{type(e).__name__}: {e}")
        # Per-node timing, stamped centrally so EVERY node type (current + future) gets it
        # with no per-node code: total run time + start offset from the run origin (for the
        # Timing tab's whole-run waterfall). Reads back on the client via NodeResultOut.meta.
        result.meta["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result.meta["start_offset_ms"] = round((t0 - run_start) * 1000, 1)
        return result

    def _emit_partial_previews(
        self,
        source_node_id: str,
        source_socket: str,
        value: Any,
        incoming_map: dict[str, list[tuple[str, str, str]]],
        outgoing_map: dict[str, list[tuple[str, str, str]]],
        node_results: dict[str, NodeRunResult],
        nodes_by_id: dict[str, NodeSpec],
    ) -> None:
        """Re-runs every direct, `supports_partial_input` downstream node against an
        in-flight batch and emits its preview as a `partial_result` event.

        Every other node's normal, authoritative single-shot `run()` call at its regular
        position in topological order is completely unaffected by this — it's a pure side
        effect layered on top of the existing contract, triggered only by a node calling
        `ctx.on_batch` (today, only the Judge Node does).
        """
        for out_socket, target_id, target_socket in outgoing_map.get(source_node_id, []):
            if out_socket != source_socket:
                continue
            target_node = nodes_by_id.get(target_id)
            target_cls = NODE_EXECUTORS.get(target_node.type) if target_node else None
            if target_node is None or target_cls is None or not target_cls.supports_partial_input:
                continue

            preview_inputs: dict[str, Any] = {}
            inputs_ready = True
            for t_socket, t_src_id, t_src_socket in incoming_map.get(target_id, []):
                if t_socket == target_socket and t_src_id == source_node_id:
                    preview_inputs[t_socket] = value
                    continue
                src_result = node_results.get(t_src_id)
                if src_result is None or t_src_socket not in src_result.outputs:
                    inputs_ready = False
                    break
                preview_inputs[t_socket] = src_result.outputs[t_src_socket]
            if not inputs_ready:
                continue

            preview_ctx = NodeRunContext(
                node_id=target_id,
                params=dict(target_node.params),
                inputs=preview_inputs,
                run=self.run,
                checkpoint=self.checkpoint,
                dry_run=self.dry_run,
                allow_live=self.allow_live,
                is_preview=True,
            )
            try:
                preview_result = target_cls().run(preview_ctx)
            except Exception as e:  # noqa: BLE001 - a broken preview must not break the real run
                self.run.logger.warning(
                    "Partial preview for '%s' failed: %s: %s", target_id, type(e).__name__, e
                )
                continue
            if preview_result.status == "error":
                # A node whose input_sockets declare more than what's actually wired in the
                # graph (e.g. an Eval Node with no `labels` edge at all) can validate that
                # itself and return an error — `_run_node`'s edge-resolution check above
                # only covers sockets that *are* wired, not every socket the node declares.
                # An error preview has nothing useful to show, so it's simply dropped here.
                continue
            self._emit(
                "partial_result",
                {
                    "node_id": target_id,
                    "outputs": preview_result.outputs,
                    "meta": preview_result.meta,
                },
            )
