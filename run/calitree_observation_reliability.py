"""Small frozen-criteria reliability pilot. Dry run by default; no criterion repairs.

Reuse the original pilot loader, binding executor, and persistent request budget.
New repetitions have separate checkpoints. Restart only resumes the same draws.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import FrozenCriteria, FrozenCriteriaExecutor
from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter
from tests.unit.calitree.assumption3_probe import (
    BASELINE, FITTED, ROOT, BudgetedEngine, BudgetExhausted, ProviderUnavailable,
    load_inputs, save,
)

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_CASES = ["J03", "J10", "J13"]


def label_from_statuses(statuses):
    # Unknown/invalid observations cannot become a negative training target.
    if not statuses or any(s not in {"complete", "partial", "absent"} for s in statuses):
        return "unresolved"
    return "no" if "absent" in statuses else "partial" if "partial" in statuses else "yes"


def summarize(rows, draws, repeats):
    cases = {}
    for case, row in rows.items():
        observations = [draws.get(f"{rep}/{case}") for rep in range(repeats)]
        labels = [d["label"] if d else "missing" for d in observations]
        conditions = []
        for condition in row["plan"]["conditions"]:
            statuses = []
            for draw in observations:
                checks = {c["condition_id"]: c for c in (draw or {}).get("observations", {}).get("checks", [])}
                statuses.append(checks.get(condition["id"], {}).get("status", "invalid" if draw else "missing"))
            known = sum(s in {"complete", "partial", "absent"} for s in statuses)
            pairs = [(a, b) for i, a in enumerate(statuses) for b in statuses[i+1:]]
            conditions.append({"id": condition["id"], "statuses": statuses,
                               "known_draws": known, "counts": dict(Counter(statuses)),
                               "stable_and_known": known == repeats and len(set(statuses)) == 1,
                               "pairwise_status_agreement": sum(a == b and a not in {"invalid", "missing"}
                                                                for a, b in pairs) / len(pairs) if pairs else None})
        cases[case] = {"instruction": row["instruction"], "provisional_human_label": row["human_label"],
                       "labels": labels, "conditions": conditions,
                       "agreement_with_provisional_label": sum(s == row["human_label"] for s in labels),
                       "resolved_draws": sum(s in {"yes", "partial", "no"} for s in labels),
                       "all_conditions_stable_and_known": all(c["stable_and_known"] for c in conditions)}
    return {"cases": cases, "planned_repeats": repeats,
            "stable_known_conditions": sum(c["stable_and_known"] for r in cases.values() for c in r["conditions"]),
            "total_conditions": sum(len(r["conditions"]) for r in cases.values()),
            "interpretation": "Repeatability only; reliable correctness needs independent concept review. Labels are provisional."}


def freeze_manifest(out, rows, *, model=DEFAULT_MODEL, repeats=3, max_tokens=1024):
    if repeats < 2 or max_tokens < 1:
        raise ValueError("At least two repeats and a positive token cap are required")
    for row in rows.values():
        if row.get("annotation_review", {}).get("status") == "uncertain":
            raise ValueError("Exclude reviewed uncertain cases from the pilot")
        FrozenCriteria.bind(row["optimized_prompt"], row["instruction"], row["plan"])
        for item in row["images"]:
            if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Changed image bytes")
    files = [Path(__file__), ROOT / "critical/lm_engine/provider_api.py",
             ROOT / "tests/unit/calitree/assumption3_probe.py"]
    files += list((ROOT / "critical/core/optimization/prompt/calitree/decomposition").glob("*.py"))
    files += list((ROOT / "critical/core/prompts/templates/calitree_decomposition_casewise_v1").glob("*.txt"))
    calls = repeats * sum(len(r["plan"]["conditions"]) for r in rows.values())
    manifest = {"version": "calitree-fresh-reliability-v1", "model": model, "temperature": 0,
                "reasoning_effort": "none", "repeats": repeats, "max_tokens": max_tokens,
                "max_calls": calls, "completion_budget": calls * max_tokens,
                "schema_retries": 0, "http_attempts_per_call": 1,
                "rows": rows, "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    out.mkdir(parents=True, exist_ok=True)
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Protocol changed; use a new run directory")
    save(path, manifest)
    return manifest


def run_pilot(out, manifest, engine):
    rows, repeats = manifest["rows"], manifest["repeats"]
    if (engine.model, engine.temperature, engine.max_tokens) != (manifest["model"], 0, manifest["max_tokens"]):
        raise ValueError("Engine differs from frozen protocol")
    budget = BudgetedEngine(engine, out / "budget.json", manifest["max_calls"], manifest["completion_budget"])
    path = out / "results.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    draws = previous.get("draws", {})
    if previous.get("stop_reason", "").startswith("blocked:"):
        raise ValueError("Previous provider/budget failure is retained; inspect it before authorizing a new run")
    stop_reason = "running"

    def persist():
        result = {"draws": draws, "usage": budget.usage, "stop_reason": stop_reason,
                  "summary": summarize(rows, draws, repeats)}
        save(path, result)
        return result

    for rep in range(repeats):
        for case, row in rows.items():
            key = f"{rep}/{case}"
            if key in draws:
                continue
            directory = out / "draws" / str(rep) / case
            directory.mkdir(parents=True, exist_ok=True)
            executor = FrozenCriteriaExecutor(budget, checkpoint=CheckpointStore(directory / "checks.jsonl"), schema_retries=0)
            bound = FrozenCriteria.bind(row["optimized_prompt"], row["instruction"], row["plan"],
                                        feedback_used=row["feedback_used"], origin=row["criteria_origin"])
            try:
                observed = executor.observe(bound, prompt=row["optimized_prompt"], instruction=row["instruction"],
                                            evidence=dict(zip(("source_image", "edited_image"), [r["path"] for r in row["images"]])))
                if any(c["response"].get("finishReason") not in {None, "stop"} for c in executor.calls):
                    raise ValueError("Non-stop finish reason; observation is invalid")
                draws[key] = {"valid": True, "observations": observed,
                              "label": label_from_statuses([c["status"] for c in observed["checks"]])}
            except (BudgetExhausted, ProviderUnavailable) as exc:
                stop_reason = "blocked: " + str(exc)
                return persist()
            except ValueError as exc:
                # Malformed draws remain outcomes; do not resample or repair them.
                draws[key] = {"valid": False, "label": "unresolved", "error": str(exc)}
            finally:
                with (directory / "calls.jsonl").open("a") as f:
                    for call in executor.calls:
                        f.write(json.dumps(call) + "\n")
            persist()
            message = json.dumps({"draw": key, "label": draws[key]["label"], "usage": budget.usage})
            print(message, flush=True)
            with (out / "run.log").open("a") as f:
                f.write(message + "\n")
    stop_reason = "complete"
    return persist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", action="append")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=[DEFAULT_MODEL])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    rows = load_inputs(BASELINE, FITTED, args.case or DEFAULT_CASES)
    manifest = freeze_manifest(args.output_dir, rows, model=args.model, repeats=args.repeats, max_tokens=args.max_tokens)
    print(json.dumps({k: manifest[k] for k in ("model", "max_calls", "completion_budget", "repeats")}), flush=True)
    if not args.live:
        print("Dry run: protocol saved; no model calls or credentials loaded.")
        return
    require_live(args.live, context="fresh observation reliability pilot")
    creds = load_creds(model=args.model)
    if creds.provider != "openai" or creds.endpoints != ["https://api.openai.com/v1"]:
        raise ValueError("This pilot requires the official OpenAI endpoint; no fallback")
    engine = get_engine("gpt", model=args.model, creds=creds, temperature=0, max_tokens=args.max_tokens,
                        timeout=60, history=LLMHistoryWriter(args.output_dir / "llm-histories.log"))
    result = run_pilot(args.output_dir, manifest, engine)
    print(json.dumps(result["summary"], indent=2))
    if result["stop_reason"] != "complete":
        raise SystemExit(result["stop_reason"])


if __name__ == "__main__":
    main()
