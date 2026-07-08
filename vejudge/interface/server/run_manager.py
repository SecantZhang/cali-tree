"""Owns the ``ExperimentRun`` + ``CheckpointStore`` for one graph run.

Every graph run lands in the same ``logs/exps/<ts>-exps/`` shape as a CLI benchmark run
(``run.log``, ``llm-histories.log``, ``run_config.json``), tagged
``run_config["benchmark"] = "interface_graph"`` to distinguish it from ``"human_gap"``
CLI runs. The saved ``workflow_graph.json`` makes the run fully reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ... import config
from ...checkpoint import CheckpointStore
from ...logging.exp_logger import ExperimentRun, make_exp_run
from .graph import GraphSpec


def run_dir_for(run_id: str) -> Path:
    """The run directory a given run_id lives in — matches make_exp_run's naming."""
    return config.LOGS_ROOT / "exps" / f"{run_id}-exps"


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_run_config(run_dir: Path) -> Optional[dict[str, Any]]:
    return _read_json(run_dir / "run_config.json")


def load_workflow_graph(run_dir: Path) -> Optional[dict[str, Any]]:
    return _read_json(run_dir / "workflow_graph.json")


def load_run_status(run_dir: Path) -> Optional[dict[str, Any]]:
    return _read_json(run_dir / "run_status.json")


def count_checkpointed(run_dir: Path) -> int:
    path = run_dir / "judge_results.jsonl"
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def start_run(
    graph: GraphSpec,
    *,
    dry_run: bool,
    allow_live: bool,
    resume_from: Optional[Path] = None,
    workflow_name: Optional[str] = None,
) -> tuple[ExperimentRun, CheckpointStore]:
    run = make_exp_run(run_dir=Path(resume_from)) if resume_from else make_exp_run()

    cfg: dict[str, Any] = {
        "benchmark": "interface_graph",
        "dry_run": dry_run,
        "allow_live": allow_live,
        "n_nodes": len(graph.nodes),
        "node_types": [n.type for n in graph.nodes],
        "workflow_name": workflow_name,
    }
    # Resuming keeps the original config (matches the CLI's --continue behavior) — this is
    # also how workflow_name survives a resume without needing to be passed again.
    if not (resume_from and (run.run_dir / "run_config.json").is_file()):
        run.save_config(cfg)

    run.write_json(
        "workflow_graph.json",
        {
            "nodes": [{"id": n.id, "type": n.type, "params": n.params} for n in graph.nodes],
            "edges": [
                {
                    "source": e.source, "source_socket": e.source_socket,
                    "target": e.target, "target_socket": e.target_socket,
                }
                for e in graph.edges
            ],
        },
    )

    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")
    return run, checkpoint
