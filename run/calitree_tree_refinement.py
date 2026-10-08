"""Exploratory tree refinements on previously inspected frozen observations.

All choices use historical training groups only; later cases are a reused
evaluation cohort. This is not independent confirmation. No provider calls.
"""
import argparse
from collections import Counter
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
import platform
from zoneinfo import ZoneInfo

from critical.core.optimization.tree.regularized import (
    RegularizedSemanticTree, encode_fractions, fraction_feature_names,
)
from critical.core.optimization.tree.semantic import feature_names, schema_manifest
from run.calitree_shared_tree import (
    CANDIDATES, DEFAULT_SOURCE, ROBUSTNESS_PENALTY, ROOT, attach_features,
    bootstrap_delta, candidate_evaluation, choose, file_hash, fit_selected,
    grouped_folds, load_observations, metrics, save,
)

FAMILIES = ("balanced_presence", "balanced_fractions", "guarded_fractions")
LEAF_PENALTY = .005
PRIOR_PENALTY = .05


def feature_rows(draws, cases, family):
    if family == "balanced_presence":
        return attach_features(draws, cases, "roles")
    return [{**row, "features": encode_fractions(cases[row["case_id"]]["plan"]["conditions"], row["statuses"])}
            for row in draws if row["gate"] == "known"]


def make_model(family, depth, support):
    return RegularizedSemanticTree(feature_names() if family == "balanced_presence" else fraction_feature_names(),
                                  max_depth=depth, min_cases_leaf=support,
                                  guarded=family == "guarded_fractions",
                                  prior_penalty=PRIOR_PENALTY, leaf_penalty=LEAF_PENALTY)


def node_count(node):
    return 1 if node["leaf"] else 1 + node_count(node["left"]) + node_count(node["right"])


def rank(report):
    m = report["metrics"]
    return (m["balanced_accuracy"] - ROBUSTNESS_PENALTY * (m["conditional_pairwise_disagreement"] or 0),
            m["macro_f1"], -report.get("validation_mean_nodes", 0),
            -report.get("max_depth", 0), report.get("min_cases_leaf", 0))


def select_on_training(rows, family):
    folds = grouped_folds(rows)
    reports = []
    for depth, support in CANDIDATES:
        predictions, sizes = [None] * len(rows), []
        for train, validation in folds:
            program = make_model(family, depth, support).fit([rows[i] for i in train])
            sizes.append(node_count(program.tree))
            for i in validation:
                predictions[i] = program.predict(rows[i]["features"])
        reports.append({"family": family, "max_depth": depth, "min_cases_leaf": support,
                        "metrics": metrics(rows, predictions), "validation_mean_nodes": sum(sizes) / len(sizes),
                        "validation_predictions": [{"case_id": row["case_id"], "repeat": row["repeat"],
                                                    "prediction": prediction} for row, prediction in zip(rows, predictions)]})
    return max(reports, key=rank), reports


def run_refinement(source, output):
    cases, draws, inputs = load_observations(source)
    training = [r for r in draws if r["case_id"].startswith("J")]
    evaluation = [r for r in draws if r["case_id"].startswith("N")]
    if not training or not evaluation or {r["group"] for r in training} & {r["group"] for r in evaluation}:
        raise ValueError("Need disjoint historical and later source/instruction groups")
    output.mkdir(parents=True, exist_ok=False)
    (output / "run.log").write_text("Starting training-only exploratory selection.\n")
    (output / "llm-histories.log").write_text("No provider calls. Frozen model observations only.\n")
    manifest = {"version": "calitree-tree-refinement-v1", "new_model_calls": 0,
                "runtime": {"python": platform.python_version(), "numpy": version("numpy"),
                            "sklearn": version("scikit-learn")},
                "scope": "Exploratory comparison on reused evaluation cases; no independent confirmation",
                "source": str(source.resolve()), "input_sha256": inputs,
                "grid": CANDIDATES, "families": FAMILIES, "prior_penalty": PRIOR_PENALTY,
                "leaf_penalty": LEAF_PENALTY, "robustness_penalty": ROBUSTNESS_PENALTY,
                "min_correction_groups": 2, "role_schema": schema_manifest(),
                "fraction_schema": {"version": "calitree-role-fractions-v1", "names": fraction_feature_names(),
                                    "definition": "Per-role state counts / role check count; empty role gives zero plus NA flag"},
                "selection": "Source/instruction-grouped four-fold training-only validation; fixed rubric is eligible",
                "objective": "balanced accuracy minus 0.1 pairwise flip rate, then macro F1 and smaller program",
                "source_sha256": {str(path.relative_to(ROOT)): file_hash(path) for path in (
                    Path(__file__), ROOT / "critical/core/optimization/tree/regularized.py",
                    ROOT / "critical/core/optimization/tree/semantic.py", ROOT / "run/calitree_shared_tree.py")}}
    save(output / "manifest.json", manifest)
    fitted, selection = {}, {}
    known_train = attach_features(training, cases, "roles")
    known_eval = attach_features(evaluation, cases, "roles")
    fixed_cv = {"family": "fixed_reducer", "metrics": metrics(known_train, [r["fixed"] for r in known_train]),
                "validation_mean_nodes": 0}
    # Reference uses the original pilot's exact selection procedure.
    reports, folds = candidate_evaluation(known_train, "roles")
    legacy_choice = choose(reports)
    legacy = fit_selected(known_train, "roles", legacy_choice)
    fitted["original_roles_tree"] = {"program": legacy.to_dict(), "rule_text": legacy.rule_text(), "selected": legacy_choice}
    selection["original_roles_tree"] = {"selected": legacy_choice, "candidate_reports": reports}
    for family in FAMILIES:
        train_rows = feature_rows(training, cases, family)
        selected, reports = select_on_training(train_rows, family)
        model = make_model(family, selected["max_depth"], selected["min_cases_leaf"]).fit(train_rows)
        restored = RegularizedSemanticTree.from_dict(model.to_dict())
        selection[family] = {"selected": selected, "candidate_reports": reports}
        fitted[family] = {"program": restored.to_dict(), "rule_text": restored.rule_text(), "selected": selected}
    # Finish all choices before computing any reused evaluation metrics.
    selected_overall = max([fixed_cv] + [selection[f]["selected"] for f in FAMILIES], key=rank)["family"]
    predictions = {"fixed_reducer": [r["fixed"] for r in known_eval],
                   "original_roles_tree": [legacy.predict(r["features"]) for r in known_eval]}
    for family in FAMILIES:
        model = RegularizedSemanticTree.from_dict(fitted[family]["program"])
        records = feature_rows(evaluation, cases, family)
        decisions = [{"case_id": r["case_id"], "repeat": r["repeat"], **model.decision(r["features"])} for r in records]
        fitted[family]["decisions"] = decisions
        predictions[family] = [d["label"] for d in decisions]
    measured = {name: metrics(known_eval, values) for name, values in predictions.items()}
    for name, values in predictions.items():
        measured[name]["draw_coverage"] = len(known_eval) / len(evaluation)
        measured[name]["correct_planned_draw_fraction"] = sum(p == r["target"] for p, r in zip(values, known_eval)) / len(evaluation)
    result = {"selected_on_training": selected_overall, "primary": measured, "selection": selection,
              "fixed_training_reference": fixed_cv, "training_folds": folds, "models": fitted,
              "evaluation_outcomes": dict(Counter(r["gate"] for r in evaluation)),
              "training_labels": dict(Counter({r["case_id"]: r["target"] for r in known_train}.values())),
              "evaluation_labels": dict(Counter({r["case_id"]: r["target"] for r in known_eval}.values())),
              "bootstrap_vs_fixed": {name: bootstrap_delta(known_eval, values, predictions["fixed_reducer"])
                                     for name, values in predictions.items() if name != "fixed_reducer"}}
    save(output / "results.json", result)
    save(output / "feature_rows.json", {f: feature_rows(draws, cases, f) for f in FAMILIES})
    write_report(output, result)
    (output / "run.log").write_text(f"Complete; training-selected candidate: {selected_overall}; no provider calls.\n")
    return result


def write_report(output, result):
    pct = lambda value: f"{100*value:.1f}%"
    lines = ["# Exploratory CaliTree refinement", "",
             "Previously inspected evaluation cohort. Zero new model calls. All choices use training groups only.", "",
             f"Training-only selection chooses **{result['selected_on_training']}**, including the fixed rubric as an eligible candidate.", "",
             "## Training validation", "", "| Candidate | Balanced accuracy | Macro F1 | Flip rate |",
             "|---|---:|---:|---:|"]
    entries = [result["fixed_training_reference"]] + [result["selection"][f]["selected"] for f in FAMILIES]
    for entry in entries:
        m = entry["metrics"]
        lines.append(f"| {entry['family']} | {pct(m['balanced_accuracy'])} | {pct(m['macro_f1'])} | {pct(m['conditional_pairwise_disagreement'] or 0)} |")
    lines += ["", "## Reused evaluation cohort", "", "| Method | Agreement | Balanced accuracy | Macro F1 | Yes recall | Flip rate | Coverage |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for name, m in result["primary"].items():
        lines.append("| " + " | ".join([name, pct(m["case_macro_accuracy"]), pct(m["balanced_accuracy"]),
                     pct(m["macro_f1"]), pct(m["recall"]["yes"]), pct(m["conditional_pairwise_disagreement"] or 0), pct(m["draw_coverage"])]) + " |")
    lines += ["", f"Evaluation outcomes: `{result['evaluation_outcomes']}`. Metrics condition on fully known observations; unknown and failed draws remain unresolved.", "",
              "## What changed", "",
              "- Equal case contribution within each class for splitting and leaf loss. Leaf support still uses ordinary case mass and independent source/instruction groups.",
              "- Fraction features retain the proportion of complete/partial/absent/unknown checks within each role; presence and not-applicable indicators remain explicit.",
              "- Guarded leaves keep the fixed reducer unless a proposed correction has matching target evidence from at least two independent source/instruction groups. A rubric-change penalty and leaf-count penalty regularize the tree.",
              "- Bottom-up loss pruning removes branches that do not improve the penalized training objective. Validation also penalizes repeat disagreement.", "",
              "This remains greedy CART with loss pruning, not globally optimal structure search. The role mapper and local observations are unchanged; no shared predicate ontology is learned.", "",
              "## Programs", ""]
    for name, value in result["models"].items():
        lines += [f"### {name}", "", "```text", value["rule_text"].rstrip(), "```", ""]
    lines += ["## Conditional uncertainty", "",
              "Paired case-bootstrap intervals exclude training/selection uncertainty and adaptive reuse of this cohort.", ""]
    for name, value in result["bootstrap_vs_fixed"].items():
        lo, hi = value["percentile_95_interval"]
        lines.append(f"- {name}: {100*value['difference']:+.1f} percentage points agreement difference; 95% interval [{100*lo:+.1f}, {100*hi:+.1f}].")
    lines += ["", "## Remaining limits", "",
              "One independent yes training case still cannot establish positive-class generalization. Reweighting can amplify its noise. Guarding can preserve existing rubric behavior but cannot recover semantic evidence absent from the observations. Identical role/fraction vectors with conflicting labels require richer predicates, corrected observations, or annotation review. This cohort is reused and cannot confirm a performance improvement.", "",
              "Reproduce with `.venv/bin/python -m run.calitree_tree_refinement`. Inspect `results.json` for training folds, selection reports, portable programs and evaluation decision paths.", ""]
    (output / "report.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%y%m%d-%H:%M:%S")
    output = args.output_dir or ROOT / "logs/exps" / f"{stamp}-exps"
    result = run_refinement(args.source, output)
    print(output)
    print("Training-selected candidate:", result["selected_on_training"])
    for name, value in result["primary"].items():
        print(name, {key: round(value[key], 4) for key in (
            "case_macro_accuracy", "balanced_accuracy", "conditional_pairwise_disagreement")})


if __name__ == "__main__":
    main()
