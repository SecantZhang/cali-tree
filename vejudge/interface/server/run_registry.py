"""In-memory registry of active/completed graph runs.

Each graph executes in a dedicated spawned process. The process boundary is intentional:
an LM request blocks in synchronous ``requests.post`` and Python cannot safely interrupt
that work when it lives in a thread. A per-run process group makes Stop a real hard cancel
while the FastAPI parent remains responsive and owns all public run state.
"""

from __future__ import annotations

import multiprocessing
import os
import pickle
import queue
import signal
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...logging.exp_logger import ExperimentRun
from .executor import GraphRunResult
from .graph import GraphSpec, topological_sort
from .registry import NodeRunResult
from .run_manager import save_run_results, start_run
from .run_worker import run_graph_worker
from .schemas import utcnow_iso


@dataclass
class RunHandle:
    run_id: str
    run: ExperimentRun
    events: "queue.Queue[dict[str, Any]]" = field(default_factory=queue.Queue)
    status: str = "running"  # "running" | "done" | "error" | "stopped"
    result: Optional[GraphRunResult] = None
    process: Optional[multiprocessing.Process] = None
    monitor_thread: Optional[threading.Thread] = None
    relay_thread: Optional[threading.Thread] = None
    worker_events: Any = None
    execution_order: list[str] = field(default_factory=list)
    completed_results: dict[str, NodeRunResult] = field(default_factory=dict)
    seed_results: dict[str, NodeRunResult] = field(default_factory=dict)
    resume_from: Optional[Path] = None
    job_path: Optional[Path] = None
    result_path: Optional[Path] = None
    stop_requested: bool = False


class RunRegistry:
    def __init__(self, *, worker_imports: Optional[list[str]] = None) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = threading.Lock()
        self._mp = multiprocessing.get_context("spawn")
        # Additional importable executor-registration modules. Empty in production; used
        # by process-lifecycle tests and available to future plugin bootstrap code.
        self.worker_imports = list(worker_imports or [])
        # Run directories currently being resumed — prevents concurrent writers to one
        # append-only checkpoint. Hard Stop releases the claim as soon as SIGKILL is sent.
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
        target_node_id: Optional[str] = None,
        seed_results: Optional[dict[str, NodeRunResult]] = None,
        seed_node_ids: Optional[set[str]] = None,
    ) -> RunHandle:
        run, _checkpoint = start_run(
            graph, dry_run=dry_run, allow_live=allow_live,
            resume_from=resume_from, workflow_name=workflow_name,
        )
        order = topological_sort(graph)
        if seed_results is not None and target_node_id is not None:
            order = [target_node_id]
        if seed_node_ids:
            order = [node_id for node_id in order if node_id not in seed_node_ids]

        token = uuid.uuid4().hex
        job_path = run.run_dir / f".worker-{token}.job.pkl"
        result_path = run.run_dir / f".worker-{token}.result.pkl"
        job = {
            "run_id": run.run_id,
            "run_dir": str(run.run_dir),
            "graph": graph,
            "dry_run": dry_run,
            "allow_live": allow_live,
            "target_node_id": target_node_id,
            "seed_results": dict(seed_results or {}),
            "seed_node_ids": set(seed_node_ids or set()),
            "worker_imports": list(self.worker_imports),
        }
        with job_path.open("wb") as f:
            pickle.dump(job, f, protocol=pickle.HIGHEST_PROTOCOL)

        worker_events = self._mp.Queue()
        process = self._mp.Process(
            target=run_graph_worker,
            args=(str(job_path), str(result_path), worker_events),
            daemon=True,
            name=f"vejudge-run-{run.run_id}",
        )
        handle = RunHandle(
            run_id=run.run_id,
            run=run,
            process=process,
            worker_events=worker_events,
            execution_order=order,
            seed_results=dict(seed_results or {}),
            completed_results=dict(seed_results or {}),
            resume_from=resume_from,
            job_path=job_path,
            result_path=result_path,
        )

        # The parent never logs graph work; close its handler before the child opens the
        # same run.log. Durable JSON helpers on ExperimentRun remain usable after close().
        run.close()
        with self._lock:
            self._runs[handle.run_id] = handle
        try:
            process.start()
        except Exception:
            with self._lock:
                self._runs.pop(handle.run_id, None)
                if resume_from is not None:
                    self._active_resume_dirs.discard(resume_from)
            self._cleanup_worker_files(handle)
            raise

        handle.relay_thread = threading.Thread(
            target=self._relay_worker_events, args=(handle,), daemon=True,
            name=f"vejudge-events-{run.run_id}",
        )
        handle.monitor_thread = threading.Thread(
            target=self._monitor_worker, args=(handle,), daemon=True,
            name=f"vejudge-monitor-{run.run_id}",
        )
        handle.relay_thread.start()
        handle.monitor_thread.start()
        return handle

    def _relay_worker_events(self, handle: RunHandle) -> None:
        """Copy child IPC events into the browser queue and retain completed outputs."""
        process = handle.process
        while process is not None:
            try:
                event = handle.worker_events.get(timeout=0.05)
            except queue.Empty:
                if not process.is_alive():
                    # One final non-blocking drain handles messages already flushed by the
                    # multiprocessing queue's feeder thread as the worker exited.
                    try:
                        event = handle.worker_events.get_nowait()
                    except queue.Empty:
                        break
                else:
                    continue
            if event.get("type") == "__node_result__":
                with self._lock:
                    handle.completed_results[event["node_id"]] = event["result"]
                continue
            handle.events.put(event)

    def _monitor_worker(self, handle: RunHandle) -> None:
        process = handle.process
        if process is None:
            return
        process.join()
        if handle.relay_thread is not None:
            handle.relay_thread.join(timeout=1.0)

        with self._lock:
            stopped = handle.stop_requested
        if stopped:
            self._cleanup_worker_files(handle)
            return

        result: GraphRunResult
        try:
            if handle.result_path is None or not handle.result_path.is_file():
                raise RuntimeError(f"worker exited with code {process.exitcode} without a result")
            with handle.result_path.open("rb") as f:
                result = pickle.load(f)
        except Exception as exc:  # noqa: BLE001 - worker boundary becomes a run error
            result = GraphRunResult(
                status="error", error=f"Run worker failed: {type(exc).__name__}: {exc}",
                node_results=dict(handle.completed_results), order=list(handle.execution_order),
            )

        with self._lock:
            # Stop can race a normal worker exit. Once stop_requested wins, its terminal
            # snapshot is authoritative and must never be overwritten by this monitor.
            if handle.stop_requested:
                self._cleanup_worker_files(handle)
                return
            handle.result = result
            # Persist before publishing the terminal in-memory status. A GET that observes
            # `done` can therefore immediately open the Runs tab without racing an absent
            # run_status.json and seeing the same run misclassified as `interrupted`.
            self._persist_terminal(handle, result)
            handle.status = result.status
            if handle.resume_from is not None:
                self._active_resume_dirs.discard(handle.resume_from)
        handle.events.put(
            {"type": "run_complete", "status": result.status, "error": result.error}
        )
        self._cleanup_worker_files(handle)

    @staticmethod
    def _cleanup_worker_files(handle: RunHandle) -> None:
        result_tmp = (
            handle.result_path.with_suffix(handle.result_path.suffix + ".tmp")
            if handle.result_path is not None else None
        )
        for path in (handle.job_path, handle.result_path, result_tmp):
            if path is not None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        try:
            handle.worker_events.close()
        except (AttributeError, OSError, ValueError):
            pass

    @staticmethod
    def _persist_terminal(handle: RunHandle, result: GraphRunResult) -> None:
        handle.run.write_json(
            "run_status.json",
            {"status": result.status, "error": result.error, "finished_at": utcnow_iso()},
        )
        save_run_results(handle.run, result.node_results, result.order)

    @staticmethod
    def _kill_worker(process: multiprocessing.Process) -> None:
        if process.pid is None or not process.is_alive():
            return
        if os.name == "posix":
            try:
                # Only killpg when the worker successfully became its own group leader.
                # Otherwise kill just the process; never risk the server's process group.
                if os.getpgid(process.pid) == process.pid:
                    os.killpg(process.pid, signal.SIGKILL)
                    return
            except ProcessLookupError:
                return
            except OSError:
                pass
        try:
            process.kill()
        except (AttributeError, ProcessLookupError):
            process.terminate()

    def get(self, run_id: str) -> Optional[RunHandle]:
        return self._runs.get(run_id)

    def find_active_for_dir(self, run_dir: Path) -> Optional[RunHandle]:
        for handle in self._runs.values():
            if handle.run.run_dir == run_dir and handle.status == "running":
                return handle
        return None

    def list_ids(self) -> list[str]:
        return list(self._runs)

    def request_stop(self, run_id: str) -> bool:
        """Hard-kill a running worker and publish a terminal snapshot immediately."""
        with self._lock:
            handle = self._runs.get(run_id)
            if handle is None or handle.status != "running" or handle.stop_requested:
                return False
            handle.stop_requested = True
            completed = dict(handle.completed_results)
            result = GraphRunResult(
                status="stopped", node_results=completed,
                order=list(handle.execution_order),
            )
            stopped_ids: list[str] = []
            for node_id in handle.execution_order:
                if node_id not in result.node_results:
                    result.node_results[node_id] = NodeRunResult(status="stopped")
                    stopped_ids.append(node_id)

        # SIGKILL is a signal, not a join: this does not wait for the blocked request or
        # its timeout. The monitor thread reaps the process asynchronously.
        if handle.process is not None:
            self._kill_worker(handle.process)
        self._persist_terminal(handle, result)
        with self._lock:
            # Publish terminal state only after the kill signal and durable snapshot. This
            # also keeps Resume from entering the shared directory before the old worker
            # has been told to die.
            handle.result = result
            handle.status = "stopped"
            if handle.resume_from is not None:
                self._active_resume_dirs.discard(handle.resume_from)
        for node_id in stopped_ids:
            handle.events.put({"type": "node_status", "node_id": node_id, "status": "stopped"})
        handle.events.put({"type": "run_complete", "status": "stopped", "error": None})
        return True


REGISTRY = RunRegistry()
