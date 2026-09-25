#!/usr/bin/env python3
"""Improve extracted atomic decision specs with representation and confirmation guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from tqdm.auto import tqdm

from run.aurora_prompt_repair import LiveJudge
from vejudge.checkpoint import CheckpointStore
from vejudge.experiments.aurora_prompt_repair import prompt_digest, robustness_stats
from vejudge.experiments.prompt_repair_report import write_html_report
from vejudge.experiments.structured_decision_test import (
    compile_alternate_prose_prompt,
    compile_controlled_prose_prompt,
    parse_decision_spec,
    select_candidate_rounds,
)
from vejudge.lm_engine import load_creds, openai_compat
from vejudge.lm_engine.gate import require_live
from vejudge.logging.llm_history import LLMHistoryWriter


PROPOSER_SYSTEM = """You improve a reusable, case-agnostic atomic decision specification
for a no/partial/yes image-edit judge. Return the complete revised JSON object only. Keep the
same schema and output contract. Modify only evidence_rules, decision_steps,
label_boundaries, and tie_breaks. Use atomic decisions, preserve explicit priority, and make
the no/partial and partial/yes boundaries executable. Never mention a particular image,
instruction, item, editor, prediction, target answer, training process, or feedback."""


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    temporary.replace(path)


def _seeded_key(candidate: dict[str, Any], seed: int) -> str:
    identity = "::".join(
        str(candidate.get(key, "")) for key in ("item_id", "method", "round")
    )
    return hashlib.sha256(f"{seed}::{identity}".encode("utf-8")).hexdigest()


def select_pilot_candidates(
    candidates: list[dict[str, Any]],
    structured: dict[tuple[str, str, int], dict[str, Any]],
    *,
    selection: str,
    limit: Optional[int],
    seed: int,
) -> list[dict[str, Any]]:
    """Select a deterministic pilot while alternating methods and their labels."""
    selected = list(candidates)
    if selection == "structured-failures":
        selected = [
            row
            for row in selected
            if not structured[(row["item_id"], row["method"], row["round"])][
                "comparison"
            ]["robustness_preserved"]
        ]
    if limit is None or limit >= len(selected):
        return sorted(selected, key=lambda row: _seeded_key(row, seed))
    if limit < 1:
        raise ValueError("limit must be at least 1")

    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in selected:
        buckets.setdefault(row["method"], {}).setdefault(row["target_label"], []).append(row)
    for label_buckets in buckets.values():
        for rows in label_buckets.values():
            rows.sort(key=lambda row: _seeded_key(row, seed))

    methods = sorted(buckets)
    label_offsets = {method: 0 for method in methods}
    result: list[dict[str, Any]] = []
    while len(result) < limit:
        made_progress = False
        for method in methods:
            labels = sorted(label for label, rows in buckets[method].items() if rows)
            if not labels:
                continue
            offset = label_offsets[method] % len(labels)
            label = labels[offset]
            result.append(buckets[method][label].pop(0))
            label_offsets[method] += 1
            made_progress = True
            if len(result) == limit:
                break
        if not made_progress:
            break
    return result


def _discover_data_root(run_dir: Path) -> Optional[Path]:
    for parent in (run_dir, *run_dir.parents):
        if parent.name == "vejudge" and parent.parent.name == "data":
            candidate = parent / "datasets" / "hidden-claude" / "main"
            if candidate.is_dir():
                return candidate
    return None


def _remap_case_paths(case: dict[str, Any], data_root: Optional[Path]) -> dict[str, Any]:
    if data_root is None:
        return case
    remapped = dict(case)
    marker = "/vejudge/.claude/data/"
    for key in ("source_image_path", "edited_image_path"):
        original = str(remapped.get(key) or "")
        if marker not in original:
            continue
        replacement = data_root / original.split(marker, 1)[1]
        if replacement.is_file():
            remapped[key] = str(replacement)
    return remapped


def _write_markdown_summary(
    output_dir: Path, results: list[dict[str, Any]], summary: dict[str, Any]
) -> Path:
    lines = [
        "# Atomic decision robustness pilot",
        "",
        f"- Accepted: {summary['accepted']}/{summary['n']} "
        f"({summary['robust_coverage']:.0%})",
        f"- Seed prompts passing the dual-render gate: "
        f"{summary['seed_dual_render_robust']}/{summary['n']}",
        f"- Calls: {summary['usage']['calls']}; tokens: "
        f"{summary['usage']['total_tokens']:,}; estimated cost: "
        f"${summary['usage']['estimated_cost_usd']:.4f}",
        "",
        "| Method | Target | Case | Seed C/A | Best C/A | Confirm | Outcome |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        evaluated = [round_row for round_row in row["rounds"] if "canonical_stats" in round_row]
        seed = evaluated[0]
        best = next(
            round_row for round_row in evaluated if round_row["round"] == row["best_round"]
        )
        lines.append(
            "| {method} | {target} | `{case}` | {seed_c}/10, {seed_a}/10 | "
            "{best_c}/10, {best_a}/10 | {confirm} | {outcome} |".format(
                method=row["method"], target=row["target_label"], case=row["item_id"],
                seed_c=seed["canonical_stats"]["target_hits"],
                seed_a=seed["alternate_stats"]["target_hits"],
                best_c=best["canonical_stats"]["target_hits"],
                best_a=best["alternate_stats"]["target_hits"],
                confirm=(
                    f"{best['confirmation_stats']['target_hits']}/"
                    f"{best['confirmation_stats']['n']}"
                    if best["confirmation_stats"]["n"] else "not reached"
                ),
                outcome="accepted" if row["accepted"] else "5 rounds exhausted",
            )
        )
    lines.extend([
        "",
        "C/A are target hits for the canonical and alternate renderings of the same "
        "atomic decision specification. Acceptance requires both search sets to score "
        "at least 8/10 and a fresh canonical confirmation set to score at least 16/20.",
        "",
    ])
    path = output_dir / "atomic_robustness_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def lint_spec(
    spec: dict[str, Any], case: dict[str, Any], parent_spec: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    errors = []
    try:
        parse_decision_spec(json.dumps(spec))
    except Exception as exc:
        errors.append(f"schema:{exc}")
    text = json.dumps(spec, ensure_ascii=False).lower()
    forbidden = [case.get("item_id"), case.get("task_uid"), case.get("model")]
    instruction = re.sub(r"\s+", " ", str(case.get("instruction") or "")).strip()
    if len(instruction) >= 12:
        forbidden.append(instruction)
    for value in forbidden:
        if value and str(value).lower() in text:
            errors.append("focal_identifier_or_instruction")
            break
    meta = ("target label", "feedback", "training example", "this case", "focal", "optimizer")
    if any(value in text for value in meta):
        errors.append("optimizer_meta_language")
    if parent_spec is not None:
        for immutable in ("objective", "output_contract"):
            if spec.get(immutable) != parent_spec.get(immutable):
                errors.append(f"immutable_field_changed:{immutable}")
    return {"valid": not errors, "errors": sorted(set(errors))}


class SpecProposer:
    def __init__(self, args, checkpoint):
        self.args, self.checkpoint, self.creds = args, checkpoint, load_creds(model=args.model)

    def propose(self, case_key: str, round_index: int, spec: dict[str, Any], feedback: str) -> dict[str, Any]:
        key = f"atomic-robustness::proposal::{case_key}::{round_index}::{prompt_digest(json.dumps(spec, sort_keys=True) + feedback)}"
        if self.checkpoint.has(key):
            row = dict(self.checkpoint.get(key)); row["checkpoint_hit"] = True; return row
        messages = [{"role": "system", "content": PROPOSER_SYSTEM}, {"role": "user", "content": (
            "Current atomic specification:\n" + json.dumps(spec, ensure_ascii=False, indent=2) +
            "\n\nAggregate behavioral failure signal:\n" + feedback
        )}]
        try:
            result = openai_compat.chat_completion(
                provider=self.creds.provider, endpoints=self.creds.endpoints, token=self.creds.token,
                model=self.args.model, messages=messages, max_tokens=3072,
                temperature=0.0, timeout=self.args.timeout, max_retries=4,
            )
            content = str(result.content or "")
            revised = parse_decision_spec(content)
            row = {"valid": True, "spec": revised, "raw_content": content, "error": None,
                   "model": result.model, "prompt_tokens": result.prompt_tokens,
                   "completion_tokens": result.completion_tokens, "total_tokens": result.total_tokens,
                   "latency_seconds": result.latency_s, "checkpoint_hit": False}
            self.checkpoint.put(key, row)
            return row
        except Exception as exc:
            return {"valid": False, "spec": None, "error": f"{type(exc).__name__}: {exc}",
                    "checkpoint_hit": False}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--search-repeats", type=int, default=10)
    parser.add_argument("--search-min-correct", type=int, default=8)
    parser.add_argument("--confirmation-repeats", type=int, default=20)
    parser.add_argument("--confirmation-min-correct", type=int, default=16)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--selection", choices=("all", "structured-failures"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=44)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_live(args.live, context="atomic-decision robustness experiment")
    run_dir = args.run_dir.expanduser().resolve()
    output_dir = (args.output_dir or run_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_root = args.data_root.expanduser().resolve() if args.data_root else _discover_data_root(run_dir)
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    args.model = args.model or config.get("model", "gpt-5.4-mini")
    if not 1 <= args.search_min_correct <= args.search_repeats:
        raise ValueError("search-min-correct must be within search-repeats")
    if not 1 <= args.confirmation_min_correct <= args.confirmation_repeats:
        raise ValueError("confirmation-min-correct must be within confirmation-repeats")

    traces = _jsonl(run_dir / "repair_traces.jsonl")
    candidates = [row for row in select_candidate_rounds(traces) if row["cohort"] == "accepted_primary"]
    baseline = {row["item_id"]: row for row in _jsonl(run_dir / "baseline_predictions.jsonl")}
    structured = {(row["item_id"], row["method"], row["round"]): row
                  for row in _jsonl(run_dir / "structured_decision_results.jsonl")}
    candidates = select_pilot_candidates(
        candidates, structured, selection=args.selection, limit=args.limit, seed=args.seed
    )
    checkpoint = CheckpointStore(output_dir / "atomic_robustness_checkpoints.jsonl")
    history = LLMHistoryWriter(output_dir / "atomic_robustness_llm_history.jsonl")
    judge = LiveJudge(model=args.model, checkpoint=checkpoint, history=history,
                      max_tokens=1024, timeout=args.timeout)
    proposer = SpecProposer(args, checkpoint)

    def calls(case, prompt, prefix, count):
        return [judge.judge(case, prompt, temperature=0.3,
                            call_id=f"{prefix}:{index:02d}") for index in range(count)]

    def run_track(candidate):
        identity = (candidate["item_id"], candidate["method"], candidate["round"])
        seed = structured[identity]
        case = _remap_case_paths(baseline[candidate["item_id"]], data_root)
        target = candidate["target_label"]
        spec = seed["extraction"]["spec"]
        rounds, feedback, accepted = [], "No prior guarded evaluation.", False
        best = None
        case_key = f"{candidate['method']}::{candidate['item_id']}::{candidate['round']}"
        for round_index in range(args.max_rounds):
            proposal = None
            if round_index:
                proposal = proposer.propose(case_key, round_index, spec, feedback)
                if not proposal.get("valid"):
                    rounds.append({"round": round_index, "proposal": proposal,
                                   "lint": {"valid": False, "errors": ["invalid_proposal"]},
                                   "accepted": False})
                    feedback = "The prior proposal was invalid; preserve the complete required schema."
                    continue
                candidate_spec = proposal["spec"]
                lint = lint_spec(candidate_spec, case, parent_spec=spec)
                if not lint["valid"]:
                    rounds.append({"round": round_index, "proposal": proposal,
                                   "lint": lint, "accepted": False})
                    feedback = "The prior proposal violated the case-agnostic specification contract."
                    continue
                spec = candidate_spec
            else:
                lint = lint_spec(spec, case)
            canonical = compile_controlled_prose_prompt(spec)
            alternate = compile_alternate_prose_prompt(spec)
            prefix = f"atomic:{case_key}:round:{round_index}"
            canonical_rows = calls(case, canonical, prefix + ":canonical:search", args.search_repeats)
            alternate_rows = calls(case, alternate, prefix + ":alternate:search", args.search_repeats)
            canonical_stats = robustness_stats(canonical_rows, target, required=args.search_min_correct)
            alternate_stats = robustness_stats(alternate_rows, target, required=args.search_min_correct)
            confirmation_rows = []
            confirmation_stats = robustness_stats([], target, required=args.confirmation_min_correct)
            if canonical_stats["robust"] and alternate_stats["robust"]:
                confirmation_rows = calls(case, canonical, prefix + ":canonical:confirm",
                                          args.confirmation_repeats)
                confirmation_stats = robustness_stats(
                    confirmation_rows, target, required=args.confirmation_min_correct)
            accepted = bool(confirmation_stats["robust"])
            rank = [min(canonical_stats["target_hit_rate"], alternate_stats["target_hit_rate"]),
                    confirmation_stats["target_hit_rate"],
                    canonical_stats["target_hit_rate"] + alternate_stats["target_hit_rate"],
                    -len(canonical)]
            row = {"round": round_index, "spec": spec, "proposal": proposal, "lint": lint,
                   "canonical_prompt": canonical, "alternate_prompt": alternate,
                   "canonical_search": canonical_rows, "canonical_stats": canonical_stats,
                   "alternate_search": alternate_rows, "alternate_stats": alternate_stats,
                   "confirmation": confirmation_rows, "confirmation_stats": confirmation_stats,
                   "rank": rank, "accepted": accepted}
            rounds.append(row)
            if best is None or rank > best[0]:
                best = (rank, row)
            if accepted:
                break
            feedback = (
                f"Human target category: {target}. Canonical distribution: "
                f"{json.dumps(canonical_stats['label_distribution'], sort_keys=True)}. "
                f"Alternate distribution: {json.dumps(alternate_stats['label_distribution'], sort_keys=True)}. "
                f"Confirmation distribution: {json.dumps(confirmation_stats['label_distribution'], sort_keys=True)}. "
                "Revise only the reusable boundary decisions causing this aggregate mismatch."
            )
        best_row = best[1] if best else None
        return {"item_id": candidate["item_id"], "method": candidate["method"],
                "source_round": candidate["round"], "target_label": target,
                "accepted": accepted,
                "stop_reason": "accepted_two_render_search_and_confirmation" if accepted else "max_rounds_exhausted",
                "rounds": rounds, "best_round": best_row["round"] if best_row else None,
                "best_confirmation_stats": best_row["confirmation_stats"] if best_row else None,
                "prior_semantic_json_robust": seed["comparison"]["robustness_preserved"]}

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_track, candidate) for candidate in candidates]
        with tqdm(total=len(futures), desc="Atomic robustness", unit="track") as bar:
            for future in as_completed(futures):
                results.append(future.result()); bar.update(1)
    results.sort(key=lambda row: (row["item_id"], row["method"], row["source_round"]))
    _write_jsonl(output_dir / "atomic_robustness_results.jsonl", results)
    accepted_rows = [row for row in results if row["accepted"]]
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
    method_breakdown = {
        method: {
            "n": sum(row["method"] == method for row in results),
            "accepted": sum(row["method"] == method and row["accepted"] for row in results),
        }
        for method in sorted({row["method"] for row in results})
    }
    label_breakdown = {
        label: {
            "n": sum(row["target_label"] == label for row in results),
            "accepted": sum(
                row["target_label"] == label and row["accepted"] for row in results
            ),
        }
        for label in sorted({row["target_label"] for row in results})
    }
    summary = {"schema_version": 1, "experiment": "atomic_decision_robustness",
               "model": args.model, "n": len(results), "accepted": len(accepted_rows),
               "robust_coverage": len(accepted_rows) / len(results) if results else None,
               "prior_semantic_json_robust": sum(row["prior_semantic_json_robust"] for row in results),
               "seed_dual_render_robust": sum(
                   bool(row["rounds"])
                   and row["rounds"][0].get("canonical_stats", {}).get("robust")
                   and row["rounds"][0].get("alternate_stats", {}).get("robust")
                   for row in results
               ),
               "by_method": method_breakdown, "by_label": label_breakdown,
               "usage": usage,
               "pricing": {"input_usd_per_million_tokens": 0.75,
                           "output_usd_per_million_tokens": 4.5,
                           "note": "Estimate excludes cache discounts and provider markups."},
               "selection": {"mode": args.selection, "limit": args.limit, "seed": args.seed,
                             "source_candidates": len([row for row in select_candidate_rounds(traces)
                                                       if row["cohort"] == "accepted_primary"]),
                             "selected": len(results)},
               "source_run_dir": str(run_dir), "output_dir": str(output_dir),
               "data_root": str(data_root) if data_root else None,
               "settings": {key: getattr(args, key) for key in (
                   "search_repeats", "search_min_correct", "confirmation_repeats",
                   "confirmation_min_correct", "max_rounds")},
               "stop_reasons": {reason: sum(row["stop_reason"] == reason for row in results)
                                for reason in sorted({row["stop_reason"] for row in results})}}
    (output_dir / "atomic_robustness_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    markdown_path = _write_markdown_summary(output_dir, results, summary)
    if output_dir == run_dir:
        write_html_report(run_dir)
        print(f"report={run_dir / 'report.html'}")
    print(json.dumps(summary, indent=2))
    print(f"results={output_dir / 'atomic_robustness_results.jsonl'}")
    print(f"summary={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
