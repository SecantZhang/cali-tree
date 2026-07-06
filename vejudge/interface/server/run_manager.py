"""Owns the ``ExperimentRun`` + ``CheckpointStore`` for one graph run.

Every graph run lands in the same ``logs/exps/<ts>-exps/`` shape as a CLI benchmark run
(``run.log``, ``llm-histories.log``, ``run_config.json``), tagged
``run_config["benchmark"] = "interface_graph"`` to distinguish it from ``"human_gap"``
CLI runs. The saved ``workflow_graph.json`` makes the run fully reproducible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ...checkpoint import CheckpointStore
from ...logging.exp_logger import ExperimentRun, make_exp_run
from .graph import GraphSpec


def start_run(
    graph: GraphSpec,
    *,
    dry_run: bool,
    allow_live: bool,
    resume_from: Optional[Path] = None,
) -> tuple[ExperimentRun, CheckpointStore]:
    run = make_exp_run(run_dir=Path(resume_from)) if resume_from else make_exp_run()

    cfg: dict[str, Any] = {
        "benchmark": "interface_graph",
        "dry_run": dry_run,
        "allow_live": allow_live,
        "n_nodes": len(graph.nodes),
        "node_types": [n.type for n in graph.nodes],
    }
    # Resuming keeps the original config (matches the CLI's --continue behavior).
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
