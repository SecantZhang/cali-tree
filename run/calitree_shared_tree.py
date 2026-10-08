"""Retrospective shared-rule pilot on frozen five-repeat observations; no API calls.

The 31 historical J cases train the rule; 19 later N cases evaluate it. Both
cohorts have already been inspected. This is not untouched end-to-end confirmation
and the role ontology is an explicit fixed scaffold, not an induced ontology.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
from zoneinfo import ZoneInfo

import numpy as np
import sklearn
from sklearn.model_selection import GroupKFold

from critical.core.optimization.tree.semantic import (
    LABELS, SharedDecisionTree, case_weights, condition_role,
    encode_conditions, feature_names, fixed_prediction, schema_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "logs/exps/260930-10:51:35-exps"
REPEATS = 5
CANDIDATES = [(depth, support) for depth in (1, 2, 3) for support in (2, 4)]
ROBUSTNESS_PENALTY = 0.1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def load_observations(directory):
    """Verify original snapshots, every attempted slot, and successful call bindings."""
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("repeats") != REPEATS:
        raise ValueError("This pilot requires the frozen five-repeat protocol")
    files = {str(directory / "manifest.json"): file_hash(directory / "manifest.json")}
    for name, expected in manifest["source_files"].items():
        if file_hash(name) != expected:
            raise ValueError("Changed original artifact: " + name)
        files[name] = expected
    rows = manifest["rows"]
    old = Path(manifest["source"])
    frozen = json.loads((old / "frozen_plans.json").read_text())
    for case, row in rows.items():
        for field in ("instruction", "human_label", "task", "plan", "images", "feedback_used"):
            if row[field] != frozen[case][field]:
                raise ValueError("Changed frozen case: " + case)
        if row.get("annotation_review", {}).get("status") == "uncertain":
            raise ValueError("Uncertain annotation in fitting cohort")
        if case.startswith("N") and row["feedback_used"]:
            raise ValueError("Later-case criteria used their evaluation target")
    jobs = {}
    for source in (old, directory):
        for path in sorted((source / "jobs").glob("*.json")):
            value = json.loads(path.read_text())
            key = value["job_id"]
            if not key.startswith("check/"):
                continue
            if key in jobs:
                raise ValueError("Duplicate observation slot")
            jobs[key] = value
            files[str(path)] = file_hash(path)
    expected_keys = {f"check/{rep}/{case}/{c['id']}" for case, row in rows.items()
                     for c in row["plan"]["conditions"] for rep in range(REPEATS)}
    if set(jobs) != expected_keys:
        raise ValueError("Missing or unexpected attempted observation slots")
    draws = []
    for case, row in sorted(rows.items()):
        group = row["images"][0]["sha256"] + ":" + digest(row["instruction"])
        for rep in range(REPEATS):
            statuses, outcomes = {}, {}
            for condition in row["plan"]["conditions"]:
                record = jobs[f"check/{rep}/{case}/{condition['id']}"]
                outcomes[condition["id"]] = record["outcome"]
                if record["outcome"] != "completed":
                    continue
                if record["full_plan_sha256"] != digest(row["plan"]):
                    raise ValueError("Observation plan binding changed")
                check = record["check"]
                if check["condition_id"] != condition["id"] or check["status"] not in {
                    "complete", "partial", "absent", "unknown"
                }:
                    raise ValueError("Invalid observation")
                for call in record["calls"]:
                    if call["input"] != {"instruction": row["instruction"], "condition": condition}:
                        raise ValueError("Unexpected label-bearing or mismatched checker inputs")
                    if call["image_sha256"] != [image["sha256"] for image in row["images"]]:
                        raise ValueError("Observation image binding changed")
                statuses[condition["id"]] = check["status"]
            incomplete = len(statuses) != len(row["plan"]["conditions"])
            gate = "incomplete" if incomplete else "unknown" if "unknown" in statuses.values() else "known"
            draws.append({"case_id": case, "repeat": rep, "group": group,
                          "category": row["task"], "target": row["human_label"],
                          "statuses": statuses, "outcomes": outcomes, "gate": gate,
                          "fixed": fixed_prediction(list(statuses.values())) if not incomplete else "unresolved"})
    return rows, draws, files


def attach_features(draws, rows, kind):
    return [{**row, "features": encode_conditions(rows[row["case_id"]]["plan"]["conditions"],
                                                  row["statuses"], kind)}
            for row in draws if row["gate"] == "known"]


def metrics(rows, predictions):
    if len(rows) != len(predictions) or not rows:
        raise ValueError("Need matched nonempty predictions")
    weights = case_weights(rows)
    cm = {label: {prediction: 0.0 for prediction in LABELS} for label in LABELS}
    by_case = defaultdict(list)
    for row, prediction, weight in zip(rows, predictions, weights):
        if prediction not in LABELS:
            raise ValueError("Metrics require resolved predictions")
        cm[row["target"]][prediction] += weight
        by_case[row["case_id"]].append(prediction)
    recalls, f1s = {}, {}
    for label in LABELS:
        actual = sum(cm[label].values())
        predicted = sum(cm[target][label] for target in LABELS)
        tp = cm[label][label]
        recalls[label] = tp / actual if actual else 0.0
        f1s[label] = 2 * tp / (actual + predicted) if actual + predicted else 0.0
    flips = []
    for values in by_case.values():
        pairs = [(a, b) for i, a in enumerate(values) for b in values[i+1:]]
        if pairs:
            flips.append(sum(a != b for a, b in pairs) / len(pairs))
    total = sum(weights)
    return {"cases": len(by_case), "draws": len(rows),
            "case_macro_accuracy": sum(cm[label][label] for label in LABELS) / total,
            "balanced_accuracy": sum(recalls.values()) / len(LABELS),
            "macro_f1": sum(f1s.values()) / len(LABELS),
            "recall": recalls, "f1": f1s, "case_weighted_confusion": cm,
            "conditional_pairwise_disagreement": float(np.mean(flips)) if flips else None,
            "cases_with_multiple_known_draws": len(flips),
            "prediction_counts": dict(Counter(predictions))}


def grouped_folds(rows, *, category=False):
    groups = [r["category"] if category else r["group"] for r in rows]
    n = len(set(groups))
    if n < 2:
        raise ValueError("Need at least two independent groups")
    splitter = GroupKFold(n_splits=n if category else min(4, n))
    return [(list(train), list(test)) for train, test in splitter.split(rows, groups=groups)]


def candidate_evaluation(rows, kind):
    folds = grouped_folds(rows)
    reports = []
    for depth, support in CANDIDATES:
        predictions = [None] * len(rows)
        for train, test in folds:
            program = SharedDecisionTree(feature_names(kind), max_depth=depth,
                                         min_cases_leaf=support).fit([rows[i] for i in train])
            for i in test:
                predictions[i] = program.predict(rows[i]["features"])
        measured = metrics(rows, predictions)
        reports.append({"max_depth": depth, "min_cases_leaf": support, "metrics": measured})
    fold_cases = [{"train": sorted({rows[i]["case_id"] for i in train}),
                   "validation": sorted({rows[i]["case_id"] for i in test})} for train, test in folds]
    return reports, fold_cases


def choose(reports, robust=False):
    def rank(report):
        m = report["metrics"]
        penalty = ROBUSTNESS_PENALTY * (m["conditional_pairwise_disagreement"] or 0) if robust else 0
        return (m["balanced_accuracy"] - penalty, m["macro_f1"],
                -report["max_depth"], report["min_cases_leaf"])
    return max(reports, key=rank)


def fit_selected(rows, kind, choice):
    return SharedDecisionTree(feature_names(kind), max_depth=choice["max_depth"],
                              min_cases_leaf=choice["min_cases_leaf"]).fit(rows)


def majority(rows):
    counts = {label: sum(w for row, w in zip(rows, case_weights(rows)) if row["target"] == label)
              for label in LABELS}
    return max(LABELS, key=lambda label: (counts[label], -LABELS.index(label)))


def bootstrap_delta(rows, predictions, baseline, repeats=2000):
    grouped = defaultdict(list)
    for row, a, b in zip(rows, predictions, baseline):
        grouped[row["case_id"]].append(float(a == row["target"]) - float(b == row["target"]))
    values = np.array([np.mean(v) for v in grouped.values()])
    rng = np.random.default_rng(44)
    samples = rng.choice(values, size=(repeats, len(values)), replace=True).mean(axis=1)
    return {"metric": "paired case-macro accuracy difference", "cases": len(values),
            "difference": float(values.mean()),
            "percentile_95_interval": [float(x) for x in np.quantile(samples, [.025, .975])],
            "interpretation": "Conditional on saved features and selected tree; selection uncertainty is excluded"}


def collisions(rows):
    groups = defaultdict(Counter)
    for row, weight in zip(rows, case_weights(rows)):
        groups[tuple(row["features"])][row["target"]] += weight
    total = len({r["case_id"] for r in rows})
    return {"observed_lookup_accuracy_bound": sum(max(c.values()) for c in groups.values()) / total,
            "conflicting_vectors": [{"features": list(key), "class_mass": dict(counts)}
                                    for key, counts in groups.items() if len(counts) > 1],
            "interpretation": "Optimistic retrospective representation diagnostic, not achievable test accuracy"}


def run_experiment(source, output):
    rows, draws, inputs = load_observations(source)
    train_ids = sorted(case for case in rows if case.startswith("J"))
    test_ids = sorted(case for case in rows if case.startswith("N"))
    if not train_ids or not test_ids:
        raise ValueError("Expected historical J and later N cohorts")
    train_groups = {r["group"] for r in draws if r["case_id"] in train_ids}
    test_groups = {r["group"] for r in draws if r["case_id"] in test_ids}
    if train_groups & test_groups:
        raise ValueError("Source/instruction group leakage")
    output.mkdir(parents=True, exist_ok=False)
    (output / "run.log").write_text("Verified frozen inputs; starting offline grouped selection.\n")
    manifest = {"version": "calitree-shared-tree-pilot-v1", "new_model_calls": 0,
                "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                            "sklearn": sklearn.__version__},
                "scope": "Retrospective aggregation transfer; both cohorts previously inspected",
                "source": str(source.resolve()), "input_sha256": inputs,
                "train_ids": train_ids, "evaluation_ids": test_ids,
                "selection": "Four-fold source/instruction-grouped CV on J only",
                "candidate_grid": CANDIDATES, "robustness_penalty": ROBUSTNESS_PENALTY,
                "schemas": {kind: schema_manifest(kind) for kind in ("pooled", "roles")},
                "gate": "All arms use identical fully known draws; unknown and failed draws remain unresolved",
                "case_weighting": "Each case has total fit/scoring weight one across its known repeats",
                "class_order": LABELS, "test_criteria_label_feedback": False,
                "annotations": "Released labels remain provisional; J16 is excluded by the source cohort",
                "source_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in [
                    Path(__file__), ROOT / "critical/core/optimization/tree/semantic.py",
                    ROOT / "critical/core/optimization/tree/base.py"]}}
    save(output / "manifest.json", manifest)
    (output / "llm-histories.log").write_text("No model calls: this experiment only uses saved observation records.\n")
    known = attach_features(draws, rows, "pooled")
    train = [r for r in known if r["case_id"] in train_ids]
    test = [r for r in known if r["case_id"] in test_ids]
    predictions = {"fixed_reducer": [r["fixed"] for r in test],
                   "training_majority": [majority(train)] * len(test)}
    models, selections, schemas = {}, {}, {}
    for kind in ("pooled", "roles"):
        all_features = attach_features(draws, rows, kind)
        fitting = [r for r in all_features if r["case_id"] in train_ids]
        evaluation = [r for r in all_features if r["case_id"] in test_ids]
        reports, folds = candidate_evaluation(fitting, kind)
        selections[kind] = {"candidate_reports": reports, "folds": folds}
        schemas[kind] = {"feature_names": feature_names(kind), "collision_diagnostic": collisions(all_features)}
        for robust in ((False, True) if kind == "roles" else (False,)):
            name = kind + ("_robust_tree" if robust else "_tree")
            selected = choose(reports, robust)
            program = fit_selected(fitting, kind, selected)
            restored = SharedDecisionTree.from_dict(program.to_dict())
            predictions[name] = [restored.predict(r["features"]) for r in evaluation]
            models[name] = {"selected": selected, "program": restored.to_dict(),
                            "rule_text": restored.rule_text(),
                            "decisions": [{"case_id": r["case_id"], "repeat": r["repeat"],
                                           **restored.decision(r["features"])} for r in evaluation]}
    results = {name: metrics(test, pred) for name, pred in predictions.items()}
    # Exploratory outer category holdouts use only later, label-blind compiled cases.
    # Selection is repeated inside each outer training fold; repeats never cross it.
    later_roles = [r for r in attach_features(draws, rows, "roles") if r["case_id"] in test_ids]
    outer_predictions = {name: [None] * len(later_roles) for name in ("roles_tree", "training_majority")}
    outer = []
    for train_indices, test_indices in grouped_folds(later_roles, category=True):
        fitting = [later_roles[i] for i in train_indices]
        reports, folds = candidate_evaluation(fitting, "roles")
        selected = choose(reports)
        program = fit_selected(fitting, "roles", selected)
        for i in test_indices:
            outer_predictions["roles_tree"][i] = program.predict(later_roles[i]["features"])
            outer_predictions["training_majority"][i] = majority(fitting)
        outer.append({"held_out_categories": sorted({later_roles[i]["category"] for i in test_indices}),
                      "train_ids": sorted({r["case_id"] for r in fitting}),
                      "evaluation_ids": sorted({later_roles[i]["case_id"] for i in test_indices}),
                      "inner_folds": folds, "selected": selected, "program": program.to_dict()})
    summary = {"primary": results, "selection": selections, "models": models,
               "schemas": schemas, "source_outcomes": dict(Counter(d["gate"] for d in draws)),
               "evaluation_outcomes": dict(Counter(d["gate"] for d in draws if d["case_id"] in test_ids)),
               "bootstrap_vs_fixed": {name: bootstrap_delta(test, pred, predictions["fixed_reducer"])
                                      for name, pred in predictions.items() if name != "fixed_reducer"},
               "nested_later_category_cv": {"metrics": {name: metrics(later_roles, pred)
                                                         for name, pred in outer_predictions.items()},
                                            "folds": outer}}
    per_case = []
    for case, row in sorted(rows.items()):
        slots = [d for d in draws if d["case_id"] == case]
        methods = {}
        for name, pred in predictions.items():
            matching = {(r["case_id"], r["repeat"]): p for r, p in zip(test, pred)}
            methods[name] = [matching.get((case, d["repeat"]), "unresolved") for d in slots] if case in test_ids else None
        per_case.append({"case_id": case, "category": row["task"], "instruction": row["instruction"],
                         "target": row["human_label"], "historical_label_feedback": row["feedback_used"],
                         "partition": "train" if case in train_ids else "evaluation",
                         "conditions": [{"id": c["id"], "requirement": c["requirement"],
                                         "role": condition_role(c["requirement"]),
                                         "statuses": [d["statuses"].get(c["id"], "failed") for d in slots]}
                                        for c in row["plan"]["conditions"]],
                         "draw_gates": [d["gate"] for d in slots], "predictions": methods})
    summary["evaluation_label_counts"] = dict(Counter(rows[case]["human_label"] for case in test_ids))
    summary["training_label_counts"] = dict(Counter(rows[case]["human_label"] for case in train_ids))
    summary["effective_training_label_counts"] = dict(Counter(
        rows[case]["human_label"] for case in sorted({r["case_id"] for r in train})))
    summary["unevaluable_training_ids"] = sorted(set(train_ids) - {r["case_id"] for r in train})
    summary["unevaluable_evaluation_ids"] = sorted(set(test_ids) - {r["case_id"] for r in test})
    planned = len(test_ids) * REPEATS
    for name, pred in predictions.items():
        results[name]["resolved_draw_coverage"] = len(test) / planned
        results[name]["correct_planned_draw_fraction"] = sum(p == r["target"] for r, p in zip(test, pred)) / planned
    save(output / "results.json", summary)
    save(output / "cases.json", per_case)
    save(output / "feature_rows.json", {kind: attach_features(draws, rows, kind) for kind in ("pooled", "roles")})
    write_report(output, manifest, summary, per_case)
    (output / "run.log").write_text(json.dumps({"new_model_calls": 0, "primary": results}, indent=2) + "\n")
    return summary


def write_report(output, manifest, summary, cases):
    percent = lambda x: f"{100*x:.1f}%"
    train_count, test_count = len(manifest["train_ids"]), len(manifest["evaluation_ids"])
    lines = ["# Shared semantic decision-tree pilot", "",
             "Retrospective test of learned aggregation on saved real model observations. Zero new model calls.", "",
             "## Frozen design", "",
             f"Train on {train_count} historical J cases; select depth/support using grouped CV on training cases only. Evaluate on {test_count} later N cases. All five repeats stay with their source/instruction group. Both cohorts were previously inspected; this is not untouched confirmation.", "",
             "The semantic-role mapper is a fixed text-only scaffold (requested change, target binding, preservation), not a learned concept library. Local wording and decision boundaries remain historically case-specific. This pilot tests shared composition, not automatic abstraction or new predicate execution.", "",
             f"Training label counts: `{summary['training_label_counts']}`; effective known-draw fitting counts: `{summary['effective_training_label_counts']}`.", "",
             f"Evaluation label counts: `{summary['evaluation_label_counts']}`. Small class counts limit conclusions about class-specific generalization.", "",
             f"Cases with no known draws: training `{summary['unevaluable_training_ids']}`, evaluation `{summary['unevaluable_evaluation_ids']}`. Conditional accuracy therefore uses {summary['primary']['fixed_reducer']['cases']} of {test_count} evaluation cases.", "",
             "Unknown and failed draws remain unresolved for every arm, producing matched coverage. Accuracy and macro metrics give each evaluable case equal weight across its known repeats. Never count five draws as five independent cases.", "",
             "## Primary retrospective transfer", "",
             "| Method | Case-macro agreement | Balanced accuracy | Macro F1 | Partial recall | Yes recall | Conditional flip rate | Draw coverage |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, m in summary["primary"].items():
        lines.append("| " + " | ".join([name, percent(m["case_macro_accuracy"]), percent(m["balanced_accuracy"]),
                                         percent(m["macro_f1"]), percent(m["recall"]["partial"]), percent(m["recall"]["yes"]),
                                         percent(m["conditional_pairwise_disagreement"] or 0), percent(m["resolved_draw_coverage"])]) + " |")
    lines += ["", f"Evaluation draw outcomes: `{summary['evaluation_outcomes']}`.", "",
              "Flip rate uses pairs of known draws within each case; cases with fewer than two known draws are excluded from that metric. Coverage is reported independently. Constant predictions can be stable but wrong.", "",
              "## Paired uncertainty versus fixed reducer", "",
              "Case-bootstrap intervals are descriptive and conditional on recorded observations and the fitted tree; they exclude training/selection uncertainty.", ""]
    for name, result in summary["bootstrap_vs_fixed"].items():
        lo, hi = result["percentile_95_interval"]
        lines.append(f"- {name}: {100*result['difference']:+.1f} percentage points; 95% interval [{100*lo:+.1f}, {100*hi:+.1f}].")
    lines += ["", "## Learned programs", ""]
    for name, result in summary["models"].items():
        s = result["selected"]
        lines += [f"### {name}", "", f"Selected depth {s['max_depth']}, minimum leaf support {s['min_cases_leaf']} case mass.",
                  "", "```text", result["rule_text"].rstrip(), "```", ""]
    lines += ["## Exploratory later-case category holdouts", "",
              "Nested selection holds out one source category at a time using only later N cases. This is an additional retrospective stress test, not independent confirmation.", ""]
    for name, m in summary["nested_later_category_cv"]["metrics"].items():
        lines.append(f"- {name}: case-macro agreement {percent(m['case_macro_accuracy'])}; balanced accuracy {percent(m['balanced_accuracy'])}; yes recall {percent(m['recall']['yes'])}.")
    lines += ["", "## Representation diagnostics", ""]
    for kind, value in summary["schemas"].items():
        c = value["collision_diagnostic"]
        lines.append(f"- {kind}: {len(c['conflicting_vectors'])} feature vectors contain conflicting labels; optimistic observed lookup bound {percent(c['observed_lookup_accuracy_bound'])}.")
    lines += ["", "These bounds use all observed labels only after evaluation, and never select the tree or features. They diagnose insufficiency in the recorded representation, not a ceiling on richer semantic decisions.", "",
              "## Later-case predictions", "", "| Case | Provisional label | Known draws / 5 | Fixed reducer | Role tree | Robust role tree |",
              "|---|---|---:|---|---|---|"]
    for c in cases:
        if c["partition"] == "evaluation":
            p = c["predictions"]
            lines.append(f"| {c['case_id']} | {c['target']} | {c['draw_gates'].count('known')} | {', '.join(p['fixed_reducer'])} | {', '.join(p['roles_tree'])} | {', '.join(p['roles_robust_tree'])} |")
    lines += ["", "## Limits and next test", "",
              "This experiment cannot establish semantic truth of the atomic observations, faithful abstraction of local predicates, repeatability of a newly generated decomposition, or untouched end-to-end generalization. The role assignments need an independent audit; they may combine different meanings or omit a requested change. The existing records and provisional labels are retained.", "",
              "Next: audit role/concept assignments without outcome-driven edits, then freeze parameterized predicates and evaluate fresh, untouched source/instruction groups with a stronger class balance. Compare shared-predicate execution with the existing local criteria, keeping inference compute matched.", "",
              "Artifacts: `manifest.json`, `results.json`, `cases.json`, `feature_rows.json`, `run.log`, `llm-histories.log`.", "",
              "Reproduce (writes a new directory; never calls a provider):", "", "```sh",
              f".venv/bin/python -m run.calitree_shared_tree --source {manifest['source']} --output-dir /private/tmp/calitree-shared-tree-replay",
              "```", ""]
    (output / "report.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%y%m%d-%H:%M:%S")
    output = args.output_dir or ROOT / "logs/exps" / f"{stamp}-exps"
    result = run_experiment(args.source, output)
    measured = ("case_macro_accuracy", "balanced_accuracy", "conditional_pairwise_disagreement",
                "resolved_draw_coverage")
    print(json.dumps({"output": str(output), "new_model_calls": 0,
                      "primary": {name: {key: metrics[key] for key in measured}
                                  for name, metrics in result["primary"].items()}}, indent=2))


if __name__ == "__main__":
    main()
