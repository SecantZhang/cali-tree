"""Node executor contract + registry.

Only the 3 in-scope node types (Dataset, Judge, Eval — see ``interface.md``) register here.
Concrete node modules (``node_db.dataset_node``, ``node_vejudge.judge_node``,
``node_eval.eval_node``) import ``register``/``NodeExecutor`` from this module and decorate
their executor class; this module never imports them back, so there's no import cycle.
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


@dataclass
class NodeRunResult:
    outputs: dict[str, Any] = field(default_factory=dict)  # keyed by output socket name
    status: str = "done"  # "done" | "error"
    error: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


class NodeExecutor(ABC):
    """Base class every in-scope node executor subclasses."""

    node_type: ClassVar[str]
    category: ClassVar[str]  # "node_db" | "node_vejudge" | "node_eval"
    input_sockets: ClassVar[dict[str, str]] = {}
    output_sockets: ClassVar[dict[str, str]] = {}
    param_schema: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def run(self, ctx: NodeRunContext) -> NodeRunResult: ...

    @classmethod
    def type_info(cls) -> NodeTypeInfo:
        return NodeTypeInfo(
            input_sockets=dict(cls.input_sockets), output_sockets=dict(cls.output_sockets)
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
