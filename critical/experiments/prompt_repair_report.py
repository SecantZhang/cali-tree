"""Build a self-contained browser report for prompt-repair experiments."""

from __future__ import annotations

import copy
import difflib
import json
from pathlib import Path
from typing import Any, Iterable, Optional


SCHEMA_VERSION = 1
TEMPLATE_PATH = Path(__file__).with_name("prompt_repair_report_template.html")


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _artifact_path(value: Any, run_dir: Path) -> Optional[Path]:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    candidates = [path]
    if not path.is_absolute():
        candidates.insert(0, run_dir / path)
    else:
        # A copied run often retains an old absolute prefix. Recover from the first
        # run-directory-name component when possible.
        try:
            offset = path.parts.index(run_dir.name)
            candidates.append(run_dir.joinpath(*path.parts[offset + 1 :]))
        except ValueError:
            pass
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _read_artifact(value: Any, run_dir: Path) -> Optional[str]:
    path = _artifact_path(value, run_dir)
    if path is None:
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _image_url(value: Any, run_dir: Path) -> Optional[str]:
    path = _artifact_path(value, run_dir)
    if path is None:
        return None
    return path.resolve().as_uri()


def _prompt_diff(parent: str, candidate: str) -> str:
    return "".join(
        difflib.unified_diff(
            parent.splitlines(keepends=True),
            candidate.splitlines(keepends=True),
            fromfile="parent",
            tofile="candidate",
        )
    )


def _seed_prompt(run_dir: Path, config: dict[str, Any], traces: Iterable[dict[str, Any]]) -> str:
    configured = _read_artifact(config.get("prompt_path"), run_dir)
    if configured is not None:
        return configured
    for trace in traces:
        for round_row in trace.get("rounds") or []:
            prompt_path = _artifact_path(round_row.get("candidate_prompt_path"), run_dir)
            if prompt_path is None:
                continue
            candidate = prompt_path.parent / "round-00-seed.txt"
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8", errors="replace")
    candidates = sorted(run_dir.glob("prompts/*/*/round-00-seed.txt"))
    return candidates[0].read_text(encoding="utf-8", errors="replace") if candidates else ""


def build_report_payload(run_dir: Path) -> dict[str, Any]:
    """Load and enrich one compatible experiment directory for the browser."""

    run_dir = run_dir.expanduser().resolve()
    baseline_path = run_dir / "baseline_predictions.jsonl"
    if not baseline_path.is_file():
        raise FileNotFoundError(f"missing required report input: {baseline_path}")

    baselines = _read_jsonl(baseline_path)
    traces = _read_jsonl(run_dir / "repair_traces.jsonl")
    structured_results = _read_jsonl(run_dir / "structured_decision_results.jsonl")
    ablation_results = _read_jsonl(run_dir / "structured_ablation_results.jsonl")
    summary = _read_json(run_dir / "summary.json", {})
    structured_summary = _read_json(run_dir / "structured_decision_summary.json", {})
    ablation_summary = _read_json(run_dir / "structured_ablation_summary.json", {})
    config = _read_json(run_dir / "run_config.json", {})
    manifest = _read_json(run_dir / "sample_manifest.json", {})
    seed_prompt = _seed_prompt(run_dir, config, traces)

    traces_by_item: dict[str, list[dict[str, Any]]] = {}
    structured_by_round = {
        (str(row.get("item_id")), str(row.get("method")), int(row.get("round", 0))): row
        for row in structured_results
    }
    ablation_by_round = {
        (str(row.get("item_id")), str(row.get("method")), int(row.get("round", 0))): row
        for row in ablation_results
    }
    for raw_trace in traces:
        trace = copy.deepcopy(raw_trace)
        parent_prompt = seed_prompt
        for round_row in trace.get("rounds") or []:
            candidate = str(round_row.get("candidate_prompt") or parent_prompt)
            diff_text = _read_artifact(round_row.get("prompt_diff_path"), run_dir)
            round_row["prompt_diff"] = (
                diff_text if diff_text is not None else _prompt_diff(parent_prompt, candidate)
            )
            round_row["structured_test"] = structured_by_round.get(
                (str(trace.get("item_id")), str(trace.get("method")), int(round_row.get("round", 0)))
            )
            round_row["structured_ablation"] = ablation_by_round.get(
                (str(trace.get("item_id")), str(trace.get("method")), int(round_row.get("round", 0)))
            )
            parent_prompt = candidate
        trace["best_prompt"] = (
            _read_artifact(trace.get("best_prompt_path"), run_dir) or parent_prompt
        )
        traces_by_item.setdefault(str(trace.get("item_id", "")), []).append(trace)

    cases = []
    for raw_case in baselines:
        case = copy.deepcopy(raw_case)
        case["source_image_url"] = _image_url(case.get("source_image_path"), run_dir)
        case["edited_image_url"] = _image_url(case.get("edited_image_path"), run_dir)
        case["repairs"] = sorted(
            traces_by_item.get(str(case.get("item_id", "")), []),
            key=lambda row: str(row.get("method", "")),
        )
        cases.append(case)

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "prompt_repair_experiment",
        "run_name": run_dir.name,
        "run_dir": str(run_dir),
        "summary": summary,
        "structured_summary": structured_summary,
        "ablation_summary": ablation_summary,
        "config": config,
        "manifest": {
            "dataset": manifest.get("dataset"),
            "seed": manifest.get("seed"),
            "sample_size": manifest.get("sample_size", len(cases)),
            "quotas": manifest.get("quotas"),
        },
        "seed_prompt": seed_prompt,
        "cases": cases,
    }


def write_html_report(run_dir: Path, output_path: Optional[Path] = None) -> Path:
    """Write a standalone HTML report and return its resolved path."""

    run_dir = run_dir.expanduser().resolve()
    output_path = (output_path or run_dir / "report.html").expanduser().resolve()
    payload = build_report_payload(run_dir)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # JSON inside a script element must not be able to terminate that element.
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "__PROMPT_REPAIR_REPORT_DATA__" not in template:
        raise ValueError(f"report template is missing its data marker: {TEMPLATE_PATH}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        template.replace("__PROMPT_REPAIR_REPORT_DATA__", serialized),
        encoding="utf-8",
    )
    return output_path
