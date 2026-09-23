# Cali-Tree / Rubric-Lite: complete version and worktree comparison report

This is a ground-truth reference for independently evaluating every prompt version and every
code difference between the active worktrees, so you don't have to reconstruct it from chat.
Every claim below points to a specific file, run directory, or diff you can re-check yourself.
Nothing here was paraphrased from memory without verification — prompt texts were read in
full, code was diffed directly, and every number is pulled from a result JSON or a live run
directory, listed alongside the claim.

See also: [calitree_status.md](calitree_status.md) (canonical/frozen/negative-control map),
[calitree.md](calitree.md) (full narrative history), [calitree_goal.md](calitree_goal.md)
(original spec).

---

## 1. Worktree inventory

| Worktree | Branch | Base commit | State |
|---|---|---|---|
| `vejudge` (root) | `main` | `374ad61` | Clean; local `main` is 5 commits ahead of `origin/main` (unpushed, pre-existing, unrelated) |
| `.claude/worktrees/calitree-goal-plan-1940df` (**this one**) | `claude/calitree-goal-plan-1940df` | `7670df1` | This session's uncommitted work |
| `.claude/worktrees/calitree-implementation` (**"codex"**) | `codex/calitree-implementation` | `7670df1` (same base) | Uncommitted parallel work by a Codex agent; pushed to origin only at the unchanged base commit |
| `.claude/worktrees/markdown-plan-implementation-01604c` | detached @ `7670df1` | `7670df1` | Clean, nothing to lose |
| `.claude/worktrees/prompt-calibration-explore` | `prompt-calibration-explore` | +0/-10 vs main | Already fully merged; only stray junk files |
| `~/.codex/worktrees/d2f8/prompt-calibration-explore` | `codex/edit-aware-video-judge` | +0/-9 vs main | Already fully merged; only stray junk files |
| `/private/tmp/vejudge-preprocessed-evidence-db` | — | — | No longer a git repo (stale/prunable worktree) |

**Merge safety** (already verified): local `main` has diverged from the `7670df1` base with 10
merge commits, but touches only `workflows/joint_semantic_calibration_M3_M5_M6.json` — zero
file overlap with either `calitree-goal-plan-1940df` or `calitree-implementation`'s changes.

The rest of this report compares **`calitree-goal-plan-1940df`** ("mine") against
**`calitree-implementation`** ("codex") in detail, since those are the two with substantive,
overlapping, uncommitted work.

---

## 2. Prompt version algorithm differences

### 2a. Cali-Tree line — `vejudge/core/prompts/templates/calitree_v{1,2,3,4,v3_evidence}/`

All versions share the same JSON-output contract discipline and SOURCE/EDITED framing. The
table below is the **decision procedure and output schema**, read directly from each
`initial_rubric.txt` (paths below; open them yourself to verify verbatim):

| Version | Path | Decision mechanism | Output schema |
|---|---|---|---|
| **v1** | `calitree_v1/initial_rubric.txt` | Single free-form judgment: "how well the edit instruction was satisfied while preserving unrelated source content" — no decomposition, no explicit tie-break rules. | `{"label","rationale"}` |
| **v2** (frozen default) | `calitree_v2/initial_rubric.txt` | 4-step procedure: (1) decompose instruction into explicit semantic conditions, (2) compare SOURCE/EDITED per condition citing visible evidence, (3) check edit locality, (4) apply labels with two explicit tie-break rules (`no` vs `partial` requires *some* visible evidence per condition; `partial` vs `yes` requires the overall idea followed). | `{"label","rationale"}` |
| **v3** (original, frozen negative control — distinct from "v3_evidence" below) | `calitree_v3/initial_rubric.txt` | Decomposes into **4 independent structured fields** (`requested_change`: none/partial/full; `subject_identity`: wrong/ambiguous/correct/n-a; `spatial_relation`: wrong/partial/correct/n-a; `scene_continuity`: replaced/degraded/preserved), then a **deterministic rule table** maps field combinations to `no`/`partial`/`yes`. | `{"rubric_version":"sc-v3","rubric_scores":{4 fields},"label","rationale"}` |
| **v4** (frozen negative control) | `calitree_v4/initial_rubric.txt` | Single `fulfillment` field (none/partial/full) that **maps directly** to the label (none→no, partial→partial, full→yes) — the simplest, one-field variant. | `{"fulfillment","label","rationale"}` |
| **v3_evidence** (Codex, uncommitted, `calitree-implementation` only) | `calitree_v3_evidence/initial_rubric.txt` | **Byte-identical to v2** (verified `diff`, zero output) through the entire decision procedure, labels, and both tie-breaks. Adds one appended paragraph after the tie-breaks: report three additional **self-assessed determinability fields** — `conditions_visible` (bool), `evidence_contradictory` (bool), `edit_incomplete_vs_undeterminable` ("incomplete"\|"undeterminable") — explicitly stated to never change the label. | `{"label","rationale","conditions_visible","evidence_contradictory","edit_incomplete_vs_undeterminable"}` |

**Important naming trap:** `calitree_v3` (four-field, frozen) and `calitree_v3_evidence`
(Codex's, uncommitted) are unrelated prompt bundles that happen to share the "v3" prefix. Do
not conflate them.

**Companion files** (`extract_components.txt`, `merge_prompts.txt`, `gradient_feedback.txt`,
`conflict_resolver.txt`) — v2 is the only version with `conflict_resolver.txt`; v1/v3/v4 have
4 files each (no conflict resolver). **v3_evidence's other four files are byte-identical to
v2's** (verified `diff`, zero output for all four).

### 2b. Rubric-Lite line — `vejudge/core/prompts/templates/rubric_lite_v{1..6}/`, `rubric_lite_partial_v2/`

These are the **flat** (non-tree) judge prompts — a different architecture line entirely.

| Version | Decision mechanism | Output schema |
|---|---|---|
| **v1** | Per-condition ordinal evidence scale (none/partial/full) + explicit 3-step decision rule (any `none` or replaced scene → no; any `partial` → partial; all `full` → yes). | `{"conditions":[{condition,evidence}],"scene","label","rationale"}` |
| **v2** | **Three-view vote**: `evidence_gate`, `completion_gate`, `locality_gate` each independently vote no/partial/yes; resolved by strict majority, ties → partial. | `{"rubric_votes":{3 gates},"label","rationale"}` |
| **v3** | Three **ordinal 0–100 scores** (`change_evidence`, `specification_fidelity`, `source_preservation`); evidence score = **min** of the three; default cutpoints no<35, partial 35–89, yes 90–100 (learnable). | `{"rubric_version":"rubric-lite-ordinal-v3","ordinal_scores":{3},"label","rationale"}` |
| **v4** (canonical, frozen default) | Same 3-score/min-scalar mechanism as v3, with refined per-dimension guidance (explicit penalty list for hybrids/duplicates/leftovers/wrong containers). This is the version behind every frozen artifact (`rubric_lite_v4_imagenhub.json`, etc.) and this session's two-gate work. | Same as v3 |
| **v5** (frozen negative control) | Same 3-score mechanism, but explicitly instructs **tolerance for generation-quality defects** (blur, distortion, unreadable text must not reduce `specification_fidelity`); uses **discrete** cutpoints (0/50/100) rather than a continuous scale. | Same as v3/v4 |
| **v6** (frozen negative control) | Replaces the 3-score vector with an **evidence ledger**: per-condition `status` (absent/emerging/mostly/complete) + `achieved_evidence`/`missing_evidence` free text + `residual_type` (9-way categorical) + one continuous `semantic_completion` score + `scene_validity`. Cutpoints on `semantic_completion` (no<25, partial 25–74, yes 75–100). | `{"rubric_version":"...v6","conditions":[...],"achieved_evidence","missing_evidence","residual_type","semantic_completion","scene_validity","label","rationale"}` |
| **partial_v2** (verifier, used conditionally with v4) | A **second-pass verifier** run only on primary `yes` predictions: per-condition none/partial/full evidence + `requested_delta` (absent/recognizable) + `intended_subject` (correct/wrong) + `scene` (same/replaced); deterministic 3-rule mapping to no/partial/yes. | `{"rubric_version":"rubric-lite-partial-v2","conditions":[...],"requested_delta","intended_subject","scene","label","rationale"}` |

**None of the Rubric-Lite versions were touched by Codex's worktree** — `rubric_lite.py` and
`rubric_lite_nodes.py` have zero diff there. This session's two-gate work (`two_gate_label`,
`fit_two_gate_thresholds`) is new, mine only, and operates on the v4 prompt's existing
`change_evidence`/`specification_fidelity` scores without any new prompt.

---

## 3. Code/algorithm differences: `calitree-goal-plan-1940df` vs `calitree-implementation`

Both diffed against the shared base commit `7670df1`. File-level stats:

| File | Mine (lines +/-) | Codex (lines +/-) | Overlap? |
|---|---:|---:|---|
| `vejudge/core/calibration/calitree.py` | +145/− | +89/− | **Same file, disjoint additions** (see 3a) |
| `vejudge/interface/node_calibration/calitree_nodes.py` | +625/− | +429/− | **Same file, disjoint additions** (see 3b) |
| `vejudge/core/calibration/rubric_lite.py` | +342/− | 0 (untouched) | No overlap |
| `vejudge/interface/node_calibration/rubric_lite_nodes.py` | +83/− | 0 (untouched) | No overlap |
| `vejudge/interface/node_db/editinspector_source_node.py` | 0 (untouched) | +34/− | No overlap |
| `web/src/nodes/*` | +31/− (2 files) | 0 (untouched) | No overlap |
| Tests | +580 lines (3 files) | +403 lines (1 file) | Disjoint test functions |
| `run/README.md`, `logs/updates/updates_summary.md` | small additions | small additions | Same lines touched — **would conflict if both were committed as-is** |

### 3a. `vejudge/core/calibration/calitree.py` — the pure tree algorithm

- **Mine adds**: `specialization_mode` ("replace"\|"additive"), `merge_objective`
  ("covered_accuracy"\|"balanced"), `require_ge_base`, `root_objective` ("balanced"\|"coverage").
  In additive mode: the merge acceptance gate switches from covered-case accuracy to a
  no-regression-vs-base balanced-accuracy guard, and the returned root becomes the
  **accumulated widest validated merge** (selected by balanced accuracy under `root_objective`)
  instead of a fallback — guaranteeing the root is never worse than the flat base. Routing
  gains `route_default_to_root`. Also adds `ordinal_absolute_error`/`ORDINAL_VALUE` and an
  `ordinal_mae` field in `classification_metrics`.
- **Codex adds**: the **same** `ordinal_mae` addition to `classification_metrics` (near-identical
  formula, different variable names: `ORDINAL` vs my `ORDINAL_VALUE`), plus a standalone
  `tree_metrics(tree)` function (leaf/merge/compression/root-coverage summary derived purely
  from the tree dict — architecturally cleaner placement than my node-layer equivalent, since
  it needs no live judge data).
- **Untouched by Codex**: the builder (`CaliTreeBuilder.build()`) itself — no additive mode, no
  root-objective change, no failure-mode grouping support. Codex's tree is the unmodified v2
  replace-mode algorithm throughout.

### 3b. `vejudge/interface/node_calibration/calitree_nodes.py` — the node/training layer

- **Mine adds**:
  - `_failure_mode_signature`/`_failure_mode_groups` — clusters leaves by `(base-prediction,
    target)` residual signature instead of task, gated behind additive mode.
  - `_referral_quality_metrics` (Metric 3: consensus-referral precision/recall/F1, by-editor,
    by-operation-family) and `_tree_metrics`/`_route_metrics` (structural + routing metrics,
    node-layer placement).
  - `_evidence_signals`/`_row_evidence_signals`/`_evidence_referral`/
    `_fit_evidence_referral_policy` — a referral policy **fitted from training labels**
    (grid-search over rule type × routing-support threshold, selected to maximize
    referral-F1 under a coverage floor) reading purely structural signals (`consensus_tie` +
    routing geometry). Zero new prompt fields required.
  - `_media_with_change` + `change_signal` param — attaches a computed localized
    source↔edited change map (new `vejudge/preprocessing/localized_change.py`, numpy+Pillow,
    content-hash cached) as a third image + text descriptor to the judge call.
- **Codex adds**:
  - `_referral_summary`/`_referral_consensus_metrics` — the **same** Metric 3 formula as mine,
    independently derived, plus `_routing_inference_metrics` (routing/depth/fallback metrics —
    see the bug note in §5).
  - `_fit_evidence_referral_policy`/`_evidence_referral_decision` — a referral policy that is
    **not fit from data**: a fixed set of boolean toggles (all default `True`), reading the new
    `calitree_v3_evidence` prompt's self-reported `conditions_visible`/`evidence_contradictory`/
    `edit_incomplete_vs_undeterminable` fields, plus judge-path disagreement (≥3 distinct
    candidate labels) and routing threshold/support. Requires the new prompt version; no
    coverage-floor control.
  - `_extract_evidence_signals` — parses the three new v3_evidence fields out of the judge
    response (returns `None` for v2/v4, so it's additive/inert for other prompt versions).
  - EditInspector × Cali-Tree cross-dataset support is wired through this file's train executor
    consuming the modified `editinspector_source_node.py` (below) — **scope mine doesn't cover**
    (I only extended Rubric-Lite to EditInspector, not the tree).

### 3c. `vejudge/interface/node_db/editinspector_source_node.py` — Codex only

Adds a `split_as` param (`keep`\|`train`\|`test`) letting one `editinspector_source` node's
output be stamped as the training split and another's as the test split, so a single
`calitree_train`→`calitree_judge`→`calitree_eval` graph can run Cali-Tree cross-dataset on
EditInspector (`workflows/examples/calitree_editinspector.json`, Codex-only). Never run live
(dry-run only, see §4).

### 3d. `vejudge/core/calibration/rubric_lite.py` + `rubric_lite_nodes.py` — mine only

Codex has **zero diff** in these files. My additions: `two_gate_label`, `apply_two_gate`,
`fit_two_gate_thresholds`, `cross_validate_two_gate`, `_assign_cv_folds` (shared fold-assignment
helper extracted from the existing ordinal CV), and a `calibration_mode`
(`min_scalar`\|`two_gate`) param on `rubric_lite_fit`/`rubric_lite_apply`, plus
`selection_objective` finally plumbed into `rubric_lite_train` (the objective already existed
in `fit_ordinal_thresholds`/`rubric_lite_fit` — it just wasn't forwarded from the train node).

### 3e. Frontend, wiring, and test coverage

- **Web**: I touched `paramSchemas.ts` (new enum options) and `CaliTreeJudgeNode.tsx` (fixed a
  pre-existing bug where the node's param schema was hardcoded empty, so `human_review_mode`
  was never selectable in the graph editor UI). **Codex touched no web files** — its
  `evidence_policy` mode is backend-only and inherits the same latent UI-invisibility bug.
- **Tests**: mine adds 580 new test lines across 3 files (`test_calitree.py`,
  `test_rubric_lite.py`, `test_calitree_nodes.py`) plus a new `test_localized_change.py`.
  Codex adds 403 new test lines, all in `test_calitree_nodes.py` (test names: see the git diff
  directly — `test_classification_metrics_reports_ordinal_mae`,
  `test_referral_consensus_metrics_separates_disagreement_from_error`,
  `test_tree_metrics_summarizes_compression_from_nodes_and_timeline`,
  `test_v3_evidence_judgment_preserves_label_and_adds_referral_signals`,
  `test_evidence_referral_refers_when_conditions_not_visible`, and 12 more — run
  `git diff 7670df1 -- tests/unit/interface/node_calibration/test_calitree_nodes.py` in the
  `calitree-implementation` worktree for the full list).
- **Docs**: mine adds `calitree_status.md` (canonical/frozen/negative-control map),
  8 preregistered experiment protocol+result JSON pairs, and a `docs/calitree.md` status
  banner. Codex adds only the copied `calitree_goal.md` and two `updates_summary.md`/detail-file
  entries (dated `260730-16:16:46` and `260731-16:49:28` — **note**: both detail files exist on
  disk in the codex worktree but are `.gitignore`d and would silently NOT be included in a
  normal `git add`; the same is true of every detail file I wrote this session — both worktrees
  need `git add -f` on `logs/updates/details/*.md` to actually commit them, matching the
  convention already used by every pre-existing tracked file under that path).

---

## 4. Complete results compendium

### 4a. Historical small-run prompt comparison (pre-existing, from `docs/calitree.md`)

3 training / 11 test cases, `calitree_v1`("v1-era")/`v2`/`v3`/`v4`:

| Version | Test acc | Balanced | Recall no | Recall partial | Recall yes | Accepted/rejected merges | Judge calls | Total tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v1-era | 63.64% | 58.33% | 75.00% | 0.00% | 100.00% | 2/0 | 28 | 35,718 |
| v2 | 63.64% | 55.56% | 66.67% | 100.00% | 0.00% | 2/0 | 50 | 65,807 |
| v3 | 63.64% | 55.56% | 66.67% | 0.00% | 100.00% | 0/3 | 50 | 95,613 |
| v4 | 54.55% | 81.48%* | 44.44% | 100.00% | 100.00% | 2/0 | 17 | 31,269 |

*v4's balanced score is unstable — only 1 partial + 1 yes case in the 11-case test set.
Source: `logs/exps/260728-01:28:26-exps/` (v2), `.../260728-01:16:18-exps/` (v3),
`.../260728-01:32:41-exps/` (v4).

### 4b. Large-scale (1,200-case) Cali-Tree v2 vs Rubric-Lite v4 (pre-existing)

| System | Accuracy | Balanced | Recall partial |
|---|---:|---:|---:|
| Initial rubric (v2, no tree) | 78.25% | 59.81% | 30.37% |
| Cali-Tree v2 (full tree) | 82.83% | 60.41% | 26.67% |
| Rubric-Lite v4 | 81.33% | 55.37% | 28.89% |
| Selective Cali-Tree v2 (abstention) | 92.87% @ 64.25% coverage | 60.07% | 8.11%† |

†Low because the selective policy accepts only 37 human-`partial` cases at all.
Source: `logs/exps/260728-14:29:10-exps/calitree_combined_1200_summary.json`.

### 4c. This session's live experiments (120-case dev slice: 232 train / 120 test, `gpt-4.1-mini`)

| Run | Config | Test acc | Balanced | Macro-F1 | Partial F1 | Run dir |
|---|---|---:|---:|---:|---:|---|
| Evidence-referral baseline | v2 replace, my structural evidence_policy | 80.83% | 36.12% | 37.26% | 20.00% | `logs/exps/calitree-evidence-dev120-v2-exps` |
| Delta-tree | additive + failure_mode + change_signal=all | 81.67% | 51.35%‡ | 41.57% | 0.00%‡ | `logs/exps/calitree-delta-dev120-v2-exps` |
| Two-gate (min_scalar, accuracy) | flat Rubric-Lite, existing calibrator | 83.24%§ | 51.27% | 52.11% | 40.48% | `logs/exps/twogate-dev120-minscalar-acc-exps` |
| Two-gate (min_scalar, macro_f1) | flat Rubric-Lite | 78.69%§ | 52.41% | 49.98% | 30.43% | `logs/exps/twogate-dev120-minscalar-macrof1-exps` |
| Two-gate (two_gate, macro_f1) | flat Rubric-Lite, new calibration | 72.73%§ | 62.17% | 48.50% | 23.81% | `logs/exps/twogate-dev120-macrof1-exps` |
| Stronger judge (gpt-4.1, min_scalar/acc) | flat Rubric-Lite | 79.83%§ | 49.60% | 49.53% | 31.46% | `logs/exps/twogate-dev120-gpt41-minscalar-acc-exps` |
| Stronger judge (gpt-4.1, two_gate) | flat Rubric-Lite | 77.27%§ | 49.91% | 46.89% | 28.57% | `logs/exps/twogate-dev120-gpt41-exps` |
| **Codex comparison** | v2 replace, `calitree_v3_evidence` + fixed evidence_policy | **81.67%** | **47.07%** | **42.11%** | **10.53%** | `../calitree-implementation/logs/exps/codex-devslice-evidence-live-exps` |

‡Delta-tree's root-selection bug (fixed by `root_objective=balanced`, untested live after the
fix — see follow-ups in `calitree_delta_tree_result.json`) let the accumulated root abandon
`partial` entirely for accuracy. §Two-gate/stronger-judge accuracy figures are **out-of-fold
cross-validated** (352-case pool), not a single train/test split — not directly comparable
row-to-row with the other rows' plain test-split numbers; see
`rubric_lite_two_gate_result.json` for the full ladder.

### 4d. Codex-implementation-only artifacts (never run live — dry-run validated only)

- `logs/exps/260731-17:06:26-imagenhub-calitree-full1200-exps/` — errored (same class of
  dry-run-guard-ordering bug I hit and fixed).
- `logs/exps/260731-17:09:10-imagenhub-calitree-full1200-exps/` — dry-run succeeded, `n=0`
  everywhere (no billable calls made). No live full-1200 result exists in that worktree.

---

## 5. Known bugs / caveats found during this comparison

1. **Codex's `fallback_to_root_rate` always reports `0.0`**, and
   **`tree_metrics.overall.structure` always reports `null`**, in a live `calitree_eval` run.
   Root cause: `_routing_inference_metrics(tree=...)` is called with `tree=None` because
   `calitree_eval`'s input sockets don't include `prompt_tree`. Verified by direct count against
   the train report's `predictions` dict: true rate is 46.59% (164/352), not 0%.
2. **The `global_selection` guard rejected TextGrad's global rewrite in both independent runs**
   (mine and Codex's) — the rewritten warm-start prompt scored lower on held-out balanced
   accuracy in both cases (0.560 vs 0.645 mine; 0.664 vs 0.678 Codex's). This means roughly
   half of each system's cases (whichever fall back to the global root) are classified by the
   **literal, unmodified seed prompt**, not by anything TextGrad produced — a third independent
   data point (alongside the delta-tree and two-gate results) that global TextGrad optimization
   doesn't reliably survive its own validation guard.
3. **Leaf/merge-level TextGrad output is real and substantial** (verified: 22/22 leaves in my
   run have prompt text different from the seed), but is a **stochastic byproduct** of each
   run's specific optimizer calls — not a controlled variable between "v2" and "v3_evidence" as
   prompt designs. Any accuracy difference attributed to routed-to-leaf cases is confounded by
   this, not a clean prompt-only ablation.
4. **`logs/updates/details/*.md` files are gitignored** in both worktrees (`.gitignore:16:
   logs/`), even though dozens of pre-existing ones are tracked in history (added via
   `git add -f` at some point). A plain `git add`/`git commit` in either worktree will silently
   drop new detail files unless force-added.

---

## 6. How to reproduce or extend any of this yourself

- Every prompt file is under `vejudge/core/prompts/templates/<version>/` in each worktree —
  `diff` them directly, as done throughout this report.
- Every live run's full artifacts (raw predictions, per-item routing, token usage, `run.log`,
  `llm-histories.log`) are in the `logs/exps/<run-id>-exps/` directories cited above —
  `calitree_train.json` has the actual trained tree (including every node's evolved prompt
  text and the `global_selection` decision); `calitree_eval_evaluate.json` has the full metric
  suite.
- `git diff 7670df1 -- <path>` in either worktree reproduces the exact diffs summarized in §3.
- The 8 preregistered protocol/result JSON pairs in `docs/experiments/` (including this report's
  companion `calitree_worktree_comparison_result.json`) each carry their own `run_dir` pointer
  and a machine-readable version of the numbers above.
