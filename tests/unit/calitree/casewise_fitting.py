"""Opt-in, label-informed per-case exploration on recorded real AURORA cases.

This fits observable criteria to known cases. It does not estimate generalization.
Run: python -m tests.unit.calitree.casewise_fitting --live --baseline-dir ...
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from threading import Lock
import time

from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter


TEMPLATES = Path(__file__).parent / "templates/casefit_v1"
STATUS = ["complete", "partial", "absent", "unknown"]


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


CONDITION_FIELDS = ["id", "requirement", "source_selector", "complete_when", "partial_when", "absent_when", "unknown_when"]
PLAN_SCHEMA = object_schema({
    "conditions": {"type": "array", "minItems": 1, "maxItems": 8,
                   "items": object_schema({key: {"type": "string"} for key in CONDITION_FIELDS})},
    "rubric_conflicts": {"type": "array", "items": {"type": "string"}},
})
CHECK_SCHEMA = object_schema({"source_observation": {"type": "string"},
                              "edited_observation": {"type": "string"},
                              "status": {"type": "string", "enum": STATUS},
                              "rationale": {"type": "string"}})


def validate_plan(value):
    if not isinstance(value, dict) or set(value) != {"conditions", "rubric_conflicts"}:
        raise ValueError("Expected conditions and rubric_conflicts")
    conditions = value["conditions"]
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 8:
        raise ValueError("Expected 1-8 conditions")
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != set(CONDITION_FIELDS):
            raise ValueError("Incorrect condition fields")
        if any(not isinstance(s, str) or not s.strip() for s in condition.values()):
            raise ValueError("Every condition field must be a nonempty string")
    ids = [c["id"] for c in conditions]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate condition IDs")
    if not isinstance(value["rubric_conflicts"], list) or any(not isinstance(s, str) or not s.strip() for s in value["rubric_conflicts"]):
        raise ValueError("Invalid rubric_conflicts")
    return value


def validate_check(value):
    if not isinstance(value, dict) or set(value) != set(CHECK_SCHEMA["properties"]):
        raise ValueError("Incorrect check fields")
    if value["status"] not in STATUS or any(not isinstance(v, str) or not v.strip() for v in value.values()):
        raise ValueError("Invalid status or empty observation")
    return value


def aggregate(checks):
    """Explicit conjunction: failed/unknown condition => no; incomplete => partial."""
    if not checks:
        raise ValueError("Cannot aggregate zero conditions")
    statuses = [validate_check(c)["status"] for c in checks]
    if any(s in ("absent", "unknown") for s in statuses):
        return "no"
    return "partial" if "partial" in statuses else "yes"


def check_payload(instruction, condition):
    # Construct allowlisted evaluation input; never forward the fitting feedback.
    return {"instruction": instruction, "condition": deepcopy(condition)}


def query_media(arm):
    """Convert recorded image provenance entries into the LM media contract."""
    query = arm["input"]["query"]
    return [{"type": "image", "path": arm["media"][query[f"{role}_image_position"] - 1]["path"]}
            for role in ("source", "edited")]


class CasewiseExperiment:
    def __init__(self, engine, destination):
        self.engine = engine
        self.destination = Path(destination)
        self.lock = Lock()
        self.templates = {stage: (TEMPLATES / f"{stage}.txt").read_text() for stage in ("decompose", "check")}

    def request(self, stage, payload, schema, validate, media=()):
        identity = {"stage": stage, "payload": payload, "schema": schema,
                    "template": self.templates[stage], "model": self.engine.model,
                    "temperature": self.engine.temperature, "max_tokens": self.engine.max_tokens,
                    "media": [{**m, **({"sha256": hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest()} if "path" in m else {})} for m in media]}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.destination / "stages" / (key + ".json")
        if path.exists():
            record = json.loads(path.read_text())
            return deepcopy(validate(record["value"])), key
        calls = []
        error = None
        for attempt in range(2):
            prompt = self.templates[stage] + "\nINPUT_JSON: " + json.dumps(payload, ensure_ascii=False)
            if error:
                prompt += "\nSCHEMA_ERROR: " + error + "\nINVALID_RESPONSE: " + str(calls[-1]["response"].get("content"))
            response = self.engine.generate(prompt, media_inputs=list(media), schema=schema, strict_schema=True)
            entry = {"stage": stage, "key": key, "attempt": attempt, "input": payload,
                     "prompt": prompt, "schema": schema, "media": list(media), "response": response}
            calls.append(entry)
            with self.lock:
                with (self.destination / "calls.jsonl").open("a") as out:
                    out.write(json.dumps(entry) + "\n")
            try:
                value = validate(response.get("parsed"))
            except ValueError as exc:
                if attempt:
                    raise
                error = str(exc)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"identity": identity, "calls": calls, "value": value}, indent=2))
            return value, key
        raise AssertionError("No validated stage response")

    def fit(self, instruction, optimized_prompt, media, human_label, *, max_rounds=3, annotation_review=None):
        from critical.core.optimization.prompt.calitree.annotation_quality import annotation_review as parse_review
        if parse_review({"target_label": human_label, "annotation_review": annotation_review})["status"] == "uncertain":
            raise ValueError("Uncertain annotations must be reviewed before casewise fitting")
        rounds = []
        compile_input = {"instruction": instruction, "optimized_prompt": optimized_prompt}
        for index in range(max_rounds):
            record = {"round": index, "feedback_used": index > 0, "valid": False, "label": ""}
            try:
                plan, key = self.request("decompose", compile_input, PLAN_SCHEMA, validate_plan, media if index else ())
                record.update(plan=plan, plan_key=key, checks=[], check_keys=[])
                for condition in plan["conditions"]:
                    check, key = self.request("check", check_payload(instruction, condition), CHECK_SCHEMA, validate_check, media)
                    record["checks"].append({"condition_id": condition["id"], **check})
                    record["check_keys"].append(key)
                plain_checks = [{k: v for k, v in c.items() if k != "condition_id"} for c in record["checks"]]
                record.update(valid=True, label=aggregate(plain_checks))
            except Exception as exc:
                record["error"] = str(exc)
            rounds.append(record)
            if not record["valid"]:
                # A pipeline failure is not a wrong semantic prediction and cannot
                # justify applying human-label feedback to the decomposition.
                break
            if record["valid"] and record["label"] == human_label:
                break
            compile_input = {"instruction": instruction, "optimized_prompt": optimized_prompt,
                             "human_training_feedback": {"label": human_label}, "previous_attempt": record}
        return {"rounds": rounds, "first_label": rounds[0]["label"], "final_label": rounds[-1]["label"],
                "matched": rounds[-1]["valid"] and rounds[-1]["label"] == human_label}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", action="append", help="Case IDs; default all cases in the frozen record")
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    if args.max_rounds < 1:
        parser.error("--max-rounds must be positive")
    require_live(explicit=args.live, context="Label-informed per-case AURORA decomposition exploration")
    baseline_path = args.baseline_dir / "results.json"
    baseline = json.loads(baseline_path.read_text())
    cases = args.case or sorted(baseline["manifest"]["cases"])
    if len(cases) != len(set(cases)) or any(k not in baseline["results"] for k in cases):
        parser.error("Unknown or duplicate case ID")
    dest = args.output_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    provenance = {row["path"]: row["sha256"] for row in json.loads((args.baseline_dir / "public_provenance.json").read_text())["matches"]}
    manifest = {"purpose": "Per-case accuracy exploration with explicit human-label fitting feedback; no generalization criterion",
                "cases": cases, "max_rounds": args.max_rounds, "model": "gpt-4.1", "temperature": 0, "max_tokens": 4096,
                "schema_retries": 1, "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "templates": {p.name: p.read_text() for p in TEMPLATES.glob("*.txt")}}
    mp = dest / "manifest.json"
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise ValueError("Experiment identity changed; use another output directory")
    mp.write_text(json.dumps(manifest, indent=2))
    (dest / "source_snapshot.py").write_bytes(Path(__file__).read_bytes())
    pointer = dest / "log_directory.json"
    if pointer.exists():
        log_dir = Path(json.loads(pointer.read_text())["path"])
    else:
        log_dir = Path.cwd() / "logs/exps" / (time.strftime("%y%m%d-%H:%M:%S") + "-exps")
        log_dir.mkdir(parents=True, exist_ok=False)
        pointer.write_text(json.dumps({"path": str(log_dir)}))
    (log_dir / "config.json").write_text(json.dumps(manifest, indent=2))
    engine = get_engine("gpt", model="gpt-4.1", creds=load_creds(engine="gpt"), temperature=0,
                        max_tokens=4096, timeout=90, history=LLMHistoryWriter(log_dir / "llm-histories.log"))
    experiment = CasewiseExperiment(engine, dest)
    results_path = dest / "results.json"
    results = json.loads(results_path.read_text())["cases"] if results_path.exists() else {}

    def run(case_id):
        case = baseline["manifest"]["cases"][case_id]
        old = baseline["results"][case_id]["arms"]
        prompt = baseline["manifest"]["category_prompts"][case["task"]]
        pair = query_media(old["visual_references"])
        for m in pair:
            if hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest() != provenance[m["path"]]:
                raise ValueError("Public image provenance changed")
        marked = [{"type": "text", "text": "SOURCE image"}, pair[0], {"type": "text", "text": "EDITED image"}, pair[1]]
        fit = experiment.fit(case["instruction"], prompt["optimized"], marked, case["target_label"], max_rounds=args.max_rounds)
        return case_id, {"instruction": case["instruction"], "human_label": case["target_label"], "human_mean_score": case["human_score"],
                         "original": old["Original"]["label"], "optimized": old["Optimized"]["label"],
                         "previous_decomposed": old["visual_references"]["label"], **fit}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(run, k) for k in cases if k not in results]):
            key, result = future.result()
            results[key] = result
            report = {"manifest": manifest, "cases": results}
            results_path.write_text(json.dumps(report, indent=2))
            (log_dir / "results.json").write_text(json.dumps(report, indent=2))
            message = f"{key} human={result['human_label']} original={result['original']} optimized={result['optimized']} initial={result['first_label']} final={result['final_label']} rounds={len(result['rounds'])}"
            print(message, flush=True)
            with (log_dir / "run.log").open("a") as out:
                out.write(message + "\n")
    print(json.dumps({"finished": len(results), "matched": sum(r["matched"] for r in results.values())}), flush=True)


if __name__ == "__main__":
    main()
