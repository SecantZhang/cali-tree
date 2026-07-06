"""In-memory registry of active/completed graph runs.

Single-process, local-only (no persistence across a server restart — the run's own
``logs/exps/<ts>-exps/`` directory is the durable record; this registry is just what
lets the API report live status and stream progress for a run still in this process).
Each run executes on a background thread so the FastAPI event loop is never blocked by
the node executors' blocking ``lm_engine`` HTTP calls.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from ...logging.exp_logger import ExperimentRun
from .executor import GraphExecutionEngine, GraphRunResult
from .graph import GraphSpec
from .run_manager import start_run


@dataclass
class RunHandle:
    run_id: str
    run: ExperimentRun
    events: "queue.Queue[dict[str, Any]]" = field(default_factory=queue.Queue)
    status: str = "running"  # "running" | "done" | "error"
    result: Optional[GraphRunResult] = None
    thread: Optional[threading.Thread] = None


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = threading.Lock()

    def start(self, graph: GraphSpec, *, dry_run: bool, allow_live: bool) -> RunHandle:
        run, checkpoint = start_run(graph, dry_run=dry_run, allow_live=allow_live)
        handle = RunHandle(run_id=run.run_id, run=run)

        def progress_cb(event: str, payload: dict[str, Any]) -> None:
            handle.events.put({"type": event, **payload})

        def _work() -> None:
            engine = GraphExecutionEngine(
                graph, run=run, checkpoint=checkpoint, dry_run=dry_run,
                allow_live=allow_live, progress_cb=progress_cb,
            )
            result = engine.execute()
            handle.result = result
            handle.status = result.status
            handle.events.put(
                {"type": "run_complete", "status": result.status, "error": result.error}
            )

        handle.thread = threading.Thread(target=_work, daemon=True)
        with self._lock:
            self._runs[handle.run_id] = handle
        handle.thread.start()
        return handle

    def get(self, run_id: str) -> Optional[RunHandle]:
        return self._runs.get(run_id)

    def list_ids(self) -> list[str]:
        return list(self._runs)


REGISTRY = RunRegistry()
