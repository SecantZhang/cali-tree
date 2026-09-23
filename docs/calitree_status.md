# Cali-Tree / Rubric-Lite: canonical path and version status

This is the one-page map of what is **live**, what is a **frozen baseline**, and what is a
**recorded negative control**. It exists so the many versions in this project stop being
confusing: only the canonical path below is extended; everything else is kept for
reproducibility and to stop us re-running settled dead ends. Nothing here is deleted.

For the full experimental record see [calitree.md](calitree.md); for the goal/spec see
[calitree_goal.md](calitree_goal.md); for protocols and results see
[experiments/](experiments/).

---

## TL;DR

- **Canonical forward path:** the *flat, abstention-first judge* — one global rubric call →
  calibrated three-class label → calibrated abstention. No prompt tree.
- **Frozen baselines (reproducibility anchors, do not iterate):** the whole Cali-Tree
  hierarchy (`calitree_v2` end-to-end) and Rubric-Lite v4 as evaluated.
- **Negative controls (kept for the record, do not extend):** `calitree_v1/v3/v4`,
  `rubric_lite_v1/v2/v3/v5/v6`, the score-pattern rules, and the gpt-4.1 A/B.

## The decision: converge on one architecture

The evidence says the **hierarchy is not the lever**. On the 1,200-case held-out set the
routed-tree prediction *before* consensus and editor-prior resolution was **77.58%** —
*below* the flat initial rubric at **78.25%**. Cali-Tree only reached 82.83% after adding
three global judgments plus a fitted editor prior, and the live evidence run rejected 13 of
20 merges and fell back to the root on 55% of cases. Meanwhile flat Rubric-Lite v4 (one call
+ two cutpoints) ≈ matches the whole tree at full coverage (81.33% vs 82.83%).

So the parts that actually move results are **independent-judge consensus** and
**calibrated abstention / editor-reliability priors** — both architecture-agnostic. The
hierarchy (leaves, embeddings, clustering, merge synthesis, routing) is therefore retired to
a frozen baseline, and all new work happens on the flat path.

**This is now directly confirmed, not just inferred.** A flat single-global-prompt path
(`calitree_train` with `architecture=rubric_lite`: no embeddings, no leaves, no clustering, no
merges, no routing) running the identical consensus/editor-prior/selective-policy code
reproduces v2's full-1,200-case numbers within 0.1–3pp on every full-coverage metric, and
**matches v2's deployable selective headline**: 93.14% accepted accuracy @ 63.17% coverage
(n=758) versus v2's 92.87% @ 64.25% (n=771). See
[`calitree_flat_selective_result.json`](experiments/calitree_flat_selective_result.json).

### Canonical forward path (what it is)

```text
SOURCE + EDITED + instruction
  -> one global rubric call (Rubric-Lite v4 evidence scores)
  -> calibrated three-class label (two fitted cutpoints on the min-evidence score)
  -> [optional] independent three-way consensus for robustness
  -> calibrated abstention as the deployment product (needs_human)
  -> report full-coverage label AND auto accuracy + coverage, separately
```

- **Keeps:** the flat single-rubric judge, calibrated cutpoints, three-way consensus, and
  calibrated abstention (the strong deployable result — 92.87% auto accuracy at 64% coverage).
- **Drops (to baseline):** task leaves, component embeddings, semantic clustering, merge
  synthesis, routing thresholds, promoted branches.
- **First confirming experiment — done, confirmed:** the 92.87%/64% selective result was
  reproduced with the consensus + editor-reliability policy on a *flat* rubric (no tree):
  93.14% @ 63.17% coverage on the same 1,200-case held-out set
  (`calitree_flat_selective_result.json`). The tree is fully retired; the Cali-Tree selective
  numbers are now attributable to the flat path, not just the frozen hierarchy.

## Version status

### Architectures

| Architecture | Status | Note |
|---|---|---|
| Flat calibrated judge + abstention (Rubric-Lite line) | **Canonical** | The forward path above. |
| Cali-Tree hierarchy, `specialization_mode=replace` (v2) | **Frozen baseline** | Source of the 82.83% full-coverage and 92.87% selective numbers; preserved per the goal doc. Not extended. |
| Cali-Tree **flat**, `architecture=rubric_lite` on `calitree_train` | **Tested — confirmed positive** | One global node, no embeddings/leaves/clustering/merges/routing, running the exact same three-way consensus + editor-prior + selective-policy code as v2. Reproduces v2's full-1,200 numbers within 0.1–3pp on every full-coverage metric and matches the selective headline: 93.14% @ 63.17% coverage vs v2's 92.87% @ 64.25% (`calitree_flat_selective_result.json`). This is the "first confirming experiment" below, now closed. |
| Cali-Tree **delta-tree**, `specialization_mode=additive` | **Tested — negative (closed)** | Opt-in redesign: additive specialization accumulates validated deltas into a root, leaves cluster by failure mode, localized change signal targets `partial`. Dev-slice result: mechanism converges (beats flat) but the coverage-selected root abandoned `partial` (F1 0.0). **Fixed with `root_objective=balanced` and re-validated at full 1,200-case scale: partial F1 recovers to 0.21 (bug confirmed fixed), but the fixed tree still loses to frozen v2 on every metric** (acc −0.6pp, balanced −4.3pp, partial recall −10.4pp; `calitree_delta_tree_result.json`). Closes the investigation: additive specialization is not an improvement over v2's consensus/editor-prior machinery at scale. v2 replace mode is the default and stays frozen. |

### Prompt template versions — `vejudge/core/prompts/templates/`

Two independent naming lines share a `vN` suffix; do not conflate them. `calitree_vN` are the
*tree* prompt bundles; `rubric_lite_vN` are the *flat* rubric prompts.

| Template | Line | Status | Note |
|---|---|---|---|
| `calitree_v2` | tree | Frozen baseline (tree default) | Semantic-consistency rubric used by the frozen hierarchy. |
| `calitree_v1` | tree | Negative control | Weak class boundaries; superseded by v2. |
| `calitree_v3` | tree | Negative control | Four-field decomposition; all merges failed. |
| `calitree_v4` | tree | Negative control | Single fulfillment field; over-predicts partial/yes. |
| `rubric_lite_v4` | flat | **Canonical** | Class-preserving ordinal evidence; the live rubric. |
| `rubric_lite_partial_v2` | flat | Canonical (optional) | Yes-only partial-progress verifier used with v4. |
| `rubric_lite_v1` | flat | Negative control | Condition evidence; inadequate accuracy. |
| `rubric_lite_v2` | flat | Negative control | Three-view vote; worse accuracy + partial. |
| `rubric_lite_v3` | flat | Negative control | Ordinal scores; erased the `yes` class. |
| `rubric_lite_v5` | flat | Negative control | Core-completion; failed development gate. |
| `rubric_lite_v6` | flat | Negative control | Evidence ledger; failed stage-1 gate. |

### Frozen artifacts — `vejudge/core/calibration/artifacts/`

| Artifact | Status | Note |
|---|---|---|
| `rubric_lite_v4_imagenhub.json` | **Canonical** | v4 cutpoints for ImagenHub SC; no selective policy. |
| `rubric_lite_v4_editinspector_cutpoints_v1.json` | Canonical candidate | Two-cutpoint domain adaptation for EditInspector. |
| `rubric_lite_v4_editinspector_selective_v1.json` | Frozen, scope-limited | Perfect-evidence selective `yes` rule; EditInspector-only (fails on ImagenHub). |
| `rubric_lite_v5_core_completion_experimental.json` | Negative control | Experimental. |
| `rubric_lite_v6_evidence_ledger_experimental.json` | Negative control | Failed stage-1. |
| `gepa_v1_imagenhub.json` | **Tested — negative** | A flat global prompt optimized by GEPA (reflective mutation + Pareto search; runs in an isolated Python 3.10+ venv, see `run/gepa_baseline/`), evaluated via `gepa_frozen` → `calitree_judge` → `calitree_eval` exactly like any other flat baseline. On the same dev slice: accuracy ties Initial Rubric (0.808) but **underperforms Global TextGrad** on accuracy (0.808 vs 0.825), balanced accuracy (0.384 vs 0.470), and partial F1 (**0.0 vs 0.4375**) — despite ~2x TextGrad's optimizer compute (754 rollouts + 33 reflection calls, 1.46M tokens vs. TextGrad's ~704 calls). See `gepa_baseline_result.json`. Not promoted; kept as a reproducible negative baseline. |

### Calibration modes — `rubric_lite_fit` `calibration_mode`

| Mode | Status | Note |
|---|---|---|
| `min_scalar` (two cutpoints on `min` of the three scores) | **Canonical** | The frozen Rubric-Lite v4 calibrator. |
| `two_gate` (presence × completeness cutpoints) | **Tested — negative** | Two independent gates did **not** beat the existing min-scalar on partial F1 or macro F1 (`rubric_lite_two_gate_result.json`): dev-slice partial F1 0.24 (two_gate) / 0.30 (min_scalar+macro_f1) vs **0.40** for the frozen min-scalar+accuracy-guarded. Confirms partial is a *signal* problem, not a calibration one. Kept as a reproducible option; not promoted. |

### Referral modes — `calitree_judge` `human_review_mode`

| Mode | Status | Note |
|---|---|---|
| `selective_policy` (consensus support + editor reliability) | **Canonical** | The strong abstention result; to be lifted onto the flat path. |
| `off` | Canonical | Reproduces frozen full-coverage behavior. |
| `evidence_policy` (this session) | Open sub-problem | Target-blind evidence referral; on the dev slice it fired zero times — its signals must be made to vary (consensus-support bands, score margin) before it is competitive. |

### Workflows — `workflows/examples/`

| Kind | Files | Status |
|---|---|---|
| Flat / Rubric-Lite | `rubric_lite_imagenhub*.json`, `rubric_lite_editinspector_{calibrated,final,zero_shot}.json` | Canonical |
| Flat negative controls | `rubric_lite_editinspector_{core_completion,evidence_ledger}.json` | Negative control |
| Tree | `calitree_imagenhub.json`, `calitree_imagenhub_evidence.json` | Frozen baseline / evidence sub-experiment |

## What the labels mean

- **Canonical** — the live forward path. New work extends only these.
- **Frozen baseline** — reproducibility anchor. Tests pin it; its numbers are cited; it is not
  extended or "improved." Required by the goal doc.
- **Negative control** — a settled dead end, kept so the failure is not re-run. See its
  `*_result.json` for the evidence. Do not build on it.

## Why (the five lessons behind the decision)

1. The hierarchy is not the lever — routed tree 77.58% < flat rubric 78.25%; gains came from
   consensus + editor priors (`260728-14:29:10-exps`).
2. `partial` is a representation/signal problem, not a calibration or judge-model one — ~95%
   of partial cases share their exact three-score tuple with a `no`/`yes` case
   (`rubric_lite_score_collision_audit.json`). **Four independent moves all failed to beat the
   existing flat calibrator's partial F1 ≈ 0.40** (`rubric_lite_two_gate_result.json`): two-gate
   presence/completeness cutpoints, a macro-F1 objective, a partial-progress verifier, and a
   stronger judge (gpt-4.1, which *regressed* it). Source+edited+instruction simply lack a
   cleanly separable "partially done" signal; the only untried lever is a different signal
   (region-grounded pixel localization), not more calibration. Treat ~0.40 as the ceiling here.
3. Much "error" is human disagreement — only 8–31% of partial targets are unanimous; model
   ~55% on disputed vs ~90%+ on unanimous. 90% on the median label is not reachable without
   resolving cases humans dispute.
4. Abstention is the deployable win — selective 92.87% @ 64% coverage, 96.6% on unanimous.
5. Simpler ≈ as good — Rubric-Lite v4 (one call + two cutpoints) ≈ matches the whole tree at
   full coverage, and transfers better than richer rules.
