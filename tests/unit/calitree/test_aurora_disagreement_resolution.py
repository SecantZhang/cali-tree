"""Controlled development ablation using frozen independent predictions."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

from critical import config
from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayVision, SemanticRubric
from critical.core.optimization.prompt.calitree.decomposition.models import DecompositionResult
from .test_twoway_vision_aurora import hashes
from .test_optimized_aurora_prompts import write_json


BASE = config.PROJECT_ROOT / ".cache/calitree-tests/vision-v2-20260926/validation/results.json"


def test_disagreement_resolution_development(hard_experiment):
    base = json.loads(BASE.read_text())
    experiment = hard_experiment
    assert base["manifest"]["model"] == experiment.engine.model
    destination = experiment.report_dir / "resolution_development"
    destination.mkdir(parents=True, exist_ok=True)
    frozen = hashes()
    frozen[str(Path(__file__).relative_to(config.PROJECT_ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {"source_hashes": frozen, "baseline_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
                "model": experiment.engine.model, "temperature": 0,
                "cohort": "All 50 previously evaluated validation tasks, now development data",
                "ground_truth_not_provided_to_resolver": True,
                "baseline_and_decomposed_predictions_reused": True}
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest
    else:
        write_json(manifest_path, manifest)
    algorithm = DecompositionTwoWayVision(experiment.engine, checkpoint=CheckpointStore(destination / "checkpoint.jsonl"))
    path = destination / "draws.json"
    rows = json.loads(path.read_text()) if path.exists() else {}

    def resolve(key):
        row = base["results"][key]
        old = row["arms"]["Decomposed"]
        case = base["manifest"]["cases"][key]
        evidence = {k+"_image": str(config.PROJECT_ROOT / case[k+"_image"]) for k in ("source", "edited")}
        try:
            result = algorithm.resolve(SemanticRubric.from_dict(old["trace"]["rubric"]),
                                       DecompositionResult(old["label"], old["rationale"], old["trace"]),
                                       row["arms"]["Optimized"], evidence)
            prediction = {"label": result.label, "rationale": result.rationale, "valid": True, "trace": result.trace}
        except Exception as error:
            prediction = {"label": "", "valid": False, "error_type": type(error).__name__}
        return key, {"expected": row["expected"], "substantive_rewrite": row["substantive_rewrite"],
                     "arms": {**row["arms"], "Resolved": prediction}}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(resolve, key) for key in base["results"] if key not in rows]
        for future in as_completed(futures):
            key, row = future.result()
            rows[key] = row
            write_json(path, rows)
            write_json(destination / "calls.json", algorithm.calls)
            print(f"Resolution {len(rows)}/50 {key}: {row['arms']['Resolved']['label']} expected {row['expected']}", flush=True)
    metrics = {}
    for name, group in (("all", list(rows.values())), ("rewritten", [r for r in rows.values() if r["substantive_rewrite"]])):
        metrics[name] = {arm: {"correct": sum(r["arms"][arm]["label"] == r["expected"] for r in group),
                              "total": len(group), "invalid": sum(not r["arms"][arm]["valid"] for r in group)}
                         for arm in ("Original", "Optimized", "Decomposed", "Resolved")}
    report = {"manifest": manifest, "metrics": metrics, "results": rows, "resolver_calls": len(algorithm.calls)}
    write_json(destination / "results.json", report)
    print(json.dumps(metrics, indent=2), flush=True)
    assert metrics["all"]["Resolved"]["invalid"] == 0
    assert metrics["all"]["Resolved"]["correct"] == 50, "Remaining mismatches preserved; development is not fresh validation"
