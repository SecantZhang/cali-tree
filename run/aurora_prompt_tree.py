#!/usr/bin/env python3
"""Evaluate AURORA with focused prompt-tree leaves and deterministic aggregation."""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from tqdm.auto import tqdm

from run.aurora_atomic_robustness import (
    _discover_data_root,
    _jsonl,
    _remap_case_paths,
    _write_jsonl,
    select_pilot_candidates,
)
from run.aurora_prompt_repair import LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.experiments.aurora_prompt_repair import prompt_digest, robustness_stats
from vejudge.experiments.structured_decision_test import select_candidate_rounds
from vejudge.lm_engine import load_creds, openai_compat
from vejudge.lm_engine.gate import require_live
from vejudge.logging.llm_history import LLMHistoryWriter


DECOMPOSER_SYSTEM = """Decompose one image-edit instruction into independent, visually
checkable semantic requirements. Return JSON only:
{"requirements":[{"id":"r1","text":"...","role":"core|modifier","kind":"object|action|relation|attribute|outcome"}]}

A core requirement is the requested object, transformation, action, or relationship whose
absence means the main edit did not happen. A modifier is an attribute such as color, size,
count, degree, or fine placement: if the core edit is present but a modifier fails, the edit
is partial rather than wholly absent. Actions and requested spatial relationships are core.
For a causal action with an explicit result, emit separate core requirements for the actor or
contact, the action, and the observable resulting state. For example, do not combine "a hand
pushes an object farther right" into one requirement: separately check the hand/contact and
that the object is visibly farther right than in the source; mark the latter as kind=outcome.
Express ordinary requested final states directly. For example, "move the candles close to
each other" becomes "the candles are close to each other" with kind=relation, not a comparison
of source and edited spacing. Use kind=outcome only for an explicit causal result or explicit
before/after comparison that must be observed.
Do not add scene preservation, visual quality, or unstated requirements. Use one to four
non-overlapping requirements and include at least one core requirement."""


REQUIREMENT_LEAF = """You are one leaf in a prompt-tree image-edit evaluator.
Evaluate ONLY whether there is visible, directionally correct evidence for the single
requirement below. Do not score scene preservation, unrelated objects, image aesthetics,
or the overall instruction.

Focused requirement ({role}, {kind}): {text}

Choose:
- no: the edited image has no visible evidence for this requirement, or visibly contradicts it.
- partial: there is visible, directionally correct evidence, but it is incomplete, ambiguous,
  weak, approximate, or not fully realized.
- yes: the requirement is clearly and sufficiently satisfied.

Use the SOURCE image only to establish the before-state. Return exactly one compact JSON
object and nothing else:
{{"label":"no|partial|yes","rationale":"brief visible evidence for this requirement only"}}
"""


FIDELITY_LEAF = """You are the strict fidelity-audit leaf for one image-edit requirement.
Evaluate ONLY whether the visible result realizes this requirement completely and precisely.
Actively look for semantic shortfalls. Do not score unrelated content or overall quality.

Focused requirement ({role}, {kind}): {text}

Choose:
- no: the requirement is absent, contradicted, applied to the wrong target, or has no credible
  visible evidence.
- partial: the intended effect is recognizable, but any meaningful part is incomplete,
  approximate, ambiguous, weak, misplaced, or not visibly demonstrated.
- yes: the full requirement is clearly and unambiguously realized with no meaningful semantic
  shortfall.

For contact, holding, motion, and spatial relationships, require the requested state to be
visibly demonstrated; proximity or a plausible pose alone is partial. For a color or attribute
change, require the full target to have the requested attribute. Return JSON only:
{{"label":"no|partial|yes","rationale":"the strongest visible fidelity evidence"}}
"""


PRESERVATION_LEAF = """You are the collateral-change leaf in a prompt-tree evaluator.
Evaluate ONLY semantic changes outside the requested target/effect by comparing SOURCE and
EDITED. Do not judge whether the requested edit succeeded. Ignore style, realism, blur, text
artifacts, and low-level quality unless they change semantic content.

Choose:
- no: the scene/main subject is replaced or unrecognizable, the wrong subject is edited, or
  identities/shapes of multiple important non-target objects are replaced.
- partial: the same scene and object identities remain recognizable, but at least one clear
  unintended attribute, color, count, position, or extra-object change exists.
- yes: important non-target content remains semantically intact; only the requested target
  and effect changed.

Return exactly one compact JSON object and nothing else:
{"label":"no|partial|yes","rationale":"brief preservation evidence only"}
"""


def parse_requirements(content: str, instruction: str) -> list[dict[str, str]]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("decomposer response does not contain JSON")
    value = json.loads(text[start : end + 1])
    rows = value.get("requirements") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
        raise ValueError("requirements must contain one to four entries")
    result, seen = [], set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("each requirement must be an object")
        requirement = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()
        role = str(row.get("role") or "").strip().lower()
        kind = str(row.get("kind") or "").strip().lower()
        if not requirement or role not in {"core", "modifier"}:
            raise ValueError("each requirement needs text and a core/modifier role")
        if kind not in {"object", "action", "relation", "attribute", "outcome"}:
            raise ValueError("each requirement needs a supported criterion kind")
        key = requirement.lower()
        if key in seen:
            raise ValueError("requirements must not be duplicated")
        seen.add(key)
        result.append({"id": f"r{index}", "text": requirement, "role": role, "kind": kind})
    if not any(row["role"] == "core" for row in result):
        raise ValueError("at least one core requirement is required")
    return result


def aggregate_tree(
    requirements: list[dict[str, str]],
    requirement_rows: list[dict[str, Any]],
    preservation_row: dict[str, Any],
) -> dict[str, Any]:
    if len(requirements) != len(requirement_rows):
        raise ValueError("one leaf result is required per requirement")
    leaves = [*requirement_rows, preservation_row]
    if any(not row.get("valid") or row.get("label") not in {"no", "partial", "yes"}
           for row in leaves):
        return {"label": "", "valid": False, "reason": "invalid_leaf"}

    paired = list(zip(requirements, requirement_rows))
    core_labels = [row["label"] for requirement, row in paired if requirement["role"] == "core"]
    modifier_labels = [
        row["label"] for requirement, row in paired if requirement["role"] == "modifier"
    ]
    preservation = preservation_row["label"]
    if "no" in core_labels or preservation == "no":
        label, reason = "no", "a core requirement or scene preservation failed"
    elif "partial" in core_labels or preservation == "partial" or any(
        label != "yes" for label in modifier_labels
    ):
        label, reason = "partial", "the core edit exists but at least one branch is incomplete"
    else:
        label, reason = "yes", "all core, modifier, and preservation branches passed"
    return {"label": label, "valid": True, "reason": reason}


def compile_requirement_leaf(requirement: dict[str, str]) -> str:
    return REQUIREMENT_LEAF.format(**requirement)


def compile_fidelity_leaf(requirement: dict[str, str]) -> str:
    return FIDELITY_LEAF.format(**requirement)


def combine_requirement_leaves(
    requirement: dict[str, str], presence: dict[str, Any], fidelity: dict[str, Any]
) -> dict[str, Any]:
    if any(not row.get("valid") or row.get("label") not in {"no", "partial", "yes"}
           for row in (presence, fidelity)):
        return {"label": "", "valid": False, "reason": "invalid_requirement_leaf",
                "presence": presence, "fidelity": fidelity}
    if presence["label"] == "no":
        label, reason = "no", "the presence leaf found no visible evidence"
    elif requirement.get("kind") == "outcome" and fidelity["label"] == "no":
        label, reason = "no", "the explicit causal outcome failed strict verification"
    elif presence["label"] == "yes" and fidelity["label"] == "yes":
        label, reason = "yes", "presence and strict fidelity both passed"
    else:
        label, reason = "partial", "visible evidence exists but fidelity is incomplete or disputed"
    return {"label": label, "valid": True, "reason": reason,
            "presence": presence, "fidelity": fidelity}


def write_markdown_summary(
    output_dir: Path, results: list[dict[str, Any]], summary: dict[str, Any]
) -> Path:
    lines = [
        "# AURORA focused prompt-tree evaluation",
        "",
        f"- Repair pool: {summary['accepted']}/{summary['n']} robust "
        f"({summary['repair_robust_coverage']:.2%})",
        f"- Original structured prompts: {summary['source_structured_robust']}/"
        f"{summary['source_candidate_count']} robust",
        f"- Hybrid lower bound: {summary['hybrid_robust_lower_bound']}/"
        f"{summary['source_candidate_count']} "
        f"({summary['hybrid_coverage_lower_bound']:.2%})",
        f"- Above 80% target: {summary['target_over_80_percent_met']}",
        f"- Calls: {summary['usage']['calls']}; tokens: "
        f"{summary['usage']['total_tokens']:,}; estimated cost: "
        f"${summary['usage']['estimated_cost_usd']:.4f}",
        "",
        "| Target | Instruction | Requirements | Search | Confirmation | Robust |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        instruction = str(row["instruction"]).replace("|", "\\|")
        lines.append(
            f"| {row['target_label']} | {instruction} | "
            f"{len(row['decomposition']['requirements'])} | "
            f"{row['search_stats']['target_hits']}/{row['search_stats']['n']} | "
            f"{row['confirmation_stats']['target_hits']}/"
            f"{row['confirmation_stats']['n']} | {row['accepted']} |"
        )
    lines.extend([
        "",
        "Each tree repetition independently scores requirement presence, strict requirement "
        "fidelity, and collateral preservation. A deterministic typed rule aggregates the "
        "leaves; no final LLM aggregation call is used.",
        "",
    ])
    path = output_dir / "prompt_tree_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class InstructionDecomposer:
    def __init__(self, model: str, timeout: int, checkpoint: CheckpointStore):
        self.model, self.timeout, self.checkpoint = model, timeout, checkpoint
        self.creds = load_creds(model=model)

    def decompose(self, item_id: str, instruction: str) -> dict[str, Any]:
        key = f"prompt-tree::decompose::{item_id}::{prompt_digest(DECOMPOSER_SYSTEM + instruction)}"
        if self.checkpoint.has(key):
            row = dict(self.checkpoint.get(key)); row["checkpoint_hit"] = True; return row
        try:
            result = openai_compat.chat_completion(
                provider=self.creds.provider, endpoints=self.creds.endpoints, token=self.creds.token, model=self.model,
                messages=[{"role": "system", "content": DECOMPOSER_SYSTEM},
                          {"role": "user", "content": instruction}],
                max_tokens=768, temperature=0.0, timeout=self.timeout, max_retries=4,
            )
            requirements = parse_requirements(str(result.content or ""), instruction)
            row = {"valid": True, "requirements": requirements,
                   "raw_content": str(result.content or ""), "model": result.model,
                   "prompt_tokens": result.prompt_tokens,
                   "completion_tokens": result.completion_tokens,
                   "total_tokens": result.total_tokens, "latency_seconds": result.latency_s,
                   "checkpoint_hit": False}
            self.checkpoint.put(key, row)
            return row
        except Exception as exc:
            return {"valid": False, "requirements": [
                {"id": "r1", "text": instruction, "role": "core", "kind": "action"}
            ], "error": f"{type(exc).__name__}: {exc}", "checkpoint_hit": False}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--selection", choices=("all", "structured-failures"),
                        default="structured-failures")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--min-correct", type=int, default=8)
    parser.add_argument("--confirmation-repeats", type=int, default=20)
    parser.add_argument("--confirmation-min-correct", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_live(args.live, context="AURORA prompt-tree experiment")
    run_dir, output_dir = args.run_dir.expanduser().resolve(), args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    args.model = args.model or config.get("model", "gpt-5.4-mini")
    data_root = args.data_root.expanduser().resolve() if args.data_root else _discover_data_root(run_dir)

    traces = _jsonl(run_dir / "repair_traces.jsonl")
    source_candidates = [row for row in select_candidate_rounds(traces)
                         if row["cohort"] == "accepted_primary"]
    structured = {(row["item_id"], row["method"], row["round"]): row
                  for row in _jsonl(run_dir / "structured_decision_results.jsonl")}
    def source_structured_pass(identity: tuple[str, str, int]) -> bool:
        stats = structured[identity]["comparison"]["structured_robustness"]
        return bool(
            int(stats.get("n") or 0) == args.repeats
            and int(stats.get("target_hits") or 0) >= args.min_correct
        )

    source_robust = sum(
        source_structured_pass((row["item_id"], row["method"], row["round"]))
        for row in source_candidates
    )
    source_failures = len(source_candidates) - source_robust
    selection_candidates = source_candidates
    if args.selection == "structured-failures":
        selection_candidates = [
            row for row in source_candidates
            if not source_structured_pass((row["item_id"], row["method"], row["round"]))
        ]
    candidates = select_pilot_candidates(selection_candidates, structured, selection="all",
                                         limit=args.limit, seed=args.seed)
    baseline = {row["item_id"]: row for row in _jsonl(run_dir / "baseline_predictions.jsonl")}
    checkpoint = CheckpointStore(output_dir / "prompt_tree_checkpoints.jsonl")
    history = LLMHistoryWriter(output_dir / "prompt_tree_llm_history.jsonl")
    judge = LiveJudge(model=args.model, checkpoint=checkpoint, history=history,
                      max_tokens=512, timeout=args.timeout)
    decomposer = InstructionDecomposer(args.model, args.timeout, checkpoint)

    def tree_prediction(case, requirements, phase, repeat_index):
        requirement_rows = []
        for requirement in requirements:
            presence = judge.judge(
                case, compile_requirement_leaf(requirement), temperature=0.3,
                call_id=(f"prompt-tree:{case['item_id']}:{phase}:{repeat_index:02d}:"
                         f"{requirement['id']}:presence"),
            )
            fidelity = judge.judge(
                case, compile_fidelity_leaf(requirement), temperature=0.3,
                call_id=(f"prompt-tree:{case['item_id']}:{phase}:{repeat_index:02d}:"
                         f"{requirement['id']}:fidelity"),
            )
            requirement_rows.append(combine_requirement_leaves(requirement, presence, fidelity))
        preservation = judge.judge(
            case, PRESERVATION_LEAF, temperature=0.3,
            call_id=f"prompt-tree:{case['item_id']}:{phase}:{repeat_index:02d}:preservation",
        )
        aggregate = aggregate_tree(requirements, requirement_rows, preservation)
        return {"call_id": f"prompt-tree:{phase}:{repeat_index:02d}",
                **aggregate, "requirements": requirement_rows, "preservation": preservation}

    def run_case(candidate):
        case = _remap_case_paths(baseline[candidate["item_id"]], data_root)
        decomposition = decomposer.decompose(case["item_id"], case["instruction"])
        requirements = decomposition["requirements"]
        search = [tree_prediction(case, requirements, "search", index)
                  for index in range(args.repeats)]
        search_stats = robustness_stats(search, candidate["target_label"], required=args.min_correct)
        confirmation = []
        if search_stats["robust"]:
            confirmation = [tree_prediction(case, requirements, "confirm", index)
                            for index in range(args.confirmation_repeats)]
        confirmation_stats = robustness_stats(
            confirmation, candidate["target_label"], required=args.confirmation_min_correct
        )
        accepted = bool(search_stats["robust"] and confirmation_stats["robust"])
        return {"item_id": candidate["item_id"], "method": candidate["method"],
                "source_round": candidate["round"], "instruction": case["instruction"],
                "human_score": case["human_score"], "target_label": candidate["target_label"],
                "decomposition": decomposition, "search": search,
                "search_stats": search_stats, "confirmation": confirmation,
                "confirmation_stats": confirmation_stats, "accepted": accepted,
                "stop_reason": "accepted" if accepted else (
                    "confirmation_failed" if confirmation else "search_failed")}

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_case, candidate) for candidate in candidates]
        with tqdm(total=len(futures), desc="Prompt tree", unit="case") as bar:
            for future in as_completed(futures):
                results.append(future.result()); bar.update(1)
    results.sort(key=lambda row: (row["item_id"], row["method"], row["source_round"]))
    _write_jsonl(output_dir / "prompt_tree_results.jsonl", results)

    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for _, value in checkpoint.items():
        if not isinstance(value, dict) or value.get("model") is None:
            continue
        usage["calls"] += 1
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[field] += int(value.get(field) or 0)
    usage["estimated_cost_usd"] = (
        usage["prompt_tokens"] * 0.75 + usage["completion_tokens"] * 4.5
    ) / 1_000_000
    accepted = sum(row["accepted"] for row in results)
    repair_coverage = accepted / len(results) if results else None
    tree_results = {
        (row["item_id"], row["method"], row["source_round"]): row for row in results
    }
    hybrid_robust_lower_bound = sum(
        source_structured_pass((row["item_id"], row["method"], row["round"]))
        or bool(tree_results.get((row["item_id"], row["method"], row["round"]), {}).get(
            "accepted"
        ))
        for row in source_candidates
    )
    hybrid_coverage_lower_bound = (
        hybrid_robust_lower_bound / len(source_candidates) if source_candidates else None
    )
    source_failure_identities = {
        (row["item_id"], row["method"], row["round"])
        for row in source_candidates
        if not source_structured_pass((row["item_id"], row["method"], row["round"]))
    }
    evaluated_all_failures = bool(
        source_failure_identities <= set(tree_results)
    )
    summary = {"schema_version": 1, "experiment": "aurora_prompt_tree",
               "model": args.model, "n": len(results), "accepted": accepted,
               "robust_coverage": repair_coverage,
               "repair_robust_coverage": repair_coverage,
               "source_candidate_count": len(source_candidates),
               "source_structured_robust": source_robust,
               "source_structured_robust_threshold": args.min_correct,
               "source_structured_failures": source_failures,
               "evaluated_all_source_failures": evaluated_all_failures,
               "hybrid_robust_lower_bound": hybrid_robust_lower_bound,
               "hybrid_coverage_lower_bound": hybrid_coverage_lower_bound,
               "target_over_80_percent_met": bool(
                   hybrid_coverage_lower_bound is not None
                   and hybrid_coverage_lower_bound > 0.8
               ),
               "settings": {"repeats": args.repeats, "min_correct": args.min_correct,
                            "confirmation_repeats": args.confirmation_repeats,
                            "confirmation_min_correct": args.confirmation_min_correct,
                            "aggregation": "core_no_or_preservation_no=>no; any_partial_or_modifier_not_yes=>partial; else yes"},
               "usage": usage, "source_run_dir": str(run_dir),
               "data_root": str(data_root) if data_root else None,
               "by_method": {method: {"n": sum(row["method"] == method for row in results),
                                       "accepted": sum(row["method"] == method and row["accepted"]
                                                       for row in results)}
                             for method in sorted({row["method"] for row in results})},
               "by_label": {label: {"n": sum(row["target_label"] == label for row in results),
                                     "accepted": sum(row["target_label"] == label and row["accepted"]
                                                     for row in results)}
                            for label in sorted({row["target_label"] for row in results})}}
    routing_manifest = []
    for candidate in source_candidates:
        identity = (candidate["item_id"], candidate["method"], candidate["round"])
        structured_row = structured[identity]
        structured_is_robust = source_structured_pass(identity)
        tree_row = tree_results.get(identity)
        if structured_is_robust:
            route, robust = "structured_prompt", True
        elif tree_row and tree_row["accepted"]:
            route, robust = "prompt_tree", True
        else:
            route, robust = "unresolved", False
        routing_manifest.append({
            "item_id": candidate["item_id"], "method": candidate["method"],
            "source_round": candidate["round"], "target_label": candidate["target_label"],
            "route": route, "robust": robust,
            "structured_prompt": structured_row["structured_prompt"]
            if route == "structured_prompt" else None,
            "structured_robustness": structured_row["comparison"]["structured_robustness"],
            "prompt_tree": ({
                "requirements": tree_row["decomposition"]["requirements"],
                "requirement_presence_prompts": [
                    compile_requirement_leaf(requirement)
                    for requirement in tree_row["decomposition"]["requirements"]
                ],
                "requirement_fidelity_prompts": [
                    compile_fidelity_leaf(requirement)
                    for requirement in tree_row["decomposition"]["requirements"]
                ],
                "preservation_prompt": PRESERVATION_LEAF,
                "search_stats": tree_row["search_stats"],
                "confirmation_stats": tree_row["confirmation_stats"],
            } if tree_row else None),
        })
    _write_jsonl(output_dir / "hybrid_routing_manifest.jsonl", routing_manifest)
    (output_dir / "prompt_tree_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    markdown_path = write_markdown_summary(output_dir, results, summary)
    print(json.dumps(summary, indent=2))
    print(f"results={output_dir / 'prompt_tree_results.jsonl'}")
    print(f"routes={output_dir / 'hybrid_routing_manifest.jsonl'}")
    print(f"summary={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
