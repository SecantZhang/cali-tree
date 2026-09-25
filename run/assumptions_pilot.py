"""Reproducible ten-case, retrospective assumption audit; no model API calls.

Uses ten independent recorded repetitions per arm, never acceptance-selected
confirmation runs. Fits trees locally with task-grouped out-of-fold evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import zipfile

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "logs/exps/aurora-prompt-repair-focal-only"
TREE_SOURCE = ROOT / "logs/exps/aurora-prompt-tree-full-v4/prompt_tree_results.jsonl"
LABELS = ["no", "partial", "yes"]
ENCODE = {label: index for index, label in enumerate(LABELS)}
# Selection frozen before computing the pilot outcomes: 3 no / 4 partial / 3 yes,
# all eight AURORA source categories, five editors, ten distinct task groups.
SELECTED = [
    ("1592db8eeb058575e243", "Grab/move; yes"),
    ("2138bd4e57807fa97c98", "Multi-attribute addition; yes"),
    ("d69e2f7ee93fd333b4a8", "Object transformation; yes"),
    ("21a7dfd984ad3a3db1da", "Subjective style; no"),
    ("7b5a1243dcf10cae8e01", "Spatial relation; no"),
    ("81f92ae2a66d7d4f4a31", "Human action; no"),
    ("1f7d2138a8bbd43782af", "Color change; partial"),
    ("266944e1405d6f8cdeb3", "Relative movement; partial"),
    ("76505993b22ebaa0dbf8", "Object removal; partial"),
    ("cf97845c496dba21bc2d", "Object plus size/location; partial"),
]
FEATURES = {
    "coarse": ["requirement_mean", "requirement_min", "preservation"],
    "detailed": ["presence_min", "presence_mean", "fidelity_min", "fidelity_mean",
                 "core_min", "modifier_min", "modifier_applicable", "preservation",
                 "requirement_yes_fraction", "requirement_no_fraction"],
}
AUDIT_PATH = ROOT / "docs/experiments/assumptions_10_case_visual_audit.json"


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def mode(values):
    counts = Counter(values)
    winners = [v for v, n in counts.items() if n == max(counts.values())]
    return winners[0] if len(winners) == 1 else "tie"


def distribution(values):
    counts = Counter(values)
    n = len(values)
    return {
        "n": n, "counts": dict(counts), "mode": mode(values),
        "stable": len(counts) == 1,
        "pairwise_disagreement": 1 - sum(c * (c - 1) for c in counts.values()) / (n * (n - 1))
        if n > 1 else None,
    }


def features(tree_case, repeat):
    reqs = tree_case["decomposition"]["requirements"]
    leaves = repeat["requirements"]
    assert len(reqs) == len(leaves)
    value = [ENCODE[r["label"]] for r in leaves]
    presence = [ENCODE[r["presence"]["label"]] for r in leaves]
    fidelity = [ENCODE[r["fidelity"]["label"]] for r in leaves]
    core = [v for q, v in zip(reqs, value) if q["role"] == "core"]
    modifier = [v for q, v in zip(reqs, value) if q["role"] == "modifier"]
    return {
        "requirement_mean": float(np.mean(value)), "requirement_min": min(value),
        "presence_min": min(presence), "presence_mean": float(np.mean(presence)),
        "fidelity_min": min(fidelity), "fidelity_mean": float(np.mean(fidelity)),
        "core_min": min(core), "modifier_min": min(modifier) if modifier else 2,
        "modifier_applicable": int(bool(modifier)),
        "preservation": ENCODE[repeat["preservation"]["label"]],
        "requirement_yes_fraction": value.count(2) / len(value),
        "requirement_no_fraction": value.count(0) / len(value),
    }


def classifier():
    # Frozen settings; no choice among hyperparameters based on these outcomes.
    # With ten records per task, min_samples_leaf=20 implies >=2 training tasks.
    return DecisionTreeClassifier(max_depth=2, min_samples_leaf=20, random_state=44)


def evaluate_predictions(y, pred, case_indices):
    cases = []
    for i in sorted(set(case_indices)):
        mask = case_indices == i
        values = [LABELS[int(v)] for v in pred[mask]]
        d = distribution(values)
        d.update(case_index=int(i), correct=int(np.sum(y[mask] == pred[mask])),
                 target=LABELS[int(y[mask][0])])
        cases.append(d)
    return {
        "repeat_accuracy": float(accuracy_score(y, pred)),
        "balanced_repeat_accuracy": float(balanced_accuracy_score(y, pred)),
        "modal_correct_cases": sum(c["mode"] == c["target"] for c in cases),
        "modal_ties": sum(c["mode"] == "tie" for c in cases),
        "stable_cases": sum(c["stable"] for c in cases),
        "mean_pairwise_disagreement": float(np.mean([c["pairwise_disagreement"] for c in cases])),
        "confusion": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(), "cases": cases,
    }


def fit_trees(cases, feature_rows, out):
    y = np.array([ENCODE[c["target_label"]] for c in cases for _ in range(10)])
    indices = np.repeat(np.arange(len(cases)), 10)
    categories = np.array([c["task"] for c in cases for _ in range(10)])
    results = {}
    for representation, names in FEATURES.items():
        x = np.array([[f[name] for name in names] for f in feature_rows])
        variants = {}
        for grouping, groups in [("leave_task_out", indices), ("leave_category_out", categories)]:
            predictions = np.full(len(y), -1)
            folds = []
            for group in sorted(set(groups)):
                test = groups == group
                train = ~test
                assert not set(indices[train]) & set(indices[test])
                model = classifier().fit(x[train], y[train])
                predictions[test] = model.predict(x[test])
                folds.append({"held_out_group": str(group),
                              "train_case_indices": sorted(map(int, set(indices[train]))),
                              "test_case_indices": sorted(map(int, set(indices[test]))),
                              "tree": export_text(model, feature_names=names)})
            assert np.all(predictions >= 0)
            variants[grouping] = {**evaluate_predictions(y, predictions, indices), "folds": folds}
        full = classifier().fit(x, y)
        variants["resubstitution"] = evaluate_predictions(y, full.predict(x), indices)
        variants["fitted_tree"] = export_text(full, feature_names=names)
        buckets = defaultdict(list)
        for k, row in enumerate(x):
            buckets[tuple(float(v) for v in row)].append(k)
        conflicts = []
        upper_correct = 0
        for values, rows in buckets.items():
            counts = Counter(int(y[k]) for k in rows)
            upper_correct += max(counts.values())
            if len(counts) > 1:
                conflicts.append({"features": dict(zip(names, values)),
                                  "label_counts": {LABELS[k]: v for k, v in counts.items()},
                                  "case_indices": sorted({int(indices[k]) for k in rows})})
        variants["feature_collisions"] = conflicts
        variants["observed_deterministic_mapping_accuracy_ceiling"] = upper_correct / len(y)
        variants["feature_names"] = names
        results[representation] = variants
    # A matched out-of-fold constant predictor is essential on a tiny sample.
    pred = np.empty(len(y), dtype=int)
    for i in range(len(cases)):
        mask = indices == i
        pred[mask] = Counter(map(int, y[~mask])).most_common(1)[0][0]
    results["leave_task_out_majority_baseline"] = evaluate_predictions(y, pred, indices)
    save(out / "learned_trees.json", results)
    return results


def write_reports(out, manifest, summary, details, learned, bundles):
    audit = json.loads(AUDIT_PATH.read_text())
    notes = {c["case_id"]: c for c in audit["cases"]}
    save(out / "visual_audit.json", audit)
    arm_names = {
        "fresh_natural": "Selected natural prompt, fresh recorded repeats",
        "semantic_json": "Extracted semantic policy in JSON",
        "controlled_prose": "Same extracted policy in controlled prose",
        "mechanical_json": "Original text losslessly wrapped in JSON",
        "fixed_condition_tree": "Independent condition leaves + fixed rules",
    }
    lines = [
        "# Ten-case audit of the condition-tree assumptions", "",
        "## What was actually tested", "",
        "This is a retrospective diagnostic using existing real model evaluations, plus new local tree fits and an assistant visual/text audit. No new model API calls were made. The recovered public AURORA image archive was checked against the project's pinned SHA-256 before extracting these 20 images.", "",
        "The 10 distinct source-instruction task groups cover all eight AURORA source categories, all five editors, and labels no/partial/yes in a 3/4/3 allocation. They were selected by metadata coverage from 33 unique cases with available prompt-ablation and condition traces. This is a diverse diagnostic subset of previously selected repair cases, not a representative probability sample of all AURORA edits.", "",
        "Each recorded arm has 10 repetitions per case at temperature 0.3, requested/returned model gpt-5.4-mini on the historical provider. We use fresh-natural ablation repetitions rather than the successful repetitions used to select the prompt. We exclude acceptance-triggered confirmation runs. Three selected prompts (C02, C05, C06) are unchanged seed rubrics; seven are modified prompts. Provider migration means these observations do not establish behavior on the current official API.", "",
        "The semantic-policy arm is an extraction of each selected prompt and is still executed in one LLM call. The independent-leaf arm uses a separate, instruction-derived generic decomposition with hardcoded aggregation. It is NOT a faithful compilation of the selected optimized prompt. These are two separate assumption probes, not a completed implementation of the proposed learned compiler/library.", "",
        "The effective sample size is 10 tasks, not 100 independent examples. AURORA supplies aggregate human scores; classes use the project's frozen thresholds <0.5=no, <1.5=partial, otherwise yes. Individual rater votes and human concept labels are unavailable.", "",
        "## Findings against the six assumptions", "",
        "| Assumption | Pilot assessment | Evidence |", "|---|---|---|",
        "| 1. Well-defined scoring target | Policy ambiguity found; annotation validity not established | C01 and C03 receive human yes despite preservation concerns. Some rubrics allow incidental changes; the generic tree always downgrades partial preservation. C01 has an ambiguous restriction on using instruction text. A single semantic-consistency name does not fix these policy differences. |",
        "| 2. Complete, meaning-preserving decomposition | Violated by concrete current examples | C10 loses the optimized rubric's count/duplication criterion in the independent checks. C02 embeds the same modifiers in its core condition and separate modifier leaves. C04 only restates the subjective task. Structured extraction also adds a scene-replacement exception absent from the seed rubric. |",
        f"| 3. Meaningful and dependable condition evaluation | Repeatability fails for many leaves; absolute concept accuracy remains unmeasured | {summary['unstable_atomic_leaves']}/{summary['total_atomic_leaves']} leaf evaluators change labels across ten repeats, across {summary['cases_with_unstable_leaves']}/10 cases. C05 sometimes describes a pillow beside the chair as underneath it. No independent human concept annotations are available. |",
        "| 4. Sufficient features and a learnable small tree | Current feature compression is insufficient for exact reproduction of these observed targets; good predictive composition is not demonstrated | Coarse and detailed measured feature vectors collide across different human labels. A depth-2 tree gets 66% leave-task-out accuracy, with zero yes recall. This does not disprove a richer representation or a better-supported tree. |",
        "| 5. Transferable condition-to-score mapping | Unverified; transfer stress test is unfavorable | Accuracy is 58% when holding out each source category. Eight source categories are not equivalent to eight independent operation families or external domains. Ten cases cannot establish invariance. |",
        "| 6. Adequate, representative supervision | Not met by this pilot | Only 10 task groups, including just 3 yes cases; selected prompts were tuned on their focal labels. No independent concept labels, rater agreement, or external test set. Metadata stratification aids diagnosis but does not remove selection bias. |", "",
        "## Accuracy and stability", "",
        "Correct repeats use the binned human target. A modal tie is reported separately and never counted as correct. Stable means all ten final labels agree, regardless of correctness.", "",
        "| Arm | Correct repeats / 100 | Correct case modes / 10 | Stable cases / 10 | Mean within-case pair disagreement |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, name in arm_names.items():
        m = summary["arm_metrics"][arm]
        lines.append(f"| {name} | {m['repeat_accuracy']*100:.0f} | {m['modal_correct_cases']} | {m['stable_cases']} | {m['mean_pairwise_disagreement']:.1%} |")
    lines += ["", "The extracted JSON policy changes the untied modal prediction on 5/10 cases versus the natural prompt (mean total-variation distance 0.43). Its repeat accuracy is 67%, versus 61% for the natural prompt: disagreement does not automatically mean worse human alignment. However, the paired task-bootstrap 95% interval for that accuracy difference is -20 to +32 percentage points, so this pilot does not establish an improvement.", "",
              "Even the lossless JSON wrapper changes the modal label on 7/9 non-tied comparisons (one additional comparison ties). Therefore a behavioral change alone cannot distinguish semantic information loss from prompt-format sensitivity. The specific omissions and added exceptions above are separate textual evidence.", "",
              "## Learning a shared tree", "",
              "Two feature schemas were frozen before computing outcomes. Coarse: mean requirement score, minimum requirement score, preservation. Detailed: presence/fidelity minima and means, core/modifier minima, modifier applicability, preservation, fraction of requirements yes/no. Scores encode no=0, partial=1, yes=2. Task name, instruction text, editor identity, optimizer, original prompt verdict, and human score are excluded from features.", "",
              "All fits use max_depth=2, min_samples_leaf=20, random_state=44. Ten repeat records per case imply every leaf has at least two distinct training cases. Leave-task-out places all ten repetitions of the held-out task exclusively in the test fold. Leave-category-out holds out all selected cases in a source category. No hyperparameters were selected from these results.", "",
              "| Features | Fit on the same data | Leave one task out | Leave one source category out | Observed feature-mapping ceiling |", "|---|---:|---:|---:|---:|"]
    for schema in FEATURES:
        r = learned[schema]
        lines.append(f"| {schema} | {r['resubstitution']['repeat_accuracy']:.0%} | {r['leave_task_out']['repeat_accuracy']:.0%} | {r['leave_category_out']['repeat_accuracy']:.0%} | {r['observed_deterministic_mapping_accuracy_ceiling']:.0%} |")
    lines += ["", "The ceiling is calculated only on the 100 observed repeat records: for each identical feature vector, sum the largest human-label count. It is not a bound on all future systems or on a representation using correct, richer concepts. Collisions can reflect feature compression, measurement errors, annotation ambiguity, or omitted scoring context.", "",
              "A concrete detailed-feature collision: C01 (human yes), C07, C08, and C09 (human partial) all produce fully satisfied target checks plus partial preservation, with no separate modifiers. Nine yes-labeled records and 29 partial-labeled records have the exact same detailed vector. No deterministic rule using only that vector can distinguish them.", "",
              "Both learned schemas have zero leave-task-out recall for yes (0/30 repeats across three yes cases), despite 66% overall accuracy. The generic fixed tree also has 66% overall accuracy but a different class-error pattern. Similar aggregate accuracy is not evidence of equivalent behavior or adequate calibration.", "",
              "The detailed tree fitted on all ten cases is shown only to inspect what it learned, not as an independently validated judge:", "", "```text", learned["detailed"]["fitted_tree"].rstrip(), "```", "",
              "Class 0=no, 1=partial, 2=yes. The use of modifier applicability as a split illustrates how a tiny dataset can support a brittle proxy instead of a stable scoring rule.", "",
              "## Per-case record", "", "The image and textual audit is by Codex, after seeing labels and outputs. It is not blinded, is not human gold, and was not used as training features. Click the HTML review for source/output pairs and full prompts.", "",
              "| Case | Source category | Instruction | Human score / label | Natural hits | Structured hits | Fixed-tree hits | Unstable leaves |", "|---|---|---|---|---:|---:|---:|---:|"]
    for c, d in zip(manifest["cases"], details):
        lines.append(f"| {c['case_id']} | {c['task']} | {c['instruction']} | {c['human_score']:.3f} / {c['target_label']} | {d['arms']['fresh_natural']['correct']}/10 | {d['arms']['semantic_json']['correct']}/10 | {d['arms']['fixed_condition_tree']['correct']}/10 | {d['unstable_leaf_count']}/{len(d['leaf_stats'])} |")
    lines += ["", "## Required changes before a larger learned-tree experiment", "",
              "1. Define preservation scope, severity, and relevance to the scoring target; avoid one universal partial-preservation downgrade.",
              "2. Require explicit coverage of target identity, count/duplication, attributes, relations, and exceptions where the rubric makes them relevant. Reject overlapping core/modifier checks.",
              "3. Separate uncertain evidence from actual partial fulfillment; the historical leaves conflate them.",
              "4. Obtain independent human condition annotations on a small diagnostic set. Human-verified feature sufficiency remains untested here; an assistant review cannot substitute for it.",
              "5. Freeze the compiler, concept library, score definition, and model configuration before evaluating new task groups. Use more independently labeled cases, especially yes cases, before learning transferable thresholds.", "",
              "## Reproduction and artifacts", "",
              "```bash", f".venv/bin/python run/assumptions_pilot.py --output-dir '{out.relative_to(ROOT)}' --archive /private/tmp/calitree-assumptions-aurora-human-ratings.zip", "```", "",
              "The archive is optional for the numerical replay; it is needed to recover the images. The expected archive digest is in manifest.json. The AURORA download ID and pinned source are in run/setup_aurora_bench.py.", "",
              "- [Visual case review](case_review.html)", "- [Case selection and source hashes](manifest.json)", "- [Numerical summary](summary.json)", "- [Per-case distributions](case_results.json)", "- [Fold definitions and learned trees](learned_trees.json)", "- [Exact historical records used](selected_records.json)", "- [Assistant visual audit](visual_audit.json)", ""]
    (out / "report.md").write_text("\n".join(lines))
    cards = []
    for bundle, d in zip(bundles, details):
        c = bundle["case"]
        n = notes[c["case_id"]]
        esc = html.escape
        rows = "".join(f"<tr><td>{esc(arm_names[a])}</td><td>{v['correct']}/10</td><td>{esc(str(v['counts']))}</td></tr>" for a, v in d["arms"].items())
        notes_html = "".join(f"<p><strong>{esc(k.replace('_', ' ').capitalize())}:</strong> {esc(n[k])}</p>" for k in ["observation", "decomposition_audit", "policy_audit"])
        cards.append(f"""<section id="{c['case_id']}"><h2>{c['case_id']}: {esc(c['instruction'])}</h2>
<p>{esc(c['task'])} · Human mean {c['human_score']:.3f} → {c['target_label']} · {esc(c['optimizer'])}, round {c['optimized_round']}</p>
<div class="pair"><figure><img src="images/{c['case_id']}/source.png" alt="Source image for {c['case_id']}"><figcaption>Source</figcaption></figure><figure><img src="images/{c['case_id']}/edited.png" alt="Edited image for {c['case_id']}"><figcaption>Edited</figcaption></figure></div>
{notes_html}<table><tr><th>Arm</th><th>Correct</th><th>Repeated labels</th></tr>{rows}</table>
<details><summary>Independent requirements and leaf distributions</summary><pre>{esc(json.dumps({'requirements':d['requirements'], 'leaf_stats':d['leaf_stats']}, indent=2))}</pre></details>
<details><summary>Original selected prompt</summary><pre>{esc(bundle['ablation']['original']['prompt'])}</pre></details>
<details><summary>Extracted semantic policy</summary><pre>{esc(json.dumps(bundle['structured']['extraction']['spec'], indent=2))}</pre></details>
<details><summary>Recorded rationales for every arm</summary><pre>{esc(json.dumps({a:[{'label':r['label'],'rationale':r['rationale']} for r in v['repeats']] for a,v in bundle['ablation']['arms'].items()}, indent=2))}</pre></details></section>""")
    content = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CaliTree: ten-case assumption audit</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:auto;padding:24px;color:#20252d;background:#fafafa}h1,h2{line-height:1.25}section{padding:24px 0;border-top:1px solid #ccc}.pair{display:flex;gap:20px;align-items:flex-start}figure{margin:0;flex:1;min-width:0}img{display:block;width:100%;height:350px;object-fit:contain;background:#eee}figcaption{text-align:center}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #ddd;padding:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace}details{margin:12px 0}summary{cursor:pointer;font-weight:600}@media(max-width:650px){.pair{display:block}img{height:auto}figure{margin-bottom:16px}td,th{padding:4px}}</style>
<h1>Ten-case assumption audit</h1><p>Retrospective real-model traces; ten repeats per case and arm. No new model calls. Visual notes are an unblinded Codex inspection, not independent human concept labels.</p><p><a href="report.md">Full methodology and findings</a> · <a href="summary.json">Numerical results</a></p>""" + "\n".join(cards) + "</html>"
    (out / "case_review.html").write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bases = {r["item_id"]: r for r in read_rows(SOURCE / "baseline_predictions.jsonl")}
    ablations = read_rows(SOURCE / "structured_ablation_results.jsonl")
    structured = read_rows(SOURCE / "structured_decision_results.jsonl")
    trees = read_rows(TREE_SOURCE)
    cases, bundles = [], []
    for index, (task_id, reason) in enumerate(SELECTED):
        choices = [r for r in ablations if r["item_id"].startswith("aurora-task-" + task_id + "::")]
        # Fixed optimizer preference, not chosen according to pilot results.
        a = sorted(choices, key=lambda r: (r["method"] != "textgrad", r["round"]))[0]
        b = bases[a["item_id"]]
        t = next(r for r in trees if r["item_id"] == a["item_id"] and r["method"] == a["method"])
        s = next(r for r in structured if r["item_id"] == a["item_id"] and r["method"] == a["method"] and r["round"] == a["round"])
        assert t["source_round"] == a["round"]
        assert t["instruction"] == b["instruction"]
        assert t["target_label"] == a["target_label"] == b["target_label"]
        assert s["original_prompt_sha256"] == hashlib.sha256(a["original"]["prompt"].encode()).hexdigest()
        c = {k: b[k] for k in ["item_id", "task_uid", "task", "model", "instruction", "human_score", "target_label", "source_split", "source_image_path", "edited_image_path"]}
        c.update(case_index=index, case_id=f"C{index+1:02d}", selection_reason=reason,
                 optimizer=a["method"], optimized_round=a["round"])
        cases.append(c)
        bundles.append({"case": c, "ablation": a, "tree": t, "structured": s})
    assert len({c["task_uid"] for c in cases}) == 10
    assert Counter(c["target_label"] for c in cases) == {"no": 3, "partial": 4, "yes": 3}
    assert len({c["task"] for c in cases}) == 8
    assert len({c["model"] for c in cases}) == 5
    provenance_files = [SOURCE / name for name in ["baseline_predictions.jsonl", "structured_ablation_results.jsonl", "structured_decision_results.jsonl", "repair_traces.jsonl", "run_config.json"]] + [TREE_SOURCE]
    manifest = {"created_at": datetime.now().isoformat(), "experiment": "ten_case_assumptions_audit",
                "mode": "retrospective_recorded_repeats_and_new_local_tree_fits", "new_model_calls": 0,
                "selection": "Metadata-stratified diagnostic subset of optimized cases, not a population estimate",
                "repeats": 10, "model": "gpt-5.4-mini", "temperature": 0.3,
                "tree_settings": {"max_depth": 2, "min_samples_leaf": 20, "random_state": 44},
                "analysis_script_sha256": digest(Path(__file__)),
                "visual_audit_sha256": digest(AUDIT_PATH),
                "optimizer_selection": "TextGrad first if available, otherwise GEPA; earliest stored ablation round",
                "source_files": [{"path": str(p), "sha256": digest(p)} for p in provenance_files],
                "cases": cases}
    if args.archive:
        actual = digest(args.archive)
        assert actual == "8a3430a01cda0139d4c99835a75dca98e16ec6ccc486fa30afa4504f3f18c69f"
        manifest["archive_sha256"] = actual
        with zipfile.ZipFile(args.archive) as z:
            for c in cases:
                target = out / "images" / c["case_id"]
                target.mkdir(parents=True, exist_ok=True)
                for role in ["source", "edited"]:
                    original = c[role + "_image_path"]
                    member = "human_ratings/" + original.split("human_ratings/", 1)[1]
                    path = target / (role + ".png")
                    path.write_bytes(z.read(member))
                    c[role + "_local_image"] = str(path)
                    c[role + "_image_sha256"] = digest(path)
    save(out / "manifest.json", manifest)
    save(out / "run_config.json", {k: v for k, v in manifest.items() if k != "cases"})
    save(out / "selected_records.json", bundles)
    all_features, details, arm_predictions = [], [], defaultdict(list)
    for bundle in bundles:
        c, a, t = bundle["case"], bundle["ablation"], bundle["tree"]
        d = {"case_id": c["case_id"], "instruction": c["instruction"], "target_label": c["target_label"],
             "requirements": t["decomposition"]["requirements"], "arms": {}}
        for arm, values in [(name, value["repeats"]) for name, value in a["arms"].items()] + [("fixed_condition_tree", t["search"])]:
            assert len(values) == 10, (c["item_id"], arm)
            assert len({r["call_id"] for r in values}) == 10, (c["item_id"], arm, "duplicate repeat")
            assert all(r.get("valid") and r["label"] in LABELS for r in values), (c["item_id"], arm)
            labels = [r["label"] for r in values]
            d["arms"][arm] = {**distribution(labels), "correct": labels.count(c["target_label"])}
            arm_predictions[arm].extend(ENCODE[v] for v in labels)
        ref = d["arms"]["fresh_natural"]
        for arm in ["semantic_json", "controlled_prose", "mechanical_json", "fixed_condition_tree"]:
            alt = d["arms"][arm]
            alt["tv_from_fresh_natural"] = sum(abs(ref["counts"].get(l, 0) - alt["counts"].get(l, 0)) for l in LABELS) / 20
            alt["modal_agreement_with_fresh_natural"] = (ref["mode"] == alt["mode"]) if ref["mode"] != "tie" and alt["mode"] != "tie" else None
        leaf_stats = {}
        for j, req in enumerate(d["requirements"]):
            for kind in ["presence", "fidelity"]:
                labels = [r["requirements"][j][kind]["label"] for r in t["search"]]
                leaf_stats[req["id"] + ":" + kind] = distribution(labels)
        leaf_stats["preservation"] = distribution([r["preservation"]["label"] for r in t["search"]])
        d["leaf_stats"] = leaf_stats
        d["unstable_leaf_count"] = sum(not r["stable"] for r in leaf_stats.values())
        d["features"] = [features(t, r) for r in t["search"]]
        all_features.extend(d["features"])
        details.append(d)
    y = np.array([ENCODE[c["target_label"]] for c in cases for _ in range(10)])
    indices = np.repeat(np.arange(10), 10)
    arm_metrics = {arm: evaluate_predictions(y, np.array(values), indices) for arm, values in arm_predictions.items()}
    learned = fit_trees(cases, all_features, out)
    save(out / "case_results.json", details)
    summary = {"cases": 10, "arm_metrics": arm_metrics,
               "unstable_atomic_leaves": sum(d["unstable_leaf_count"] for d in details),
               "total_atomic_leaves": sum(len(d["leaf_stats"]) for d in details),
               "cases_with_unstable_leaves": sum(d["unstable_leaf_count"] > 0 for d in details),
               "mean_tv": {arm: float(np.mean([d["arms"][arm]["tv_from_fresh_natural"] for d in details])) for arm in ["semantic_json", "controlled_prose", "mechanical_json", "fixed_condition_tree"]},
               "modal_agreement": {arm: dict(Counter(str(d["arms"][arm]["modal_agreement_with_fresh_natural"]) for d in details)) for arm in ["semantic_json", "controlled_prose", "mechanical_json", "fixed_condition_tree"]}}
    # Cluster bootstrap: ten task groups are the independent units, not 100 calls.
    rng = np.random.default_rng(44)
    resamples = rng.integers(0, 10, size=(10000, 10))
    reference = np.array([d["arms"]["fresh_natural"]["correct"] / 10 for d in details])
    summary["task_bootstrap_95_percent_intervals"] = {}
    for arm in arm_predictions:
        rates = np.array([d["arms"][arm]["correct"] / 10 for d in details])
        summary["task_bootstrap_95_percent_intervals"][arm] = {
            "accuracy": np.quantile(rates[resamples].mean(axis=1), [.025, .975]).tolist(),
            "difference_from_fresh_natural": np.quantile((rates-reference)[resamples].mean(axis=1), [.025, .975]).tolist(),
        }
    summary["unchanged_seed_prompt_cases"] = [
        b["case"]["case_id"] for b in bundles
        if hashlib.sha256(b["ablation"]["original"]["prompt"].encode()).hexdigest()
        == "3f72b992a4234652ce44be0ddcf1d9017d886dc9dac48091b7cba494a9167970"
    ]
    save(out / "summary.json", summary)
    write_reports(out, manifest, summary, details, learned, bundles)
    compact = {k: v for k, v in summary.items() if k != "arm_metrics"}
    compact["arms"] = {a: {k: v for k, v in m.items() if k not in ["cases", "confusion"]} for a, m in arm_metrics.items()}
    compact["trees"] = {r: {k: v["repeat_accuracy"] for k, v in m.items() if k in ["leave_task_out", "leave_category_out", "resubstitution"]} for r, m in learned.items() if r in FEATURES}
    print(json.dumps(compact, indent=2))
    (out / "run.log").write_text(json.dumps(compact, indent=2) + "\n")
    (out / "llm-histories.log").write_text(json.dumps({"event": "no_new_model_calls", "historical_records": "selected_records.json"}) + "\n")


if __name__ == "__main__":
    main()
