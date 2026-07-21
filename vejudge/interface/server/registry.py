"""Node executor contract + registry.

Only the in-scope node types (Peanut Source, Human Annotations, Dataset, Preprocessing,
Text/Video Judge, Eval — see ``interface.md``) register here. Concrete node modules
(``node_db.*``, ``node_preprocessing.*``, ``node_vejudge.*``, ``node_eval.*``) import
``register``/``NodeExecutor`` from this module and decorate their executor class; this
module never imports them back, so there's no import cycle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Optional

from ...checkpoint import CheckpointStore
from ...logging.exp_logger import ExperimentRun
from .graph import NodeTypeInfo


@dataclass
class NodeRunContext:
    """Everything a node executor needs to do its work for one graph run."""

    node_id: str
    params: dict[str, Any]
    inputs: dict[str, Any]  # keyed by this node's input socket name
    run: ExperimentRun
    checkpoint: CheckpointStore
    dry_run: bool = True
    allow_live: bool = False
    progress_cb: Optional[Callable[[str, dict[str, Any]], None]] = None
    # Cooperative cancellation remains useful to direct executor tests and non-interface
    # callers. Interface graph runs use a process boundary and hard-kill the whole worker,
    # since a thread blocked in a synchronous HTTP call cannot poll this callback.
    should_stop: Optional[Callable[[], bool]] = None
    # Streaming batch-eval hook (Judge Node only calls this today): a node whose output
    # arrives incrementally can call `on_batch(output_socket, partial_value)` at a batch
    # boundary to trigger a preview re-run of any directly-downstream node that opts in via
    # `NodeExecutor.supports_partial_input`. None for every node except the one the graph
    # executor is currently driving (see GraphExecutionEngine._run_node).
    on_batch: Optional[Callable[[str, Any], None]] = None
    # True only on the synthetic context GraphExecutionEngine builds to re-run a
    # `supports_partial_input` node against an in-flight upstream batch — never true for a
    # node's own normal, authoritative run at its regular position in topological order.
    is_preview: bool = False


@dataclass
class NodeRunResult:
    outputs: dict[str, Any] = field(default_factory=dict)  # keyed by output socket name
    status: str = "done"  # "done" | "error"
    error: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


class NodeExecutor(ABC):
    """Base class every in-scope node executor subclasses."""

    node_type: ClassVar[str]
    category: ClassVar[str]  # "node_db" | "node_vejudge" | "node_eval" | "node_calibration"
    # Optional finer grouping *within* a category (palette sub-folder). None = the node sits
    # flat under its category. Nodes sharing a subcategory play the same role and, by
    # convention, share one I/O contract via a role template (see node_calibration._templates).
    subcategory: ClassVar[Optional[str]] = None
    input_sockets: ClassVar[dict[str, str]] = {}
    output_sockets: ClassVar[dict[str, str]] = {}
    # Input sockets that accept fan-in — multiple incoming edges merged into a list of
    # values (see GraphExecutionEngine._run_node). All other sockets stay one-edge-only.
    multi_input_sockets: ClassVar[frozenset[str]] = frozenset()
    param_schema: ClassVar[dict[str, Any]] = {}
    # Opt-in for streaming batch-eval: only a node whose `run()` is cheap and safe to call
    # repeatedly against a growing, still-incomplete upstream input should set this True
    # (only EvalNodeExecutor does). GraphExecutionEngine uses this to decide which
    # downstream nodes get a preview re-run when an upstream node calls `ctx.on_batch`.
    supports_partial_input: ClassVar[bool] = False

    @abstractmethod
    def run(self, ctx: NodeRunContext) -> NodeRunResult: ...

    @classmethod
    def type_info(cls) -> NodeTypeInfo:
        return NodeTypeInfo(
            input_sockets=dict(cls.input_sockets),
            output_sockets=dict(cls.output_sockets),
            multi_input_sockets=frozenset(cls.multi_input_sockets),
        )


NODE_EXECUTORS: dict[str, type[NodeExecutor]] = {}


def register(executor_cls: type[NodeExecutor]) -> type[NodeExecutor]:
    """Class decorator: adds ``executor_cls`` to ``NODE_EXECUTORS`` under its ``node_type``."""
    if executor_cls.node_type in NODE_EXECUTORS:
        raise ValueError(f"Node type '{executor_cls.node_type}' is already registered")
    NODE_EXECUTORS[executor_cls.node_type] = executor_cls
    return executor_cls


def node_type_infos() -> dict[str, NodeTypeInfo]:
    """Socket shapes of every registered node type, for ``graph.validate_edges``."""
    return {t: cls.type_info() for t, cls in NODE_EXECUTORS.items()}
