"""Real AURORA development/validation experiments with no label feedback."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil

from critical import config
from critical.checkpoint import CheckpointStore
from critical.database.dl_aurora.assets import materialize_output_panel
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayVision, DecompositionTwoWayGrounded, DecompositionTwoWayIntent, DecompositionTwoWayInventory
from .test_optimized_aurora_prompts import FIXTURE, image_judgment, write_json


HOLDOUT = Path(__file__).parent / "fixtures/aurora_vision_holdout.json"
FRESH_HOLDOUT = Path(__file__).parent / "fixtures/aurora_vision_fresh64.json"
GROUNDED_HOLDOUT = Path(__file__).parent / "fixtures/aurora_vision_grounded_holdout64.json"
INTENT_HOLDOUT = Path(__file__).parent / "fixtures/aurora_vision_intent_holdout64.json"


def hashes():
    core = config.PROJECT_ROOT / "critical/core/optimization/prompt/calitree/decomposition"
    templates = config.PROJECT_ROOT / "critical/core/prompts/templates"
    paths = [*core.glob("*.py"), *templates.glob("calitree_decomposition_*/*.txt"), *[config.PROJECT_ROOT / path for path in ("critical/database/dl_aurora/assets.py", "critical/database/dl_aurora/loader.py", "run/setup_aurora_bench.py")], Path(__file__), Path(__file__).with_name("conftest.py"), Path(__file__).with_name("helpers.py"), FIXTURE, HOLDOUT, FRESH_HOLDOUT, GROUNDED_HOLDOUT, INTENT_HOLDOUT]
    return {str(p.relative_to(config.PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def datasets(cohort):
    if cohort == "development":
        data = json.loads(FIXTURE.read_text())
        rows = {key: {**data["cases"][key], "original": data["seed_prompt"],
                      "optimized": value["prompt"], "substantive_rewrite": True}
                for key, value in data["optimized_prompts"].items()}
    else:
        fixture = {"fresh_validation": FRESH_HOLDOUT, "grounded_validation": GROUNDED_HOLDOUT, "intent_validation": INTENT_HOLDOUT}.get(cohort, HOLDOUT)
        data = json.loads(fixture.read_text())
        rows = {key: {**case, "original": data["prompts"][case["original_prompt_sha256"]],
                      "optimized": data["prompts"][case["optimized_prompt_sha256"]]}
                for key, case in data["cases"].items()}
    return rows


def test_real_aurora_validation_fixture_is_frozen_and_disjoint():
    dev, validation = datasets("development"), datasets("validation")
    assert len(dev) == 7 and len(validation) == 50
    assert not {v["task_uid"] for v in dev.values()} & {v["task_uid"] for v in validation.values()}
    assert sum(c["substantive_rewrite"] for c in validation.values()) == 15
    data = json.loads(HOLDOUT.read_text())
    for digest, prompt in data["prompts"].items():
        assert hashlib.sha256(prompt.encode()).hexdigest() == digest
    fresh = datasets("fresh_validation")
    assert len(fresh) == 64
    assert not {v["task_uid"] for v in fresh.values()} & {v["task_uid"] for v in [*dev.values(), *validation.values()]}
    assert Counter(c["task"] for c in fresh.values()) == {task: 8 for task in ("ag", "clevr", "emu", "epic", "kubric", "magicbrush", "something", "whatsup")}
    grounded = datasets("grounded_validation")
    assert len(grounded) == 64
    assert not {v["task_uid"] for v in grounded.values()} & {v["task_uid"] for v in [*dev.values(), *validation.values(), *fresh.values()]}
    provenance = json.loads(GROUNDED_HOLDOUT.read_text())["provenance"]
    assert not {v["source_pixel_sha256"] for v in grounded.values()} & set(provenance["excluded_source_pixel_sha256"])
    intent = datasets("intent_validation")
    assert len(intent) == 64
    prior = [*json.loads(FIXTURE.read_text())["cases"].values(), *validation.values(), *fresh.values(), *grounded.values()]
    assert not {v["task_uid"] for v in intent.values()} & {v["task_uid"] for v in prior}
    assert Counter(c["task"] for c in intent.values()) == Counter(c["task"] for c in fresh.values())
    from PIL import Image

    def pixel_hash(case):
        with Image.open(config.PROJECT_ROOT / case["source_image"]) as image:
            rgb = image.convert("RGB")
            return hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()

    prior_pixels = {pixel_hash(case) for case in prior}
    assert all(pixel_hash(case) == case["source_pixel_sha256"] for case in intent.values())
    assert not {c["source_pixel_sha256"] for c in intent.values()} & prior_pixels
    assert len({c["source_pixel_sha256"] for c in intent.values()}) == 64
    for digest, prompt in json.loads(INTENT_HOLDOUT.read_text())["prompts"].items():
        assert hashlib.sha256(prompt.encode()).hexdigest() == digest


def normalized_output_cases(cases):
    normalized = {}
    # The frozen fixtures explicitly use this checkout's materialized archive,
    # independently of the user's configurable production dataset root.
    root = config.PROJECT_ROOT / "data/aurora/bench"
    for key, case in cases.items():
        source = config.PROJECT_ROOT / case["source_image"]
        edited = config.PROJECT_ROOT / case["edited_image"]
        row = materialize_output_panel(root, {
            "task": case["task"], "model": edited.stem,
            "source_path": str(source.relative_to(root)),
            "edited_path": str(edited.relative_to(root)),
        })
        normalized[key] = dict(case)
        if "image_normalization" in row:
            panel = root / row["edited_path"]
            normalized[key].update(
                edited_image=str(panel.relative_to(config.PROJECT_ROOT)),
                edited_image_sha256=row["image_normalization"]["output_sha256"],
                raw_edited_image=case["edited_image"],
                image_normalization=row["image_normalization"],
            )
    return normalized


def test_output_panel_routing_preserves_frozen_cases_and_labels():
    from PIL import Image
    raw = datasets("intent_validation")
    before = json.dumps(raw, sort_keys=True)
    normalized = normalized_output_cases(raw)
    assert json.dumps(raw, sort_keys=True) == before
    changed = {key for key in raw if raw[key] != normalized[key]}
    assert changed == {"I51", "I53", "I54", "I55", "I56"}
    for key in changed:
        case = normalized[key]
        assert case["target_label"] == raw[key]["target_label"]
        assert case["human_score"] == raw[key]["human_score"]
        with Image.open(config.PROJECT_ROOT / raw[key]["edited_image"]) as composite, Image.open(config.PROJECT_ROOT / case["edited_image"]) as panel:
            assert composite.convert("RGB").crop(tuple(case["image_normalization"]["crop_box"])).tobytes() == panel.convert("RGB").tobytes()


def run_experiment(experiment, cohort, *, review=False, grounded=False, intent=False, inventory=False, compare_grounded=False, baseline_dir=None, output_panels=False, development=False):
    if compare_grounded and (not (intent or inventory) or review or baseline_dir):
        raise ValueError("The four-arm fresh comparison requires intent, no review, and fresh baselines")
    destination = experiment.report_dir / cohort
    destination.mkdir(parents=True, exist_ok=True)
    cases = datasets(cohort)
    raw_cases = cases
    for case in cases.values():
        for kind in ("source", "edited"):
            p = config.PROJECT_ROOT / case[kind+"_image"]
            assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == case[kind+"_image_sha256"]
    if output_panels:
        cases = normalized_output_cases(cases)
        for case in cases.values():
            assert hashlib.sha256((config.PROJECT_ROOT / case["edited_image"]).read_bytes()).hexdigest() == case["edited_image_sha256"]
    frozen = hashes()
    manifest = {"cohort": cohort, "cases": cases, "source_hashes": frozen,
                "model": experiment.engine.model, "temperature": 0, "repeats": 1,
                "review": review, "grounded": grounded or intent or inventory, "intent": intent or inventory,
                "inventory": inventory,
                "compare_grounded": compare_grounded,
                "max_tokens": getattr(experiment.engine, "max_tokens", None),
                "output_panels": output_panels, "development": development,
                "baseline_dir": str(Path(baseline_dir).resolve()) if baseline_dir else None,
                "no_label_feedback": True, "new_prompt_optimization": False,
                "selection": "All predefined cases; no exclusions based on predictions",
                "limitation": ("64 new task groups; prompts routed from cached substantive rewrites by category, without test-label feedback. This also measures transfer beyond optimizer focal cases."
                               if cohort in {"fresh_validation", "grounded_validation", "intent_validation"} else
                               "Seven initial development cases or fifty previously selected tasks. Once their labels/results have informed revisions, they are development data. Each cached optimized prompt was historically optimized on its focal case.")}
    if baseline_dir:
        manifest["limitation"] = "Development ablation on already evaluated tasks. Direct baselines/intermediate checkpoints are reused; this run is not fresh validation. No current human labels enter the decomposition stages."
    elif development:
        manifest["limitation"] = "Development comparison on already evaluated tasks. All decisions are fresh but the cases are not unseen; no current human labels enter model calls."
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, "Cannot change a frozen run"
    else:
        write_json(manifest_path, manifest)
        for relative, digest in frozen.items():
            source = config.PROJECT_ROOT / relative
            assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
            snapshot = destination / "frozen_sources" / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, snapshot)
    previous = None
    checkpoint_path = destination / "decomposition_checkpoint.jsonl"
    if baseline_dir:
        # Reusing a formerly fresh cohort makes this a development ablation;
        # the manifest records that history explicitly.
        source = Path(baseline_dir) / cohort
        previous = json.loads((source / "results.json").read_text())
        assert previous["manifest"]["cases"] == raw_cases
        assert previous["manifest"]["model"] == experiment.engine.model
        assert previous["manifest"]["temperature"] == 0
        if not checkpoint_path.exists():
            shutil.copyfile(source / "decomposition_checkpoint.jsonl", checkpoint_path)
    checkpoint = CheckpointStore(checkpoint_path)
    strategy = DecompositionTwoWayInventory if inventory else DecompositionTwoWayIntent if intent else DecompositionTwoWayGrounded if grounded else DecompositionTwoWayVision
    algorithm = strategy(experiment.engine, checkpoint=checkpoint, review=review)
    comparator = DecompositionTwoWayGrounded(experiment.engine, checkpoint=checkpoint) if compare_grounded else None
    arm_names = ("Original", "Optimized", "Grounded", "Decomposed") if comparator else ("Original", "Optimized", "Decomposed")
    draws_path = destination / "draws.json"
    results = json.loads(draws_path.read_text()) if draws_path.exists() else {}

    def evaluate(key):
        case = cases[key]
        output = {"case_id": key, "expected": case["target_label"], "task": case["task"],
                  "substantive_rewrite": case["substantive_rewrite"], "arms": {}}
        for arm in ("Original", "Optimized"):
            output["arms"][arm] = ({**previous["results"][key]["arms"][arm], "reused_frozen_baseline": True}
                                   if previous and previous["manifest"]["cases"][key] == case else image_judgment(experiment.engine, case, case[arm.lower()]))
        evidence = {kind+"_image": str(config.PROJECT_ROOT / case[kind+"_image"]) for kind in ("source", "edited")}
        for arm, implementation in ([("Grounded", comparator)] if comparator else []) + [("Decomposed", algorithm)]:
            try:
                result = implementation.evaluate(implementation.compile(case["optimized"]), case["instruction"], evidence)
                output["arms"][arm] = {"label": result.label, "rationale": result.rationale,
                                       "valid": True, "trace": result.trace}
            except Exception as error:
                output["arms"][arm] = {"label": "", "valid": False, "error_type": type(error).__name__,
                                       "error": str(error) if isinstance(error, ValueError) else "Transport/model error; see call traces"}
        return key, output

    missing = [key for key in cases if key not in results]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(evaluate, key) for key in missing]
        for future in as_completed(futures):
            key, result = future.result()
            results[key] = result
            write_json(draws_path, results)
            write_json(destination / "decomposition_calls.json", algorithm.calls)
            if comparator:
                write_json(destination / "grounded_calls.json", comparator.calls)
            print(f"{cohort} {len(results)}/{len(cases)} {key}: expected={result['expected']} "
                  + " ".join(f"{arm}={row['label'] or row.get('error_type')}" for arm, row in result["arms"].items()), flush=True)
    groups = {"all": list(results.values()), "rewritten": [r for r in results.values() if r["substantive_rewrite"]]}
    metrics = {}
    for group, rows in groups.items():
        metrics[group] = {}
        label_counts = Counter(r["expected"] for r in rows)
        for arm in arm_names:
            correct = sum(r["arms"][arm]["label"] == r["expected"] for r in rows)
            invalid = sum(not r["arms"][arm]["valid"] for r in rows)
            confusion = Counter((r["expected"], r["arms"][arm]["label"]) for r in rows)
            recall = {label: sum(r["arms"][arm]["label"] == label for r in rows if r["expected"] == label)/count for label, count in label_counts.items()}
            metrics[group][arm] = {"correct": correct, "total": len(rows), "accuracy": correct/len(rows) if rows else None,
                                  "recall": recall, "balanced_accuracy": sum(recall.values())/len(recall) if recall else None,
                                  "invalid": invalid, "confusion": {f"{a}->{b}": n for (a,b),n in confusion.items()}}
    improved = [r["case_id"] for r in results.values() if r["arms"]["Decomposed"]["label"] == r["expected"] and r["arms"]["Optimized"]["label"] != r["expected"]]
    regressed = [r["case_id"] for r in results.values() if r["arms"]["Optimized"]["label"] == r["expected"] and r["arms"]["Decomposed"]["label"] != r["expected"]]
    report = {"manifest": manifest, "metrics": metrics, "improved_over_optimized": improved,
              "regressed_from_optimized": regressed, "pipeline_unchanged": frozen == hashes(), "results": results}
    if comparator:
        report["improved_over_grounded"] = [r["case_id"] for r in results.values() if r["arms"]["Decomposed"]["label"] == r["expected"] and r["arms"]["Grounded"]["label"] != r["expected"]]
        report["regressed_from_grounded"] = [r["case_id"] for r in results.values() if r["arms"]["Grounded"]["label"] == r["expected"] and r["arms"]["Decomposed"]["label"] != r["expected"]]
    write_json(destination / "results.json", report)
    sampling = "Direct baselines reused only for exact unchanged inputs; changed image inputs receive fresh decisions." if baseline_dir else "One fresh decision per arm/case."
    lines = [f"# Two-way vision: {cohort}", "", f"Model {experiment.engine.model}; temperature 0. {sampling}", "",
             "| Group | " + " | ".join(arm_names) + " |", "|---|" + "---:|" * len(arm_names)]
    for group, arms in metrics.items():
        lines.append("| " + group + " | " + " | ".join(f"{arms[a]['correct']}/{arms[a]['total']} ({arms[a]['invalid']} invalid)" for a in arm_names) + " |")
    lines += ["", f"Corrected: {improved}", f"Regressed: {regressed}", "", manifest["limitation"],
              "", "Ground-truth agreement is the success measure. Matching the optimized prompt alone is not enough."]
    (destination / "summary.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines), flush=True)
    assert report["pipeline_unchanged"]
    assert metrics["all"]["Decomposed"]["invalid"] == 0, "Capability errors preserved in report"
    # The goal is agreement with the human labels, not passing a weaker gate.
    assert metrics["all"]["Decomposed"]["correct"] == len(cases), "Remaining ground-truth mismatches are preserved for investigation"


def options(request):
    return {"review": request.config.getoption("--calitree-vision-review"),
            "grounded": request.config.getoption("--calitree-vision-grounded"),
            "intent": request.config.getoption("--calitree-vision-intent"),
            "inventory": request.config.getoption("--calitree-vision-inventory"),
            "output_panels": request.config.getoption("--calitree-aurora-output-panels"),
            "baseline_dir": request.config.getoption("--calitree-vision-baseline-dir")}


def test_vision_decomposition_aurora_development(hard_experiment, request):
    run_experiment(hard_experiment, "development", **options(request))


def test_vision_decomposition_aurora_validation(hard_experiment, request):
    run_experiment(hard_experiment, "validation", **options(request))


def test_vision_decomposition_aurora_fresh_validation(hard_experiment, request):
    run_experiment(hard_experiment, "fresh_validation", **options(request))


def test_vision_decomposition_aurora_grounded_validation(hard_experiment, request):
    run_experiment(hard_experiment, "grounded_validation", **options(request))


def test_vision_decomposition_aurora_intent_validation(hard_experiment):
    # Both algorithms and all four arms are predeclared before this cohort's
    # labels/results are inspected. Direct judgments and image checks are fresh.
    run_experiment(hard_experiment, "intent_validation", intent=True, compare_grounded=True)


def test_vision_decomposition_aurora_intent_development(hard_experiment, request):
    # Once inspected, this cohort is development data for new variants.
    run_experiment(hard_experiment, "intent_validation", development=True, **options(request))
