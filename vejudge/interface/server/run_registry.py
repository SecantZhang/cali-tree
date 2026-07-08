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
from pathlib import Path
from typing import Any, Optional

from ...logging.exp_logger import ExperimentRun
from .executor import GraphExecutionEngine, GraphRunResult
from .graph import GraphSpec
from .run_manager import start_run
from .schemas import utcnow_iso


@dataclass
class RunHandle:
    run_id: str
    run: ExperimentRun
    events: "queue.Queue[dict[str, Any]]" = field(default_factory=queue.Queue)
    status: str = "running"  # "running" | "stopping" | "done" | "error" | "stopped"
    result: Optional[GraphRunResult] = None
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = threading.Lock()
        # Run directories currently being resumed — guards against two tabs resuming the
        # same run dir concurrently, which would race two independent CheckpointStore
        # instances against the same judge_results.jsonl file.
        self._active_resume_dirs: set[Path] = set()

    def try_claim_resume_dir(self, run_dir: Path) -> bool:
        with self._lock:
            if run_dir in self._active_resume_dirs:
                return False
            self._active_resume_dirs.add(run_dir)
            return True

    def release_resume_dir(self, run_dir: Path) -> None:
        with self._lock:
            self._active_resume_dirs.discard(run_dir)

    def start(
        self,
        graph: GraphSpec,
        *,
        dry_run: bool,
        allow_live: bool,
        resume_from: Optional[Path] = None,
        workflow_name: Optional[str] = None,
    ) -> RunHandle:
        run, checkpoint = start_run(
            graph, dry_run=dry_run, allow_live=allow_live,
            resume_from=resume_from, workflow_name=workflow_name,
        )
        handle = RunHandle(run_id=run.run_id, run=run)

        def progress_cb(event: str, payload: dict[str, Any]) -> None:
            handle.events.put({"type": event, **payload})

        def _work() -> None:
            try:
                engine = GraphExecutionEngine(
                    graph, run=run, checkpoint=checkpoint, dry_run=dry_run,
                    allow_live=allow_live, progress_cb=progress_cb,
                    should_stop=handle.stop_event.is_set,
                )
                result = engine.execute()
            finally:
                # Release BEFORE handle.status goes terminal below — otherwise another
                # thread polling handle.status could observe "done" and immediately try
                # (and wrongly fail) to claim this same resume dir a moment before it's
                # actually released.
                if resume_from is not None:
                    with self._lock:
                        self._active_resume_dirs.discard(resume_from)
            handle.result = result
            handle.status = result.status
            run.write_json(
                "run_status.json",
                {"status": result.status, "error": result.error, "finished_at": utcnow_iso()},
            )
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

    def find_active_for_dir(self, run_dir: Path) -> Optional[RunHandle]:
        """The in-flight handle (if any) currently working in ``run_dir``.

        A resumed run gets its own fresh run_id/handle, sharing only the run directory
        with the original attempt — that original handle's `.status` stays frozen at
        whatever it was when it stopped/errored, forever, since nothing else ever updates
        it. Looking this up by directory (not by the original run_id) is what lets a
        caller correctly prefer "there's a resume in flight right now" over "here's what
        the very first attempt at this directory finished as."
        """
        for handle in self._runs.values():
            if handle.run.run_dir == run_dir and handle.status in ("running", "stopping"):
                return handle
        return None

    def list_ids(self) -> list[str]:
        return list(self._runs)

    def request_stop(self, run_id: str) -> bool:
        """Ask a running graph to stop gracefully. Returns False if there's nothing to stop."""
        handle = self._runs.get(run_id)
        if handle is None or handle.status != "running":
            return False
        handle.status = "stopping"
        handle.stop_event.set()
        handle.events.put({"type": "run_status", "status": "stopping"})
        return True


REGISTRY = RunRegistry()
