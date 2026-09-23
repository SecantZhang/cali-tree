#!/usr/bin/env python3
"""Test whether structured decision policies preserve optimized-prompt behavior."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from tqdm.auto import tqdm

from run.aurora_prompt_repair import LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.experiments.aurora_prompt_repair import prompt_digest
from vejudge.experiments.prompt_repair_report import write_html_report
from vejudge.experiments.structured_decision_test import (
    compare_behavior, compile_structured_prompt, parse_decision_spec,
    select_candidate_rounds, summarize,
)
from vejudge.lm_engine import load_creds, openai_compat
from vejudge.lm_engine.gate import require_live
from vejudge.logging.llm_history import LLMHistoryWriter


EXTRACTION_SYSTEM = """Convert a natural-language vision-judge rubric into a compact,
case-agnostic semantic decision specification. You will receive only the rubric. Never add
examples, image details, task IDs, model IDs, focal instructions, predicted labels, or target
answers. Preserve every decision boundary and its priority, but remove rhetorical prose.
Return exactly one JSON object with these keys:
{
  "objective": "short string",
  "evidence_rules": ["atomic rule"],
  "decision_steps": [{"order": 1, "decision": "atomic test", "outcomes": "routing effect"}],
  "label_boundaries": {"no": ["conditions"], "partial": ["conditions"], "yes": ["conditions"]},
  "tie_breaks": ["ordered boundary rule"],
  "output_contract": {"format": "json", "labels": ["no","partial","yes"], "rationale": "requirement"}
}"""


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows: handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    temp.replace(path)


class Extractor:
    def __init__(self, args, checkpoint, history):
        self.args, self.checkpoint, self.history = args, checkpoint, history
        self.creds = load_creds()

    def extract(self, prompt: str) -> dict[str, Any]:
        digest = prompt_digest(prompt)
        key = f"structured-decision::extract::{self.args.extractor_model}::{digest}"
        if self.checkpoint.has(key):
            row = dict(self.checkpoint.get(key)); row["checkpoint_hit"] = True; return row
        messages = [{"role": "system", "content": EXTRACTION_SYSTEM}, {"role": "user", "content": prompt}]
        attempts = []
        for attempt in range(3):
            try:
                result = openai_compat.chat_completion(
                    endpoints=self.creds.endpoints, token=self.creds.token,
                    model=self.args.extractor_model, messages=messages, max_tokens=2048,
                    temperature=0.0, timeout=self.args.timeout, max_retries=4,
                )
                content = str(result.content or "")
                attempts.append({"attempt": attempt + 1, "raw_content": content,
                                 "model": result.model, "prompt_tokens": result.prompt_tokens,
                                 "completion_tokens": result.completion_tokens,
                                 "total_tokens": result.total_tokens,
                                 "latency_seconds": result.latency_s})
                try:
                    spec = parse_decision_spec(content)
                except Exception as exc:
                    attempts[-1]["validation_error"] = f"{type(exc).__name__}: {exc}"
                    messages.extend([
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": (
                            "That response failed schema validation: " + str(exc) +
                            ". Return the complete required JSON object only."
                        )},
                    ])
                    continue
                row = {"valid": True, "error": None, "spec": spec, "raw_content": content,
                       "model": result.model, "prompt_tokens": sum(a["prompt_tokens"] for a in attempts),
                       "completion_tokens": sum(a["completion_tokens"] for a in attempts),
                       "total_tokens": sum(a["total_tokens"] for a in attempts),
                       "latency_seconds": sum(a["latency_seconds"] for a in attempts),
                       "attempts": attempts, "checkpoint_hit": False}
                self.checkpoint.put(key, row)
                return row
            except Exception as exc:
                attempts.append({"attempt": attempt + 1, "transport_error": f"{type(exc).__name__}: {exc}"})
        error = attempts[-1].get("validation_error") or attempts[-1].get("transport_error")
        return {"valid": False, "error": error, "spec": None, "attempts": attempts,
                "checkpoint_hit": False}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--extractor-model")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--robust-min-correct", type=int)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=1024)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_live(args.live, context="structured-decision equivalence experiment")
    run_dir = args.run_dir.expanduser().resolve()
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    args.model = args.model or config.get("model", "gpt-5.4-mini")
    args.extractor_model = args.extractor_model or args.model
    args.robust_min_correct = args.robust_min_correct or config.get("robust_min_correct", 6)
    traces = _jsonl(run_dir / "repair_traces.jsonl")
    baselines = {row["item_id"]: row for row in _jsonl(run_dir / "baseline_predictions.jsonl")}
    candidates = select_candidate_rounds(traces)
    checkpoint = CheckpointStore(run_dir / "structured_decision_checkpoints.jsonl")
    history = LLMHistoryWriter(run_dir / "structured_decision_llm_history.jsonl")
    extractor = Extractor(args, checkpoint, history)
    judge = LiveJudge(model=args.model, checkpoint=checkpoint, history=history,
                      max_tokens=args.max_tokens, timeout=args.timeout)
    extracted: dict[str, dict[str, Any]] = {}

    unique = {prompt_digest(row["original_prompt"]): row["original_prompt"] for row in candidates}
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(extractor.extract, prompt): digest for digest, prompt in unique.items()}
        with tqdm(total=len(futures), desc="Extract decision policies", unit="prompt") as bar:
            for future in as_completed(futures):
                extracted[futures[future]] = future.result(); bar.update(1)

    def evaluate(candidate):
        digest = prompt_digest(candidate["original_prompt"])
        extraction = extracted[digest]
        base = {key: value for key, value in candidate.items() if not key.startswith("original_prompt")}
        if not extraction.get("valid"):
            return {**base, "extraction": extraction, "structured_prompt": None,
                    "structured_screen": None, "structured_repeats": [], "comparison": {}}
        structured = compile_structured_prompt(extraction["spec"])
        case = baselines[candidate["item_id"]]
        prefix = f"structured:{candidate['method']}:{candidate['item_id']}:{candidate['round']}"
        screen = judge.judge(case, structured, temperature=0.0, call_id=prefix + ":screen")
        repeats = [judge.judge(case, structured, temperature=0.3,
                    call_id=f"{prefix}:repeat:{index:02d}") for index in range(args.repeats)]
        comparison = compare_behavior(candidate, screen, repeats, args.robust_min_correct)
        return {**base, "original_prompt_sha256": candidate.get("original_prompt_sha256"),
                "original_screen": candidate["original_screen"],
                "original_robustness": candidate["original_robustness"],
                "extraction": extraction, "structured_prompt": structured,
                "structured_prompt_sha256": prompt_digest(structured),
                "structured_screen": screen, "structured_repeats": repeats,
                "comparison": comparison}

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(evaluate, candidate): candidate for candidate in candidates}
        with tqdm(total=len(futures), desc="Test structured prompts", unit="pair") as bar:
            for future in as_completed(futures):
                results.append(future.result()); bar.update(1)
    results.sort(key=lambda row: (row["item_id"], row["method"], row["round"]))
    _write_jsonl(run_dir / "structured_decision_results.jsonl", results)
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    prefixes = ("structured-decision::extract", "aurora-repair::judge::structured:")
    for key, value in checkpoint.items():
        if not key.startswith(prefixes) or not isinstance(value, dict): continue
        usage["calls"] += 1
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[field] += int(value.get(field) or 0)
    usage["estimated_cost_usd"] = (
        usage["prompt_tokens"] * 0.75 + usage["completion_tokens"] * 4.5
    ) / 1_000_000
    summary = {"schema_version": 1, "experiment": "structured_decision_equivalence",
               "judge_model": args.model, "extractor_model": args.extractor_model,
               "candidate_pairs": len(candidates), "unique_prompts": len(unique),
               "repeats": args.repeats, "robust_min_correct": args.robust_min_correct,
               "cohorts": summarize(results), "usage": usage}
    (run_dir / "structured_decision_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    primary = summary["cohorts"]["accepted_primary"]
    lines = ["# Structured-decision equivalence", "",
             f"- Accepted optimized prompt–case pairs: {primary['n']}",
             f"- Deterministic label preserved: {primary['screen_label_preserved']}/{primary['n']} "
             f"({primary['screen_label_preservation_rate']:.1%})",
             f"- Repeated-run robustness preserved: {primary['robustness_preserved']}/{primary['n']} "
             f"({primary['robustness_preservation_rate']:.1%})",
             f"- Mean target-hit change: {primary['mean_target_hit_delta']:.2f} of 10",
             f"- Mean distribution TV distance: {primary['mean_total_variation_distance']:.3f}",
             "", "## Accepted cohort by target label", "",
             "| Target | Pairs | Screen preserved | Robustness preserved |", "|---|---:|---:|---:|"]
    for label, row in summary["cohorts"]["accepted_primary_by_label"].items():
        lines.append(f"| {label} | {row['n']} | {row['screen_label_preserved']} | {row['robustness_preserved']} |")
    lines.extend(["", "## Accepted cohort by optimizer", "",
                  "| Method | Pairs | Screen preserved | Robustness preserved |", "|---|---:|---:|---:|"])
    for method, row in summary["cohorts"]["accepted_primary_by_method"].items():
        lines.append(f"| {method} | {row['n']} | {row['screen_label_preserved']} | {row['robustness_preserved']} |")
    lines.extend(["", f"Recorded model calls: {usage['calls']}",
                  f"Recorded tokens: {usage['total_tokens']}",
                  f"Estimated cost: ${usage['estimated_cost_usd']:.4f}"])
    (run_dir / "structured_decision_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_html_report(run_dir)
    print(json.dumps(summary, indent=2)); print(f"report={run_dir / 'report.html'}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
