"""Spawned graph-run worker used by :mod:`run_registry`.

The FastAPI process owns lifecycle and API state. This module owns only blocking graph
execution, deliberately behind an OS process boundary so Stop can terminate a request
that is blocked inside ``requests.post`` (something Python threads cannot do safely).
"""

from __future__ import annotations

import importlib
import os
import pickle
from pathlib import Path
from typing import Any

from ...checkpoint import CheckpointStore
from ...logging.exp_logger import make_exp_run
from .executor import GraphExecutionEngine, GraphRunResult


def run_graph_worker(
    job_path: str,
    result_path: str,
    event_queue: Any,
) -> None:
    """Execute one serialized graph job and atomically publish its final result."""
    # Put the worker and any local descendants (ffmpeg, future helper processes, etc.) in
    # their own group. The parent checks the group id before killpg, so a rare setsid
    # failure can never target the FastAPI server's own group.
    if os.name == "posix":
        try:
            os.setsid()
        except OSError:
            pass

    with open(job_path, "rb") as f:
        job = pickle.load(f)

    # Test/plugin executors that are registered outside the built-in node_types import can
    # opt into the spawned interpreter explicitly. Production built-ins need no entries.
    for module in job.get("worker_imports", []):
        imported = importlib.import_module(module)
        hook = getattr(imported, "register_worker_nodes", None)
        if hook is not None:
            hook()

    run = make_exp_run(run_id=job["run_id"], run_dir=Path(job["run_dir"]))
    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")

    def progress(event: str, payload: dict[str, Any]) -> None:
        event_queue.put({"type": event, **payload})

    def completed_node(node_id: str, result: Any) -> None:
        # Private IPC event: the parent records it but never forwards the potentially
        # large output payload over the browser websocket.
        event_queue.put({"type": "__node_result__", "node_id": node_id, "result": result})

    try:
        engine = GraphExecutionEngine(
            job["graph"], run=run, checkpoint=checkpoint,
            dry_run=job["dry_run"], allow_live=job["allow_live"],
            progress_cb=progress, node_result_cb=completed_node,
            target_node_id=job.get("target_node_id"),
            seed_results=job.get("seed_results"),
            seed_node_ids=job.get("seed_node_ids"),
        )
        result = engine.execute()
    except BaseException as exc:  # process boundary: always give the parent a result
        result = GraphRunResult(status="error", error=f"{type(exc).__name__}: {exc}")
    finally:
        run.close()

    target = Path(result_path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
