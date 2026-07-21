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


def load_run_results(run_dir: Path) -> Optional[dict[str, Any]]:
    """The faithful `{order, node_results}` snapshot written at run end (see save_run_results),
    present only for runs recorded after that persistence landed."""
    return _read_json(run_dir / "run_results.json")


def count_checkpointed(run_dir: Path) -> int:
    path = run_dir / "judge_results.jsonl"
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


# Outputs whose collections exceed this are stored as a summary marker (not in full) in
# run_results.json, to keep run dirs bounded (a raw_dataset can be 1,000+ items). Matches the
# UI's own large-value summarization — full post-hoc inspection of huge outputs isn't a goal.
_MAX_INLINE = 50


def _summarize_value(value: Any) -> Any:
    if isinstance(value, dict) and len(value) > _MAX_INLINE:
        return {"__summary__": "dict", "n": len(value), "sample_keys": list(value)[:8]}
    if isinstance(value, list) and len(value) > _MAX_INLINE:
        return {"__summary__": "list", "n": len(value)}
    return value


def save_run_results(run: ExperimentRun, node_results: dict[str, Any], order: list[str]) -> None:
    """Persist the unified per-node results (status/error/meta/outputs) + execution order at
    run end, so a past run reconstructs faithfully from disk (see reconstruct_node_results).
    Large outputs are summarized to bound run-dir growth."""
    run.write_json(
        "run_results.json",
        {
            "order": order,
            "node_results": {
                nid: {
                    "status": r.status, "error": r.error, "meta": r.meta,
                    "outputs": {k: _summarize_value(v) for k, v in (r.outputs or {}).items()},
                }
                for nid, r in node_results.items()
            },
        },
    )


_EVAL_ARTIFACTS = (
    ("eval_", "metrics_report"),
    ("alignment_report_", "comparison"),
    ("rule_eval_", "comparison"),
)


def reconstruct_node_results(run_dir: Path) -> dict[str, Any]:
    """Best-effort `{order, node_results}` for a past run dir. Prefers the faithful
    run_results.json; otherwise reassembles from on-disk artifacts:
      - Eval-family `*.json` -> the node's output socket (the file IS the output),
      - Judge nodes -> reassemble `{item: {metric: dict}}` from judge_results.jsonl keys,
      - everything else -> status inferred from the overall run outcome, outputs empty.
    """
    saved = load_run_results(run_dir)
    if saved:
        return saved

    graph = load_workflow_graph(run_dir) or {"nodes": [], "edges": []}
    node_types = {n["id"]: n.get("type") for n in graph.get("nodes", [])}
    order = [n["id"] for n in graph.get("nodes", [])]
    overall = (load_run_status(run_dir) or {}).get("status")
    node_results: dict[str, Any] = {}

    # Eval-family artifacts (their JSON file is exactly the node output payload).
    for f in sorted(run_dir.glob("*.json")):
        if f.name.endswith(".partial.json"):
            continue
        for prefix, socket in _EVAL_ARTIFACTS:
            if f.name.startswith(prefix):
                nid = f.name[len(prefix):-len(".json")]
                node_results[nid] = {
                    "status": "done", "error": None, "meta": {},
                    "outputs": {socket: _read_json(f)},
                }

    # Judge nodes: regroup checkpoint keys "<node_id>::<item>::<metric>" -> judge_result.
    judge_ids = [nid for nid, t in node_types.items() if t == "judge"]
    ckpt = run_dir / "judge_results.jsonl"
    if judge_ids and ckpt.is_file():
        per_node: dict[str, dict[str, dict[str, Any]]] = {nid: {} for nid in judge_ids}
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = e.get("key", "")
            for nid in judge_ids:
                if key.startswith(nid + "::"):
                    item, _, metric = key[len(nid) + 2:].rpartition("::")
                    per_node[nid].setdefault(item, {})[metric] = e.get("value")
                    break
        for nid, per_item in per_node.items():
            if per_item:
                node_results[nid] = {
                    "status": "done", "error": None, "meta": {"n_items": len(per_item)},
                    "outputs": {"judge_result": per_item},
                }

    # Remaining nodes: no artifact. If the whole run finished, every node ran (-> done);
    # otherwise per-node status is genuinely unrecoverable pre-persistence (-> idle/neutral).
    for nid in node_types:
        if nid not in node_results:
            node_results[nid] = {
                "status": "done" if overall == "done" else "idle",
                "error": None, "meta": {}, "outputs": {},
            }
    return {"order": order, "node_results": node_results}


def list_disk_runs() -> list[dict[str, Any]]:
    """Every interface run dir under logs/exps, newest first, as lightweight summaries."""
    base = config.LOGS_ROOT / "exps"
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in base.glob("*-exps"):
        if not d.is_dir():
            continue
        cfg = load_run_config(d) or {}
        if cfg.get("benchmark") != "interface_graph":
            continue  # skip CLI human-gap runs — this lister is for interface graphs
        status_json = load_run_status(d) or {}
        run_id = d.name[: -len("-exps")]
        out.append({
            "run_id": run_id,
            "workflow_name": cfg.get("workflow_name"),
            "status": status_json.get("status", "interrupted"),
            "finished_at": status_json.get("finished_at"),
            "n_checkpointed": count_checkpointed(d),
            "n_nodes": cfg.get("n_nodes"),
        })
    out.sort(key=lambda r: r["run_id"], reverse=True)
    return out


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
