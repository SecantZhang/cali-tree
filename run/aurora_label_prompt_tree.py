#!/usr/bin/env python3
"""Score no/partial/yes in independent LLM leaves, then aggregate deterministically."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from tqdm.auto import tqdm

from run.aurora_atomic_robustness import _discover_data_root, _jsonl, _remap_case_paths, _write_jsonl
from run.aurora_prompt_repair import LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.experiments.aurora_prompt_repair import robustness_stats
from vejudge.experiments.structured_decision_test import select_candidate_rounds
from vejudge.lm_engine.gate import require_live
from vejudge.logging.llm_history import LLMHistoryWriter


LABELS = ("no", "partial", "yes")
SUPPORT_SCORE = {"no": 0, "partial": 1, "yes": 2}


def compile_label_support_leaf(spec: dict[str, Any], candidate_label: str) -> str:
    boundaries = spec["label_boundaries"][candidate_label]
    relevant_ties = [
        rule for rule in spec.get("tie_breaks") or []
        if candidate_label in str(rule).lower()
    ]
    criteria = "\n".join(f"- {value}" for value in boundaries)
    ties = "\n".join(f"- {value}" for value in relevant_ties) or "- No additional tie rule."
    return f"""You are one independent evidence leaf in an ordinal image-edit judge.
Evaluate ONLY how strongly the visible SOURCE/EDITED evidence supports this proposition:

    The overall satisfaction category is {candidate_label.upper()}.

Criteria for this proposition:
{criteria}

Relevant boundary guidance:
{ties}

Do not choose among no/partial/yes categories and do not evaluate another category's rubric.
Instead return a 0/1/2 support score encoded with these tokens:
- no = 0, visible evidence does not support this proposition.
- partial = 1, evidence gives mixed, ambiguous, or incomplete support for this proposition.
- yes = 2, visible evidence strongly and clearly supports this proposition.

Use only visible semantic evidence. Return exactly one compact JSON object and nothing else:
{{"label":"no|partial|yes","rationale":"brief evidence for this proposition only"}}
"""


def aggregate_label_support(leaves: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(leaves) != set(LABELS) or any(
        not row.get("valid") or row.get("label") not in SUPPORT_SCORE for row in leaves.values()
    ):
        return {"label": "", "valid": False, "reason": "invalid_label_support_leaf"}
    scores = {candidate: SUPPORT_SCORE[row["label"]] for candidate, row in leaves.items()}
    maximum = max(scores.values())
    winners = [candidate for candidate in LABELS if scores[candidate] == maximum]
    if len(winners) == 1:
        label, reason = winners[0], "unique strongest label-evidence leaf"
    else:
        label, reason = "partial", "tied ordinal support resolves to the middle category"
    return {"label": label, "valid": True, "reason": reason, "support_scores": scores}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prior-routing-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--min-correct", type=int, default=8)
    parser.add_argument("--confirmation-repeats", type=int, default=20)
    parser.add_argument("--confirmation-min-correct", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_live(args.live, context="AURORA label-evidence prompt tree")
    run_dir = args.run_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    args.model = args.model or config.get("model", "gpt-5.4-mini")
    data_root = args.data_root.expanduser().resolve() if args.data_root else _discover_data_root(run_dir)

    routes = _jsonl(args.prior_routing_manifest.expanduser().resolve())
    unresolved = {(row["item_id"], row["method"], row["source_round"])
                  for row in routes if row["route"] == "unresolved"}
    traces = _jsonl(run_dir / "repair_traces.jsonl")
    candidates = [row for row in select_candidate_rounds(traces)
                  if row["cohort"] == "accepted_primary"
                  and (row["item_id"], row["method"], row["round"]) in unresolved]
    structured = {(row["item_id"], row["method"], row["round"]): row
                  for row in _jsonl(run_dir / "structured_decision_results.jsonl")}
    baseline = {row["item_id"]: row for row in _jsonl(run_dir / "baseline_predictions.jsonl")}
    checkpoint = CheckpointStore(output_dir / "label_tree_checkpoints.jsonl")
    history = LLMHistoryWriter(output_dir / "label_tree_llm_history.jsonl")
    judge = LiveJudge(model=args.model, checkpoint=checkpoint, history=history,
                      max_tokens=512, timeout=args.timeout)

    def predict(case, spec, phase, index):
        leaves = {
            label: judge.judge(
                case, compile_label_support_leaf(spec, label), temperature=0.3,
                call_id=f"label-tree:{case['item_id']}:{phase}:{index:02d}:{label}",
            )
            for label in LABELS
        }
        return {"call_id": f"label-tree:{phase}:{index:02d}",
                **aggregate_label_support(leaves), "leaves": leaves}

    def run_case(candidate):
        identity = (candidate["item_id"], candidate["method"], candidate["round"])
        case = _remap_case_paths(baseline[candidate["item_id"]], data_root)
        spec = structured[identity]["extraction"]["spec"]
        search = [predict(case, spec, "search", index) for index in range(args.repeats)]
        search_stats = robustness_stats(search, candidate["target_label"], required=args.min_correct)
        confirmation = []
        if search_stats["robust"]:
            confirmation = [predict(case, spec, "confirm", index)
                            for index in range(args.confirmation_repeats)]
        confirmation_stats = robustness_stats(
            confirmation, candidate["target_label"], required=args.confirmation_min_correct
        )
        accepted = bool(search_stats["robust"] and confirmation_stats["robust"])
        return {"item_id": candidate["item_id"], "method": candidate["method"],
                "source_round": candidate["round"], "instruction": case["instruction"],
                "target_label": candidate["target_label"], "search": search,
                "search_stats": search_stats, "confirmation": confirmation,
                "confirmation_stats": confirmation_stats, "accepted": accepted}

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_case, candidate) for candidate in candidates]
        with tqdm(total=len(futures), desc="Label prompt tree", unit="case") as bar:
            for future in as_completed(futures):
                results.append(future.result()); bar.update(1)
    results.sort(key=lambda row: (row["item_id"], row["method"], row["source_round"]))
    _write_jsonl(output_dir / "label_tree_results.jsonl", results)
    accepted = sum(row["accepted"] for row in results)
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for _, value in checkpoint.items():
        if not isinstance(value, dict) or value.get("model") is None: continue
        usage["calls"] += 1
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[field] += int(value.get(field) or 0)
    usage["estimated_cost_usd"] = (
        usage["prompt_tokens"] * 0.75 + usage["completion_tokens"] * 4.5
    ) / 1_000_000
    prior_robust = sum(row["route"] != "unresolved" for row in routes)
    combined = prior_robust + accepted
    by_identity = {
        (row["item_id"], row["method"], row["source_round"]): row for row in results
    }
    summary = {"schema_version": 1, "experiment": "aurora_label_prompt_tree",
               "model": args.model, "n": len(results), "accepted": accepted,
               "robust_coverage": accepted / len(results) if results else None,
               "prior_hybrid_robust": prior_robust, "combined_robust": combined,
               "source_candidate_count": len(routes),
               "combined_coverage": combined / len(routes) if routes else None,
               "target_over_80_percent_met": bool(routes and combined / len(routes) > 0.8),
               "settings": {"repeats": args.repeats, "min_correct": args.min_correct,
                            "confirmation_repeats": args.confirmation_repeats,
                            "confirmation_min_correct": args.confirmation_min_correct},
               "usage": usage,
               "by_method": {method: {"n": sum(row["method"] == method for row in results),
                                       "accepted": sum(row["method"] == method and row["accepted"]
                                                       for row in results)}
                             for method in sorted({row["method"] for row in results})},
               "by_label": {label: {"n": sum(row["target_label"] == label for row in results),
                                     "accepted": sum(row["target_label"] == label and row["accepted"]
                                                     for row in results)}
                            for label in sorted({row["target_label"] for row in results})}}
    final_routes = []
    for prior in routes:
        identity = (prior["item_id"], prior["method"], prior["source_round"])
        label_row = by_identity.get(identity)
        route = dict(prior)
        if prior["route"] == "unresolved" and label_row and label_row["accepted"]:
            spec = structured[identity]["extraction"]["spec"]
            route.update({
                "route": "label_prompt_tree", "robust": True,
                "label_prompt_tree": {
                    "prompts": {label: compile_label_support_leaf(spec, label)
                                for label in LABELS},
                    "search_stats": label_row["search_stats"],
                    "confirmation_stats": label_row["confirmation_stats"],
                },
            })
        final_routes.append(route)
    _write_jsonl(output_dir / "final_hybrid_routing_manifest.jsonl", final_routes)
    (output_dir / "label_tree_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# Final AURORA prompt-tree robustness",
        "",
        f"- Final robust coverage: {combined}/{len(routes)} ({combined / len(routes):.2%})",
        f"- Above 80% target: {summary['target_over_80_percent_met']}",
        f"- Label-tree fallback: {accepted}/{len(results)} unresolved cases repaired",
        f"- Fallback calls: {usage['calls']}; tokens: {usage['total_tokens']:,}; "
        f"estimated cost: ${usage['estimated_cost_usd']:.4f}",
        "",
        "| Target | Instruction | Search | Confirmation | Robust |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in results:
        instruction = str(row["instruction"]).replace("|", "\\|")
        lines.append(
            f"| {row['target_label']} | {instruction} | "
            f"{row['search_stats']['target_hits']}/{row['search_stats']['n']} | "
            f"{row['confirmation_stats']['target_hits']}/"
            f"{row['confirmation_stats']['n']} | {row['accepted']} |"
        )
    (output_dir / "label_tree_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"results={output_dir / 'label_tree_results.jsonl'}")
    print(f"routes={output_dir / 'final_hybrid_routing_manifest.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
