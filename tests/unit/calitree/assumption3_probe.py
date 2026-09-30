"""Bounded, fresh condition checks of frozen fitted AURORA decision sets.

Default is a no-call preflight. This measures named-case repeatability, not
generalization. Plans may have been selected using fitting labels; live checker
payloads never include those labels or earlier final predictions.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import time

from critical.lm_engine import LMEngine, get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter
from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import (
    FrozenCriteria, FrozenCriteriaExecutor, NeutralEvidence,
)
from .casewise_fitting import (
    CasewiseExperiment, CHECK_SCHEMA, validate_check, validate_plan,
    check_payload, aggregate, query_media,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / ".cache/calitree-tests/vision-visual-calibration-fresh32-20260926"
FITTED = ROOT / ".cache/calitree-tests/vision-casewise-fitting32-v2-20260926/fitted_cases.json"
NEUTRAL_SOURCE = ROOT / ".cache/calitree-tests/vision-neutral-property-strict-development32-20260926/results.json"
CASE_REVIEWS = ROOT / "docs/experiments/calitree_case_reviews.json"
NEUTRAL_NOTE = (
    "\nAdditional independently generated neutral observations are supplied for SOURCE and EDITED. "
    "Their observer saw only neutral property questions and one image, without the editing instruction, "
    "image role, rubric or human annotation. Treat these as fallible measurements, check their claims "
    "against the images, and explain any contradiction with your own state assessment. Do not infer "
    "the desired state from the condition wording. No prior grading label or human annotation is provided."
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class BudgetExhausted(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class BudgetedEngine:
    """Sequential request budget, reserving before calls and surviving restart."""

    def __init__(self, engine, path, max_calls, completion_budget):
        # A reserved operation must not trigger hidden retries or mirror calls.
        # Custom offline engines own their transport; package engines enforce
        # one HTTP attempt per reservation, including failures/timeouts.
        if isinstance(engine, LMEngine):
            engine.max_http_attempts = 1
        self.engine = engine
        self.path = Path(path)
        self.name = getattr(engine, "name", None)
        self.model, self.temperature, self.max_tokens = engine.model, engine.temperature, engine.max_tokens
        self.max_calls, self.completion_budget = max_calls, completion_budget
        self.records = json.loads(self.path.read_text()) if self.path.exists() else []

    @property
    def usage(self):
        return {
            "calls": len(self.records),
            "completion_tokens_or_reserved": sum(r["charged_completion"] for r in self.records),
            "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in self.records),
            "pending_or_failed": sum(r["state"] != "complete" for r in self.records),
        }

    def generate(self, prompt, **kwargs):
        if len(self.records) >= self.max_calls:
            raise BudgetExhausted("Request allowance exhausted")
        if self.usage["completion_tokens_or_reserved"] + self.max_tokens > self.completion_budget:
            raise BudgetExhausted("Remaining completion budget cannot reserve a full request")
        record = {"request_sha256": digest({"prompt": prompt, "kwargs": kwargs}),
                  "state": "reserved", "charged_completion": self.max_tokens}
        self.records.append(record)
        save(self.path, self.records)
        try:
            response = self.engine.generate(prompt, **kwargs)
        except BaseException as exc:
            record["state"] = "failed_or_interrupted"
            save(self.path, self.records)
            if isinstance(exc, Exception):
                raise ProviderUnavailable(str(exc)) from exc
            raise
        used = response.get("completionTokens")
        record.update(state="complete", charged_completion=used if isinstance(used, int) and used >= 0 else self.max_tokens,
                      prompt_tokens=response.get("promptTokens", 0),
                      finish_reason=response.get("finishReason"))
        save(self.path, self.records)
        return response


def apply_pilot_reviews(rows, *, reviews_path=CASE_REVIEWS, allow_uncertain_diagnostic=False):
    """Attach explicit image-bound reviews; uncertain targets cannot drive fitting."""
    from critical.core.optimization.prompt.calitree.annotation_quality import annotation_review
    registry = json.loads(Path(reviews_path).read_text())
    if registry.get('version') != 'calitree-pilot-case-reviews-v1':
        raise ValueError('Unsupported pilot case review registry')
    for case, row in rows.items():
        record = registry['cases'].get(case)
        if record is None:
            continue
        if [r['sha256'] for r in row['images']] != record['image_sha256'] or row['instruction'] != record['instruction']:
            raise ValueError('Pilot case review identity mismatch: ' + case)
        if row['human_label'] != record['target_label']:
            raise ValueError('Pilot target changed; re-adjudicate its review: ' + case)
        review = annotation_review(record)
        row['annotation_review'] = review
        if review['status'] == 'uncertain' and not allow_uncertain_diagnostic:
            raise ValueError(f'{case} is user-reviewed uncertain ({review.get("category", "review")}); exclude from fitting and primary agreement. Explicit unlabeled diagnostic access is separate.')
    return rows


def load_inputs(baseline_dir, fitted_path, cases, neutral_path=None, *, allow_uncertain_diagnostic=False):
    baseline = json.loads((baseline_dir / "results.json").read_text())
    fitted = json.loads(fitted_path.read_text())["cases"]
    neutral_records = json.loads(neutral_path.read_text())["results"] if neutral_path is not None else {}
    provenance = {r["path"]: r["sha256"] for r in
                  json.loads((baseline_dir / "public_provenance.json").read_text())["matches"]}
    if not cases or len(cases) != len(set(cases)):
        raise ValueError("Choose unique, nonempty case IDs")
    rows = {}
    for key in cases:
        row = deepcopy(fitted[key])
        case = baseline["manifest"]["cases"][key]
        if row["instruction"] != case["instruction"] or row["human_label"] != case["target_label"]:
            raise ValueError("Fitted and baseline case identities differ")
        validate_plan(row["plan"])
        images = query_media(baseline["results"][key]["arms"]["visual_references"])
        identities = []
        for media in images:
            path = media["path"]
            actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if actual != provenance[path]:
                raise ValueError("Changed image bytes: " + path)
            identities.append({"path": path, "sha256": actual})
        row["media"] = [{"type": "text", "text": "SOURCE image"}, images[0],
                        {"type": "text", "text": "EDITED image"}, images[1]]
        row["images"] = identities
        row["optimized_prompt"] = baseline["manifest"]["category_prompts"][case["task"]]["optimized"]
        row["criteria_origin"] = "fitted-case:" + digest({"case": key, "row": fitted[key]})
        if row["neutral_observations"] is not None and neutral_path is not None:
            recorded = neutral_records[key]
            old = row["neutral_observations"]
            if old["questions"] != recorded["questions"]["questions"] or {
                role: old[role] for role in ("source", "edited")
            } != recorded["observations"]:
                raise ValueError("Neutral evidence differs from its saved source")
            for index, role in enumerate(("source", "edited")):
                calls = recorded["observation_calls"][role]
                if not calls or any(call["media"] != [images[index]] for call in calls):
                    raise ValueError("Neutral evidence used different image inputs")
            row["bound_neutral"] = NeutralEvidence.bind(
                recorded["questions"]["typed_probes"], recorded["observations"],
                [item["sha256"] for item in identities],
                origin="neutral-record:" + digest(recorded),
            )
        rows[key] = row
    return apply_pilot_reviews(rows, allow_uncertain_diagnostic=allow_uncertain_diagnostic)


def run_case(experiment, row, arm):
    checks, keys = [], []
    for condition in row["plan"]["conditions"]:
        payload = check_payload(row["instruction"], condition)
        if arm == "neutral":
            payload["independent_neutral_observations"] = deepcopy(row["neutral_observations"])
        check, key = experiment.request("check", payload, CHECK_SCHEMA, validate_check, row["media"])
        checks.append({"condition_id": condition["id"], **check})
        keys.append(key)
    label = aggregate([{k: v for k, v in c.items() if k != "condition_id"} for c in checks])
    prior = {c["condition_id"]: c["status"] for c in row["checks"]}
    changed = [c["condition_id"] for c in checks if c["status"] != prior[c["condition_id"]]]
    return {"valid": True, "label": label, "checks": checks, "check_keys": keys,
            "statuses_changed_from_selected_fit": changed,
            "matches_human": label == row["human_label"]}


def run_bound_case(engine, destination, row, arm):
    criteria = FrozenCriteria.bind(row["optimized_prompt"], row["instruction"], row["plan"],
                                   feedback_used=row["feedback_used"], origin=row["criteria_origin"])
    executor = FrozenCriteriaExecutor(engine, checkpoint=CheckpointStore(destination / "bound-checks.jsonl"))
    try:
        neutral = row.get("bound_neutral") if arm in {"neutral", "fresh-neutral"} else None
        if arm == "fresh-neutral":
            if neutral is None:
                raise ValueError("Fresh neutral arm requires saved typed probes")
            probes = [{"id": f"q{i + 1}", **{k: p[k] for k in
                       ("property", "object_class", "reference_class")}}
                      for i, p in enumerate(neutral.to_dict()["probes"])]
            neutral = executor.observe_neutral(probes, evidence=dict(zip(
                ("source_image", "edited_image"), [r["path"] for r in row["images"]])))
        observations = executor.observe(
            criteria, prompt=row["optimized_prompt"], instruction=row["instruction"],
            evidence=dict(zip(("source_image", "edited_image"), [r["path"] for r in row["images"]])),
            neutral_evidence=neutral,
        )
    finally:
        with (destination / "bound-calls.jsonl").open("a") as output:
            for call in executor.calls:
                output.write(json.dumps(call) + "\n")
    checks = [{k: v for k, v in c.items() if k != "check_key"} for c in observations["checks"]]
    # The historical reducer is explicit experiment policy, not the core
    # observation component. Unknown remains visible in exported features.
    label = aggregate([{k: v for k, v in c.items() if k != "condition_id"} for c in checks])
    prior = {c["condition_id"]: c["status"] for c in row["checks"]}
    return {"valid": True, "label": label, "checks": checks, "observations": observations,
            "statuses_changed_from_selected_fit": [c["condition_id"] for c in checks if c["status"] != prior[c["condition_id"]]],
            "matches_human": label == row["human_label"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline-dir", type=Path, default=BASELINE)
    parser.add_argument("--fitted", type=Path, default=FITTED)
    parser.add_argument("--neutral-source", type=Path, default=NEUTRAL_SOURCE)
    parser.add_argument("--executor", choices=("legacy", "bound"), default="bound")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--arm", action="append", choices=("direct", "neutral", "fresh-neutral"))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-calls", type=int, default=14)
    parser.add_argument("--completion-budget", type=int, default=16000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    arms = args.arm or ["direct", "neutral"]
    if len(arms) != len(set(arms)) or min(args.repeats, args.max_calls, args.completion_budget, args.max_tokens) < 1:
        parser.error("Unique arms and positive limits required")
    rows = load_inputs(args.baseline_dir, args.fitted, args.case, args.neutral_source if args.executor == "bound" else None)
    if "fresh-neutral" in arms and args.executor != "bound":
        parser.error("Fresh neutral observations require the bound executor")
    if {"neutral", "fresh-neutral"}.intersection(arms) and any(not r["neutral_observations"] for r in rows.values()):
        parser.error("Neutral arm requires saved neutral measurements for every selected case")
    calls = sum(len(r["plan"]["conditions"]) for r in rows.values()) * args.repeats * len(arms)
    if "fresh-neutral" in arms:
        calls += 2 * len(rows) * args.repeats
    preflight = {"cases": args.case, "arms": arms, "executor": args.executor, "repeats": args.repeats,
                 "uncached_calls_without_repairs": calls, "max_calls": args.max_calls,
                 "completion_budget": args.completion_budget, "compiler_or_optimizer_calls": 0}
    print(json.dumps(preflight), flush=True)
    if not args.live:
        return
    require_live(explicit=True, context="Small-set frozen-plan assumption 3 probe")
    dest = args.output_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    templates = {k: (Path(__file__).parent / "templates/casefit_v1" / (k + ".txt")).read_text()
                 for k in ("decompose", "check")}
    manifest = {**preflight, "model": "gpt-4.1", "temperature": 0, "max_tokens": args.max_tokens,
                "fitted_source_sha256": hashlib.sha256(args.fitted.read_bytes()).hexdigest(),
                "rows": {k: {"instruction": r["instruction"], "plan": r["plan"],
                             "images": r["images"], "feedback_used_to_select_plan": r["feedback_used"],
                             "selected_fit_label": r["final_decomposed"], "human_label": r["human_label"],
                             "prior_checks": r["checks"], "neutral_observations": r["neutral_observations"]}
                         for k, r in rows.items()},
                "templates": templates, "neutral_note": NEUTRAL_NOTE,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "request_helper_sha256": hashlib.sha256((Path(__file__).parent / "casewise_fitting.py").read_bytes()).hexdigest()}
    source_dir = ROOT / "critical/core/optimization/prompt/calitree/decomposition"
    manifest["core_sha256"] = {name: hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
                               for name in ("decision_sets.py", "decomposition_twoway.py")}
    manifest["bound_neutral"] = {k: r["bound_neutral"].to_dict() for k, r in rows.items() if "bound_neutral" in r}
    template_dir = ROOT / "critical/core/prompts/templates/calitree_decomposition_casewise_v1"
    manifest["bound_templates"] = {p.name: p.read_text() for p in sorted(template_dir.glob("*.txt"))}
    path = dest / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Protocol changed; use a new output directory")
    save(path, manifest)
    (dest / "source_snapshot.py").write_bytes(Path(__file__).read_bytes())
    for name in manifest["core_sha256"]:
        (dest / ("core_" + name)).write_bytes((source_dir / name).read_bytes())
    pointer = dest / "log_directory.json"
    if pointer.exists():
        logdir = Path(json.loads(pointer.read_text())["path"])
    else:
        logdir = ROOT / "logs/exps" / (time.strftime("%y%m%d-%H:%M:%S") + "-assumption3-exps")
        logdir.mkdir(parents=True, exist_ok=False)
        save(pointer, {"path": str(logdir)})
    save(logdir / "config.json", manifest)
    engine = get_engine("gpt", model="gpt-4.1", creds=load_creds(engine="gpt"), temperature=0,
                        max_tokens=args.max_tokens, timeout=90,
                        history=LLMHistoryWriter(logdir / "llm-histories.log"))
    budget = BudgetedEngine(engine, dest / "budget.json", args.max_calls, args.completion_budget)
    result_path = dest / "results.json"
    results = json.loads(result_path.read_text())["draws"] if result_path.exists() else {}
    for repeat in range(args.repeats):
        for arm in arms:
            stage_dir = dest / f"repeat-{repeat}" / arm
            stage_dir.mkdir(parents=True, exist_ok=True)
            experiment = CasewiseExperiment(budget, stage_dir)
            if arm == "neutral":
                experiment.templates["check"] += NEUTRAL_NOTE
            for key, row in rows.items():
                draw_id = f"{repeat}/{arm}/{key}"
                if draw_id in results:
                    continue
                try:
                    result = (run_bound_case(budget, stage_dir, row, arm) if args.executor == "bound"
                              else run_case(experiment, row, arm))
                except (BudgetExhausted, ProviderUnavailable) as exc:
                    print(str(exc), flush=True)
                    save(result_path, {"manifest": manifest, "draws": results, "usage": budget.usage, "stop_reason": str(exc)})
                    return
                except Exception as exc:
                    result = {"valid": False, "label": "", "error": str(exc)}
                results[draw_id] = result
                report = {"manifest": manifest, "draws": results, "usage": budget.usage, "stop_reason": "running"}
                save(result_path, report)
                save(logdir / "results.json", report)
                print(json.dumps({"draw": draw_id, "label": result["label"], "valid": result["valid"],
                                  "status_changes": result.get("statuses_changed_from_selected_fit"),
                                  "usage": budget.usage}), flush=True)
    report = {"manifest": manifest, "draws": results, "usage": budget.usage, "stop_reason": "complete"}
    save(result_path, report)
    save(logdir / "results.json", report)


if __name__ == "__main__":
    main()
