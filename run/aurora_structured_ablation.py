#!/usr/bin/env python3
"""Run controlled-prose and lossless-JSON ablations for accepted prompt repairs."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from tqdm.auto import tqdm

from run.aurora_prompt_repair import LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.experiments.aurora_prompt_repair import robustness_stats
from vejudge.experiments.prompt_repair_report import write_html_report
from vejudge.experiments.structured_decision_test import (
    compare_behavior, compile_controlled_prose_prompt, compile_mechanical_json_prompt,
    select_candidate_rounds,
)
from vejudge.lm_engine.gate import require_live
from vejudge.logging.llm_history import LLMHistoryWriter


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows: handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    temporary.replace(path)


def _arm_summary(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    selected = [row["arms"][arm] for row in rows]
    n = len(selected)
    screen = sum(row["comparison"]["screen_correct"] for row in selected)
    robust = sum(row["comparison"]["robustness_preserved"] for row in selected)
    return {"n": n, "screen_correct": screen, "screen_accuracy": screen / n,
            "robust": robust, "robust_rate": robust / n,
            "mean_target_hit_delta": sum(row["comparison"]["target_hit_delta"] for row in selected) / n,
            "mean_tv_distance": sum(row["comparison"]["total_variation_distance"] for row in selected) / n}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--robust-min-correct", type=int)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_live(args.live, context="structured prompt ablation")
    run_dir = args.run_dir.expanduser().resolve()
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    args.model = args.model or config.get("model", "gpt-5.4-mini")
    args.robust_min_correct = args.robust_min_correct or config.get("robust_min_correct", 6)
    traces = _jsonl(run_dir / "repair_traces.jsonl")
    candidates = [row for row in select_candidate_rounds(traces) if row["cohort"] == "accepted_primary"]
    baselines = {row["item_id"]: row for row in _jsonl(run_dir / "baseline_predictions.jsonl")}
    structured = {(row["item_id"], row["method"], row["round"]): row
                  for row in _jsonl(run_dir / "structured_decision_results.jsonl")}
    checkpoint = CheckpointStore(run_dir / "structured_decision_checkpoints.jsonl")
    history = LLMHistoryWriter(run_dir / "structured_ablation_llm_history.jsonl")
    judge = LiveJudge(model=args.model, checkpoint=checkpoint, history=history,
                      max_tokens=1024, timeout=args.timeout)

    def run_arm(candidate, name, prompt):
        case = baselines[candidate["item_id"]]
        prefix = f"ablation:{name}:{candidate['method']}:{candidate['item_id']}:{candidate['round']}"
        screen = judge.judge(case, prompt, temperature=0.0, call_id=prefix + ":screen")
        repeats = [judge.judge(case, prompt, temperature=0.3,
                    call_id=f"{prefix}:repeat:{index:02d}") for index in range(args.repeats)]
        comparison = compare_behavior(candidate, screen, repeats, args.robust_min_correct)
        return {"prompt": prompt, "screen": screen, "repeats": repeats,
                "robustness": comparison["structured_robustness"], "comparison": comparison}

    def evaluate(candidate):
        existing = structured[(candidate["item_id"], candidate["method"], candidate["round"])]
        spec = existing["extraction"]["spec"]
        fresh = run_arm(candidate, "fresh_natural", candidate["original_prompt"])
        prose = run_arm(candidate, "controlled_prose", compile_controlled_prose_prompt(spec))
        mechanical = run_arm(candidate, "mechanical_json", compile_mechanical_json_prompt(candidate["original_prompt"]))
        semantic = {"prompt": existing["structured_prompt"], "screen": existing["structured_screen"],
                    "repeats": existing["structured_repeats"],
                    "robustness": existing["comparison"]["structured_robustness"],
                    "comparison": existing["comparison"]}
        return {"item_id": candidate["item_id"], "method": candidate["method"],
                "round": candidate["round"], "target_label": candidate["target_label"],
                "original": {"prompt": candidate["original_prompt"],
                             "screen": candidate["original_screen"],
                             "repeats": candidate["original_repeats"],
                             "robustness": candidate["original_robustness"]},
                "arms": {"fresh_natural": fresh, "semantic_json": semantic, "controlled_prose": prose,
                         "mechanical_json": mechanical}}

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(evaluate, candidate) for candidate in candidates]
        with tqdm(total=len(futures), desc="Clean representation ablation", unit="pair") as bar:
            for future in as_completed(futures): results.append(future.result()); bar.update(1)
    results.sort(key=lambda row: (row["item_id"], row["method"], row["round"]))
    _write_jsonl(run_dir / "structured_ablation_results.jsonl", results)
    arms = {name: _arm_summary(results, name)
            for name in ("fresh_natural", "semantic_json", "controlled_prose", "mechanical_json")}
    summary = {"schema_version": 1, "experiment": "clean_structured_prompt_ablation",
               "model": args.model, "n": len(results), "original": {"screen_correct": len(results),
               "robust": len(results)}, "arms": arms}
    (run_dir / "structured_ablation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Clean structured-prompt ablation", "", "| Arm | Screen correct | Robust | Mean hit Δ | Mean TV |",
             "|---|---:|---:|---:|---:|", f"| Original natural language | {len(results)}/{len(results)} | {len(results)}/{len(results)} | 0.00 | 0.000 |"]
    for name, row in arms.items():
        lines.append(f"| {name} | {row['screen_correct']}/{row['n']} | {row['robust']}/{row['n']} | {row['mean_target_hit_delta']:.2f} | {row['mean_tv_distance']:.3f} |")
    (run_dir / "structured_ablation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_html_report(run_dir)
    print(json.dumps(summary, indent=2)); print(f"report={run_dir / 'report.html'}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
