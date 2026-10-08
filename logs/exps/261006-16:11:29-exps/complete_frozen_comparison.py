"""Complete previously unattempted final checks after the opaque-ID parser fix.

No compilation, proposals, selection or program edits are rerun. Original results
and requests are preserved. Appended checks share the original durable budget.
"""
from pathlib import Path
import sys
import json
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import restore_program, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.compiler import ProgramCompiler
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.optimization.program import RepeatedEvaluator
from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_program_optimization import code_hashes, bind_cases, write_report


def main():
    require_live("--live" in sys.argv)
    parent = Path(__file__).resolve().parent
    output = parent / "binding_repair"
    protocol = json.loads((parent / "manifest.json").read_text())
    original = json.loads((parent / "results.json").read_text())
    seed = json.loads((parent / "seed.json").read_text())
    selected = json.loads((parent / "selected.json").read_text())
    manifest = {"purpose": "Complete frozen comparison after allowing hyphens in opaque identifiers",
                "parent_results_sha256": sha256((parent / "results.json").read_bytes()).hexdigest(),
                "seed": seed["program_ref"], "selected": selected["program_ref"],
                "code_hashes": code_hashes(), "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "new_optimization": False, "shared_budget": str(parent / "budget.json")}
    if (output / "manifest.json").exists() and json.loads((output / "manifest.json").read_text()) != manifest:
        raise ValueError("Frozen repair manifest changed")
    save_json(output / "manifest.json", manifest)
    for row in protocol["partitions"]["evaluation"]:
        assert row["image_hashes"] == {k: sha256(Path(v).read_bytes()).hexdigest() for k, v in row["evidence"].items()}
    history = LLMHistoryWriter(parent / "llm-histories.log")
    calls = DurableCalls(parent, lambda cap: get_engine("gpt", model=protocol["model"], creds=load_creds(engine="gpt"),
              history=history, temperature=0, max_tokens=cap, max_http_attempts=1, timeout=60),
              identity={"model": protocol["model"], "temperature": 0, "reasoning_effort": "none"},
              **{k: protocol[k] for k in ("max_calls", "max_completion_tokens", "reserve_calls", "reserve_tokens")})
    result = {"status": "running", "scope": original["scope"] + "; frozen-program parser correction, no reoptimization",
              "search": original["search"], "original_binding_failures": original["binding_failures"]}
    before = calls.budget["calls"]
    try:
        cases, failures = bind_cases(protocol["partitions"]["evaluation"], ProgramCompiler(calls), final=True)
        result["binding_failures"] = failures
        evaluator = RepeatedEvaluator(ProgramExecutor(ModelChecker(calls),
                                      checkpoint=CheckpointStore(parent / "observations.jsonl")))
        result["evaluation"] = {}
        for name, envelope in (("seed", seed), ("optimized", selected)):
            result["evaluation"][name] = evaluator.evaluate(restore_program(envelope), cases, repeats=3,
                                                        namespace="final/" + name, final=True)
            save_json(output / "results.json", {**result, "budget": calls.budget})
        result["status"] = "completed"
    except Exception as exc:
        result.update(status="stopped", error=f"{type(exc).__name__}: {exc}")
    result.update(budget=calls.budget, calls_this_completion=calls.budget["calls"] - before,
                  total_additional_calls=calls.budget["calls"] - original["budget"]["calls"])
    save_json(output / "results.json", result)
    write_report(output, result)
    with (parent / "run.log").open("a") as log:
        log.write(json.dumps({"phase": "binding_parser_completion", "status": result["status"],
                              "total_calls": calls.budget["calls"]}) + "\n")
    print(json.dumps({"status": result["status"], "calls": calls.budget["calls"],
                      "additional_calls": result["total_additional_calls"], "error": result.get("error")}))


if __name__ == "__main__":
    main()
