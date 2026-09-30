"""Diagnostic on actual cached rewritten AURORA rubrics, without approximation.

The core compiler and vision boundary are unchanged. Unsupported semantics are
recorded as failures, never replaced with a handwritten reducer or guessed data.
"""

import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from critical import config
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWay
from critical.experiments.aurora_prompt_repair import parse_judgment
from critical.lm_engine import get_engine, load_creds


FIXTURE = Path(__file__).parent / "fixtures" / "optimized_aurora_prompts.json"
REPEATS = 3
TEMPERATURE = 0.3


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def source_hashes():
    core = config.PROJECT_ROOT / "critical/core/optimization/prompt/calitree/decomposition"
    prompts = config.PROJECT_ROOT / "critical/core/prompts/templates/calitree_decomposition_v1"
    paths = [*core.glob("*.py"), *prompts.glob("*.txt"), Path(__file__), FIXTURE]
    return {str(path.relative_to(config.PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_cached_prompts_are_substantive_rewrites_with_frozen_case_selection():
    data = json.loads(FIXTURE.read_text())
    assert len(data["optimized_prompts"]) == 7
    assert len(data["cases"]) == 10
    assert data["provenance"]["focal_only"] is True
    assert sha(data["seed_prompt"]) == data["seed_prompt_sha256"]
    assert Counter(case["target_label"] for case in data["cases"].values()) == {"yes": 3, "no": 3, "partial": 4}
    assert len({case["task_uid"] for case in data["cases"].values()}) == 10
    for key, row in data["optimized_prompts"].items():
        assert row["prompt"].split() != data["seed_prompt"].split()
        assert sha(row["prompt"]) == row["prompt_sha256"]
        assert row["focal_case"] == key
        assert len(set(row["transfer_cases"])) == 2
        assert key not in row["transfer_cases"]
        assert set(row["transfer_cases"]) <= data["cases"].keys()


def image_judgment(engine, case, prompt):
    """No human target, optimizer name, or case ID is included in a model input."""
    text = f"Instruction: {case['instruction']}\nThe first image is SOURCE; the second is EDITED."
    media = [{"type": "image", "path": str(config.PROJECT_ROOT / case[f"{kind}_image"])}
             for kind in ("source", "edited")]
    try:
        response = engine.generate(text, media_inputs=media, system=prompt)
        parsed = parse_judgment(str(response.get("content") or ""))
        return {**parsed, "response": response, "user": text, "media": media}
    except Exception as error:
        return {"label": "", "valid": False, "rationale": "", "error": type(error).__name__}


def score(rows):
    return {"correct": sum(row["label"] == row["expected"] for row in rows),
            "total": len(rows), "invalid": sum(not row.get("valid", False) for row in rows),
            "counts": dict(Counter(row["label"] for row in rows))}


def test_current_decomposition_on_cached_optimized_image_prompts(hard_experiment):
    experiment = hard_experiment
    destination = experiment.report_dir
    final_path = destination / "optimized_aurora_results.json"
    assert not final_path.exists(), "Preserve the first diagnostic result; do not tune and overwrite"
    data = json.loads(FIXTURE.read_text())
    # Check all media before any billable work. Do not silently substitute images.
    for case in data["cases"].values():
        for kind in ("source", "edited"):
            path = config.PROJECT_ROOT / case[f"{kind}_image"]
            assert path.is_file(), f"Missing cached image: {path}"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == case[f"{kind}_image_sha256"]
    frozen_hashes = source_hashes()
    manifest = {"source_hashes": frozen_hashes, "dataset": data,
                "model": experiment.engine.model, "engine": experiment.engine.name,
                "compilation_temperature": 0, "judgment_temperature": TEMPERATURE,
                "repeats": REPEATS, "no_new_optimization": True,
                "no_label_feedback_into_compilation": True,
                "unsupported_semantics_are_failures": True,
                "scope": "Seven known focal repair cases plus two other task groups per prompt; transfer is held out from the focal-only search, not a new population sample."}
    manifest_path = destination / "optimized_aurora_manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest
    else:
        write_json(manifest_path, manifest)

    algorithm = DecompositionTwoWay(experiment.engine)
    compilations = {}
    compilation_path = destination / "optimized_aurora_compilations.json"
    if compilation_path.exists():
        compilations = json.loads(compilation_path.read_text())

    def compile_one(item):
        key, row = item
        try:
            policy = algorithm.compile(row["prompt"])
            result = {"status": "compiled", "policy": policy.to_dict()}
        except ValueError as error:
            result = {"status": "failed", "error_type": type(error).__name__, "reason": str(error)}
        result["attempts"] = algorithm.rubric_compiler.attempts.get(row["prompt"], [])
        # Image-only judging must pass the real adapter boundary, without fabricated evidence.
        try:
            judgment = algorithm.judge(row["prompt"], {"input": {"instruction": data["cases"][key]["instruction"]},
                                                       "images": [data["cases"][key]["source_image"], data["cases"][key]["edited_image"]]})
            result["image_boundary"] = {"status": "succeeded", "judgment": judgment}
        except ValueError as error:
            result["image_boundary"] = {"status": "failed", "reason": str(error)}
        return key, result

    missing = [(key, row) for key, row in data["optimized_prompts"].items() if key not in compilations]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(compile_one, item) for item in missing]
        for future in as_completed(futures):
            key, result = future.result()
            compilations[key] = result
            write_json(compilation_path, compilations)
            print(f"Compiler {key}: {result['status']} {result.get('reason', '')}", flush=True)
    if experiment.calls:
        write_json(destination / "optimized_aurora_compilation_calls.json", experiment.calls)

    vision_engine = get_engine(experiment.engine.name, model=experiment.engine.model,
                               creds=load_creds(engine=experiment.engine.name),
                               temperature=TEMPERATURE, max_tokens=1024, timeout=60)
    # Original repeats are sampled once per image pair and reused as explicit
    # comparator draws for multiple prompt transfers; these are not independent new examples.
    jobs = [(f"original:{key}:{repeat}", "Original", None, key, repeat, data["seed_prompt"])
            for key in data["cases"] for repeat in range(REPEATS)]
    jobs += [(f"optimized:{key}:{case_id}:{repeat}", "Optimized", key, case_id, repeat, row["prompt"])
             for key, row in data["optimized_prompts"].items()
             for case_id in [key, *row["transfer_cases"]] for repeat in range(REPEATS)]
    results = {}
    draw_path = destination / "optimized_aurora_draws.json"
    if draw_path.exists():
        results = json.loads(draw_path.read_text())

    def evaluate(job):
        call_id, arm, prompt_id, case_id, repeat, prompt = job
        case = data["cases"][case_id]
        row = image_judgment(vision_engine, case, prompt)
        return call_id, {"arm": arm, "prompt_id": prompt_id, "case_id": case_id,
                         "repeat": repeat, "expected": case["target_label"], **row}

    missing = [job for job in jobs if job[0] not in results]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(evaluate, job) for job in missing]
        for index, future in enumerate(as_completed(futures), 1):
            call_id, row = future.result()
            results[call_id] = row
            write_json(draw_path, results)
            if index % 12 == 0 or index == len(missing):
                print(f"Fresh image judgments: {index}/{len(missing)}; completed failures stay recorded", flush=True)

    metrics, comparisons = {}, {}
    for cohort in ("focal", "transfer"):
        original, optimized = [], []
        for key, prompt in data["optimized_prompts"].items():
            ids = [key] if cohort == "focal" else prompt["transfer_cases"]
            for case_id in ids:
                for repeat in range(REPEATS):
                    original.append(results[f"original:{case_id}:{repeat}"])
                    optimized.append(results[f"optimized:{key}:{case_id}:{repeat}"])
        metrics[cohort] = {"Original": score(original), "Optimized": score(optimized),
                           "Core two-way": {"valid_predictions": 0, "total": len(optimized),
                                            "accuracy": None, "reason": "No image-evidence adapter; compiler coverage reported separately"}}
        comparisons[cohort] = {"agreement": sum(a["label"] == b["label"] for a, b in zip(original, optimized)),
                               "total": len(original)}
    compiled = sum(value["status"] == "compiled" for value in compilations.values())
    image_supported = sum(value["image_boundary"]["status"] == "succeeded" for value in compilations.values())
    report = {"manifest": manifest, "compilations": compilations, "compilation_coverage": {"compiled": compiled, "total": 7},
              "image_boundary_coverage": {"supported": image_supported, "total": 7},
              "metrics": metrics, "original_optimized_agreement": comparisons,
              "draws": results, "pipeline_unchanged": frozen_hashes == source_hashes(),
              "established_faithful_decomposition": False,
              "limitation": "This tests the current core module without expanding its vocabulary or writing substitute grading rules. Any generated bounded policy still needs semantic coverage review and an image adapter. Direct prompt scores are not decomposition scores. Historical prompts were optimized on gpt-5.4-mini; these fresh draws use the configured current model. Transfer cases are other focal-only search task groups from an existing selected diagnostic, not a new representative dataset."}
    write_json(final_path, report)
    lines = ["# Actual optimized AURORA prompt diagnostic", "", f"Model: {experiment.engine.model}; 3 fresh temperature-0.3 draws per prompt/image group.",
             f"Core policies compiled: {compiled}/7; image-only core predictions: 0.", "",
             "| Cohort | Original correct | Optimized correct | Core two-way |", "|---|---:|---:|---|"]
    for cohort, arms in metrics.items():
        lines.append(f"| {cohort} | {arms['Original']['correct']}/{arms['Original']['total']} | {arms['Optimized']['correct']}/{arms['Optimized']['total']} | Not executable on images |")
    lines += ["", "## Compiler outcomes", ""]
    lines += [f"- {key}: {value['status']}; {value.get('reason', 'Schema-valid policy; semantic equivalence unverified')}" for key, value in sorted(compilations.items())]
    lines += ["", report["limitation"], "", "The faithful-decomposition hypothesis is not established. No core code, templates, cached prompts, or labels were tuned after scoring."]
    (destination / "optimized_aurora_summary.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines), flush=True)
    assert report["pipeline_unchanged"]
    assert len(results) == 93
    assert compiled == 7, "Current core cannot faithfully compile all optimized rubrics; diagnostic artifacts preserved"
    assert image_supported == 7, "Current core cannot evaluate image-only cases; diagnostic artifacts preserved"
