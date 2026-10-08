"""Structural optimizer runner. Default preflight; --live executes the frozen pilot."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import random
from zoneinfo import ZoneInfo

from critical.checkpoint import CheckpointStore
from critical.core.decision.artifacts import digest, export_program, restore_program, save_json
from critical.core.decision.calls import DurableCalls, BudgetExhausted, ProviderStopped, CallFailure
from critical.core.decision.compiler import ProgramCompiler, TEMPLATES
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.decision.models import BoundPlan, Outcome
from critical.core.optimization.program import Case, StructuralOptimizer, RepeatedEvaluator, ModelEditProposer
from critical.core.optimization.program.demo import RUBRIC, DemoChecker, DemoProposer, demo_cases, seed_program
from critical.core.optimization.program.evaluation import source_group, validate_partitions
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.database.dl_aurora.assets import materialize_output_panel

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".cache/calitree-tests/vision-balanced-calibration-reference-collection-20260926/manifest.json"
MODEL = "gpt-6-luna"


def cohort(reference=REFERENCE, data_root=None):
    data_root = Path(data_root or ROOT / "data/aurora/bench")
    reference = Path(reference)
    collection = json.loads(reference.read_text())["cases"]
    reviews = json.loads((ROOT / "docs/experiments/calitree_case_reviews.json").read_text())["cases"]
    excluded = {r["image_sha256"][0] for r in reviews.values() if r.get("annotation_review", {}).get("status") == "uncertain"}
    rng = random.Random(20261006)
    selected, used = {}, set()
    for label in ("yes", "partial", "no"):
        candidates = sorted((r for r in collection.values() if r["target_label"] == label), key=lambda r: r["item_id"])
        rng.shuffle(candidates)
        chosen = []
        for raw in candidates:
            source = data_root / raw["source_path"]
            if sha256(source.read_bytes()).hexdigest() in excluded or raw.get("annotation_review", {}).get("status") == "uncertain":
                continue
            group = source_group(source)
            if group in used:
                continue
            row = materialize_output_panel(data_root, raw)
            evidence = {"source_image": str(source.resolve()), "edited_image": str((data_root / row["edited_path"]).resolve())}
            chosen.append({"id": row["item_id"], "group": group, "instruction": row["instruction"],
                           "target": label, "evidence": evidence,
                           "image_hashes": {k: sha256(Path(v).read_bytes()).hexdigest() for k, v in evidence.items()}})
            used.add(group)
            if len(chosen) == 4:
                break
        if len(chosen) != 4:
            raise ValueError(f"Insufficient independent {label} cases")
        selected[label] = chosen
    return {"fit": [r for label in ("no", "partial", "yes") for r in selected[label][:2]],
            "selection": [selected[label][2] for label in ("no", "partial", "yes")],
            "evaluation": [selected[label][3] for label in ("no", "partial", "yes")]}


def code_hashes():
    files = [Path(__file__), ROOT / "critical/core/optimization/prompt/calitree/node/program_leaf.py",
             ROOT / "critical/core/optimization/prompt/calitree/builder.py",
             ROOT / "critical/lm_engine/lm_template/base.py", ROOT / "critical/lm_engine/provider_api.py"]
    for directory in (ROOT / "critical/core/decision", ROOT / "critical/core/optimization/program"):
        files.extend(directory.glob("*.py"))
    files.extend(TEMPLATES.glob("*.txt"))
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


def preflight(output):
    output = Path(output)
    path = output / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest["code_hashes"] != code_hashes():
            raise ValueError("Code or templates changed; frozen run cannot be resumed")
        for rows in manifest["partitions"].values():
            for row in rows:
                if row["image_hashes"] != {k: sha256(Path(v).read_bytes()).hexdigest() for k, v in row["evidence"].items()}:
                    raise ValueError("Frozen images changed")
        return manifest
    manifest = {"version": "calitree-program-pilot-v1", "model": MODEL, "temperature": 0,
                "reasoning_effort": "none", "seed": 20261006, "rubric": RUBRIC,
                "partitions": cohort(), "code_hashes": code_hashes(),
                "reference_sha256": sha256(REFERENCE.read_bytes()).hexdigest(),
                "max_calls": 600, "max_completion_tokens": 768000,
                "reserve_calls": 80, "reserve_tokens": 90112,
                "max_checks": 4, "rounds": 2, "beam_width": 2, "proposals_per_parent": 2,
                "scope": "Exploratory reuse of previously observed reference cases; evaluation is held out only within this run"}
    save_json(path, manifest)
    (output / "run.log").touch()
    (output / "llm-histories.log").touch()
    return manifest


def bind_cases(rows, compiler, *, final=False):
    cases, failures = [], []
    for row in rows:
        try:
            plan = compiler.bind(row["instruction"], final=final)
        except (ValueError, KeyError, TypeError, CallFailure) as exc:
            # Preserve the selected case and count all its predictions unresolved.
            plan = BoundPlan(row["instruction"], ())
            failures.append({"case_id": row["id"], "error": str(exc)})
        cases.append(Case(row["id"], row["group"], plan, row["evidence"], row["target"]))
    return tuple(cases), failures


def write_report(output, result):
    lines = ["# CaliTree decision-program optimization", "", result.get("scope", ""), "",
             "Status: " + result["status"], ""]
    if "error" in result:
        lines += ["Run stopped: " + result["error"], ""]
    if "search" in result:
        search = result["search"]
        lines += [f"Selected program: `{search['program_ref']}`", f"Support: {search['support_status']}",
                  f"Search stop: {search['stop_reason']}", f"Candidate records: {len(search['lineage'])}", ""]
    if "evaluation" in result:
        lines += ["| Arm | Accuracy | Balanced accuracy | Macro F1 | Coverage | Repeat flips |", "|---|---:|---:|---:|---:|---:|"]
        for name, r in result["evaluation"].items():
            lines.append("| " + name + " | " + " | ".join(f"{100*r[k]:.1f}%" for k in
                          ("accuracy", "balanced_accuracy", "macro_f1", "coverage", "flip_rate")) + " |")
        lines += ["", "Three evaluation cases cannot establish generalization. Atomic repeatability is not semantic correctness."]
    if "budget" in result:
        lines += ["", f"Model calls: {result['budget']['calls']}; completion tokens used or reserved: {result['budget']['completion_tokens_or_reserved']}."]
    (Path(output) / "report.md").write_text("\n".join(lines) + "\n")


def execute_live(output, manifest, engine_factory):
    output = Path(output)
    calls = DurableCalls(output, engine_factory, identity={"model": MODEL, "temperature": 0, "reasoning_effort": "none"},
                         **{k: manifest[k] for k in ("max_calls", "max_completion_tokens", "reserve_calls", "reserve_tokens")})
    result = {"status": "running", "scope": manifest["scope"]}
    checkpoint = CheckpointStore(output / "observations.jsonl")
    compiler = ProgramCompiler(calls)
    executor = ProgramExecutor(ModelChecker(calls), checkpoint=checkpoint)
    evaluator = RepeatedEvaluator(executor)
    try:
        # Evaluation instructions and labels never enter seed compilation or search.
        seed = compiler.compile(manifest["rubric"], [r["instruction"] for r in manifest["partitions"]["fit"]])
        save_json(output / "seed.json", export_program(seed))
        fit, fit_failures = bind_cases(manifest["partitions"]["fit"], compiler)
        selection, selection_failures = bind_cases(manifest["partitions"]["selection"], compiler)
        result["binding_failures"] = fit_failures + selection_failures
        frozen = output / "leaves.json"
        if frozen.exists():
            bundle = json.loads(frozen.read_text())
            from critical.core.optimization.prompt.calitree.node.program_leaf import validate_program_leaves
            validate_program_leaves(bundle)
        else:
            optimizer = StructuralOptimizer(ModelEditProposer(calls), evaluator,
                          **{k: manifest[k] for k in ("rounds", "beam_width", "proposals_per_parent")})
            bundle = CaliTreeBuilder.build_program_leaves(seed, fit, optimizer=optimizer, selection_cases=selection)
            save_json(frozen, bundle)
        search = bundle["nodes"]["leaf:shared"]["result"]
        result["search"] = search
        save_json(output / "selected.json", {"program_ref": search["program_ref"], "program": search["program"]})
        # Freeze before even binding the evaluation instructions.
        evaluation, failures = bind_cases(manifest["partitions"]["evaluation"], compiler, final=True)
        result["binding_failures"].extend(failures)
        validate_partitions(fit, selection, evaluation)
        result["evaluation"] = {}
        for arm, program in (("seed", seed), ("optimized", restore_program(search))):
            result["evaluation"][arm] = evaluator.evaluate(program, evaluation, repeats=3,
                                                namespace="final/" + arm, final=True)
            save_json(output / "results.json", {**result, "budget": calls.budget})
        result["status"] = "completed"
    except (ProviderStopped, BudgetExhausted, CallFailure, ValueError, KeyError, TypeError) as exc:
        result.update(status="stopped", error=f"{type(exc).__name__}: {exc}")
    result["budget"] = calls.budget
    save_json(output / "results.json", result)
    write_report(output, result)
    with (output / "run.log").open("a") as log:
        log.write(json.dumps({"status": result["status"], "calls": calls.budget["calls"], "error": result.get("error")}) + "\n")
    return result


def run_demo(output):
    output = Path(output)
    fit, selection, evaluation = demo_cases(output / "fixtures")
    executor = ProgramExecutor(DemoChecker(), checkpoint=CheckpointStore(output / "observations.jsonl"))
    evaluator = RepeatedEvaluator(executor)
    bundle = CaliTreeBuilder.build_program_leaves(seed_program(), fit,
              optimizer=StructuralOptimizer(DemoProposer(), evaluator), selection_cases=selection)
    save_json(output / "leaves.json", bundle)
    search = bundle["nodes"]["leaf:shared"]["result"]
    result = {"status": "completed", "scope": "Synthetic offline contract demonstration; zero provider calls",
              "search": search, "evaluation": {
                  "seed": evaluator.evaluate(seed_program(), evaluation, repeats=3, namespace="final/seed"),
                  "optimized": evaluator.evaluate(restore_program(search), evaluation, repeats=3, namespace="final/optimized")}}
    save_json(output / "results.json", result)
    write_report(output, result)
    (output / "run.log").write_text("Offline demonstration completed.\n")
    (output / "llm-histories.log").write_text("No provider calls.\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs/exps" /
                        (datetime.now(ZoneInfo("America/Chicago")).strftime("%y%m%d-%H:%M:%S") + "-exps"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--demo", action="store_true")
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--report", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.report:
        write_report(args.output_dir, json.loads((args.output_dir / "results.json").read_text()))
        return
    if args.demo:
        result = run_demo(args.output_dir)
    else:
        if args.resume and not (args.output_dir / "manifest.json").exists():
            parser.error("Resume requires an existing manifest")
        manifest = preflight(args.output_dir)
        if not args.live:
            print(json.dumps({"preflight": "ready", "cases": 12, "manifest": str(args.output_dir / "manifest.json"),
                              "max_calls": 600, "completion_token_ceiling": 768000}))
            return
        from critical.lm_engine import get_engine, load_creds, require_live
        from critical.logging.llm_history import LLMHistoryWriter
        require_live(True)
        history = LLMHistoryWriter(args.output_dir / "llm-histories.log")
        result = execute_live(args.output_dir, manifest, lambda cap: get_engine("gpt", model=MODEL, creds=load_creds(engine="gpt"),
                              history=history, max_tokens=cap, temperature=0, max_http_attempts=1, timeout=60))
    print(json.dumps({"status": result["status"], "error": result.get("error"), "output": str(args.output_dir)}))


if __name__ == "__main__":
    main()
