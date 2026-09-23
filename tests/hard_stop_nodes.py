"""Importable node executors used by spawned-worker lifecycle tests."""

from __future__ import annotations

import time

from vejudge.interface.server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


class HardStopSlowNode(NodeExecutor):
    node_type = "__stopfx_slow__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        time.sleep(float(ctx.params.get("delay", 0.3)))
        return NodeRunResult(outputs={"finished": True})


class HardStopMarkerNode(NodeExecutor):
    node_type = "__stopfx_marker__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        return NodeRunResult(outputs={"marker": True})


class ResumeMarkerNode(NodeExecutor):
    node_type = "__stopfx_resumeok__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        return NodeRunResult(outputs={"resumed": True})


class FinishedMarkerNode(NodeExecutor):
    node_type = "__stopfx_marker2__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        return NodeRunResult(outputs={"finished": True})


class WorkflowSlowNode(NodeExecutor):
    node_type = "__wf_slow__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        time.sleep(float(ctx.params.get("delay", 0.3)))
        return NodeRunResult(outputs={"finished": True})


class WorkflowMarkerNode(NodeExecutor):
    node_type = "__wf_marker__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        return NodeRunResult(outputs={"marker": True})


class CheckpointThenSleepNode(NodeExecutor):
    node_type = "__stopfx_checkpoint_sleep__"
    category = "node_db"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        ctx.checkpoint.put("completed-before-stop", {"ok": True})
        time.sleep(float(ctx.params.get("delay", 3.0)))
        ctx.checkpoint.put("must-not-exist-after-stop", {"ok": False})
        return NodeRunResult(outputs={"finished": True})


_EXECUTORS = (
    HardStopSlowNode, HardStopMarkerNode, ResumeMarkerNode, FinishedMarkerNode,
    WorkflowSlowNode, WorkflowMarkerNode, CheckpointThenSleepNode,
)


def register_worker_nodes() -> None:
    from vejudge.interface.server.registry import NODE_EXECUTORS

    for executor in _EXECUTORS:
        if executor.node_type not in NODE_EXECUTORS:
            register(executor)
