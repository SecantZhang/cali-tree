"""Isolate rubric execution using frozen source-grounded development findings."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil

from critical import config
from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayExecutable
from .test_twoway_vision_aurora import hashes
from .test_optimized_aurora_prompts import write_json


BASE = config.PROJECT_ROOT / ".cache/calitree-tests/vision-grounded-development64-20260926/fresh_validation/results.json"


def test_executable_aggregation_development(hard_experiment):
    experiment = hard_experiment
    base = json.loads(BASE.read_text())
    assert base["manifest"]["model"] == experiment.engine.model
    destination = experiment.report_dir / "execution_development"
    destination.mkdir(parents=True, exist_ok=True)
    frozen = hashes()
    frozen[str(Path(__file__).relative_to(config.PROJECT_ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    helper = Path(__file__).with_name("helpers.py")
    frozen[str(helper.relative_to(config.PROJECT_ROOT))] = hashlib.sha256(helper.read_bytes()).hexdigest()
    manifest = {"source_hashes": frozen, "baseline_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
                "model": experiment.engine.model, "temperature": 0,
                "max_tokens": experiment.engine.max_tokens,
                "cohort": "All first 64 tasks, now development data",
                "observations_and_direct_predictions_reused": True,
                "no_human_labels_in_compilation_or_predicate_checks": True,
                "invalid_baseline_observations_preserved_in_denominator": True,
                "compile_each_unique_prompt_once_including_failures": True,
                "strategy": "Rubric-generated boolean predicates and ordered deterministic execution"}
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, "Cannot change a frozen execution run"
    else:
        write_json(manifest_path, manifest)
        for relative, digest in frozen.items():
            source = config.PROJECT_ROOT / relative
            assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
            snapshot = destination / "frozen_sources" / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, snapshot)
    algorithm = DecompositionTwoWayExecutable(experiment.engine, checkpoint=CheckpointStore(destination / "checkpoint.jsonl"))
    draws_path = destination / "draws.json"
    rows = json.loads(draws_path.read_text()) if draws_path.exists() else {}
    prompts = {case["optimized"] for case in base["manifest"]["cases"].values()}

    def compile_prompt(prompt):
        try:
            return prompt, algorithm.compile(prompt)
        except Exception as error:
            return prompt, error

    # A failed compilation belongs to its prompt. Do not repeatedly resample
    # that prompt just because several cases require it.
    with ThreadPoolExecutor(max_workers=4) as executor:
        compiled = dict(executor.map(compile_prompt, sorted(prompts)))

    def evaluate(key):
        row = base["results"][key]
        previous = row["arms"]["Decomposed"]
        if not previous["valid"]:
            prediction = {"label": "", "valid": False, "error_type": "MissingFrozenObservations",
                          "error": "Original observation failure preserved; no quality-based resampling"}
        else:
            try:
                # Only the rubric enters compile. Neither candidate labels nor
                # human labels enter any atomic evidence check.
                case = base["manifest"]["cases"][key]
                policy = compiled[case["optimized"]]
                if isinstance(policy, Exception):
                    raise policy
                result = algorithm.aggregate(policy, previous["trace"]["observations"])
                prediction = {"label": result.label, "rationale": result.rationale, "valid": True, "trace": result.trace}
            except Exception as error:
                prediction = {"label": "", "valid": False, "error_type": type(error).__name__,
                              "error": str(error) if isinstance(error, ValueError) else "Transport/model error; see call traces"}
        return key, {"expected": row["expected"], "task": row["task"],
                     "arms": {**row["arms"], "Executable": prediction}}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(evaluate, key) for key in base["results"] if key not in rows]
        for future in as_completed(futures):
            key, row = future.result()
            rows[key] = row
            write_json(draws_path, rows)
            write_json(destination / "calls.json", algorithm.calls)
            print(f"Execution {len(rows)}/64 {key}: {row['arms']['Executable']['label']} expected {row['expected']}", flush=True)
    metrics = {arm: {"correct": sum(r["arms"][arm]["label"] == r["expected"] for r in rows.values()),
                     "total": len(rows), "invalid": sum(not r["arms"][arm]["valid"] for r in rows.values())}
               for arm in ("Original", "Optimized", "Decomposed", "Executable")}
    improved = [key for key, row in rows.items() if row["arms"]["Executable"]["label"] == row["expected"] and row["arms"]["Decomposed"]["label"] != row["expected"]]
    regressed = [key for key, row in rows.items() if row["arms"]["Decomposed"]["label"] == row["expected"] and row["arms"]["Executable"]["label"] != row["expected"]]
    unchanged = all(hashlib.sha256((config.PROJECT_ROOT / p).read_bytes()).hexdigest() == digest for p, digest in frozen.items())
    report = {"manifest": manifest, "metrics": metrics, "improved_over_grounded": improved,
              "regressed_from_grounded": regressed, "pipeline_unchanged": unchanged,
              "results": rows}
    write_json(destination / "results.json", report)
    print(json.dumps(metrics, indent=2), flush=True)
    assert unchanged
    assert metrics["Executable"]["invalid"] == 0, "All failures preserved, including missing frozen observations"
    assert metrics["Executable"]["correct"] == 64, "Ground-truth mismatches preserved; this is development, not new validation"
