"""Probe real AURORA instructions against the unchanged bounded compiler."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWay
from .test_optimized_aurora_prompts import FIXTURE, source_hashes, write_json


def test_optimized_aurora_instruction_coverage(hard_experiment):
    experiment = hard_experiment
    data = json.loads(FIXTURE.read_text())
    frozen = source_hashes()
    algorithm = DecompositionTwoWay(experiment.engine)
    path = experiment.report_dir / "optimized_aurora_instruction_coverage.json"
    assert not path.exists(), "Preserve the first instruction diagnostic"

    def probe(key):
        instruction = data["cases"][key]["instruction"]
        try:
            plan = algorithm.decompose(instruction)
            result = {"status": "parsed", "plan": plan.to_dict()}
        except ValueError as error:
            result = {"status": "failed", "error_type": type(error).__name__, "reason": str(error)}
        return key, {"instruction": instruction, **result}

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(probe, key) for key in data["optimized_prompts"]]
        for future in as_completed(futures):
            key, result = future.result()
            results[key] = result
            print(f"Instruction {key}: {result}", flush=True)
    report = {"model": experiment.engine.model, "temperature": 0, "results": results,
              "schema_valid": sum(row["status"] == "parsed" for row in results.values()),
              "total": 7, "source_hashes": frozen, "pipeline_unchanged": frozen == source_hashes(),
              "limitation": "A parsed plan is not proof that actions, targets, or relations were retained. No synthetic evidence or human labels were supplied."}
    write_json(path, report)
    write_json(experiment.report_dir / "optimized_aurora_instruction_calls.json", experiment.calls)
    assert report["pipeline_unchanged"]
    assert report["schema_valid"] == 7, "Unsupported real instructions; first diagnostic preserved"
