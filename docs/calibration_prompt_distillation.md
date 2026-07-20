# Adversarial-calibration prompt distillation (exploration finding)

Branch: `prompt-calibration-explore`. Goal: an adversarial-calibration method that
produces an *optimized prompt with good generalization*, because the existing
calibrated/optimized prompts were "too wordy and detailed."

## The problem, quantified

The Adversarial Calibration node's per-item `optimized_prompt` (injected into a
downstream Judge's `extra_context` to re-score) was built as **one verdict sentence +
the entire debate reasoning trace, verbatim** (`render_optimized_prompt_addendum` →
`verdict.reasoning_trace`, which concatenates the original rationale + every round's
human-proxy critique + every round's judge response). Measured on a real grounded run
(`logs/exps/260714-09:57:04`, 7 items, M5), via
`vejudge/core/calibration/debate/eval/measure_prompt_verbosity.py`:

| item | old words |
|---|---|
| prj-aberdeen::0 | 320 |
| prj-aberdeen::2 | 984 |
| prj-dog-owner-interview::0 | 340 |
| prj-paris-2025::0 | **2407** |
| prj-qc-testing-lunch::1 | 957 |
| prj-qc-testing-lunch::4 | 809 |
| prj-qc-testing-lunch::6 | 2275 |

Mean **1156 words/item**, worst case **2407** — grows with round count (grounded mode
runs more rounds, so it made this *worse*), stacked verbatim onto an already ~250-word
base judge prompt. And it's a per-item narrative replay: nothing in it transfers to
another item. So it fails on both axes the goal names — concision and generalization.

## Method

Two levels, both deterministic (no extra LM call — consistent with the existing
reasoning-trace design), built on the signal that was already there but unused:
`DebateVerdict.failure_mode_summary`, counts over the fixed 10-key
`FAILURE_MODE_TAXONOMY`, explicitly documented as "the field a future corpus-distillation
pass would group by."

1. **Per-item distilled lesson** (`render_optimized_prompt_addendum`, reworked) — a
   score-correction header, the top-2 flagged judge *tendencies* (taxonomy keys phrased
   as short infinitive clauses), and at most one capped guidance clause (the last
   human-proxy critique's lead sentence, truncated). The full transcript stays in the
   `reasoning` field for *display*, but is no longer injected. Bounded ~40–60 words
   regardless of round count.

2. **Corpus-level generalization prompt** (`render_corpus_calibration_prompt`, new — the
   deferred "aggregation") — aggregates `failure_mode_summary` and signed `score_delta`
   across *all* items into ONE item-independent note naming the top-3 recurring failure
   modes + directional bias. Surfaced on the node's `meta.general_optimized_prompt` and
   in the secondary tab. This is the generalizing artifact: it's meant to be applied to
   *unseen* items, and it generalizes precisely because it's built from a fixed,
   small vocabulary rather than any item's narrative.

## Result (same run)

| | old | new |
|---|---|---|
| mean words/item | 1156 | **52** (95% reduction) |
| max words/item | 2407 | **60** (hard-bounded) |

Corpus prompt (55 words, replaces 8092 words of per-item text):

> Calibration note from 7 adversarially-reviewed items: this judge's recurring
> tendencies are to assert a rationale without citing concrete evidence; to over- or
> under-score based on edit category rather than quality; to let score meaning drift
> across prompts. Overall it tended to under-score (review raised its scores). Weigh
> these tendencies when assigning a score.

That is a genuinely transferable calibration insight — the judge's *systematic* biases
across the corpus (over-confidence, category imbalance, scale drift, a net under-scoring
tendency), in a form you could prepend to the base judge prompt for any future item.

## Why this generalizes (vs. the old form)

- The failure-mode taxonomy is a **closed vocabulary of judge biases**, not free text —
  the same key recurring across items *is* the generalization signal (here
  `overconfident_rationale` appeared in 6/7 items, `category_imbalance` in 4/7).
- The corpus prompt contains **zero item-specific tokens** (a test asserts `prj-` never
  leaks in), so it transfers by construction.
- Per-item prompts are now bounded, so injecting them can't swamp the base prompt.

## Does the sandwich even work? (real, in-sample — `measure_sandwich_effect.py`)

Two completed `judge → calibration → judge` runs were on disk, so the effect is
measurable with **zero new calls** (baseline = `judge-3`, calibrated = `judge-7`, both
real Gemini):

| run | mode | scores changed | baseline MAE | calibrated MAE |
|---|---|---|---|---|
| 260713-17:42:43 | blind | 0/6 | 1.89 | 1.89 |
| 260714-09:57:04 | grounded | **6/6** | 2.06 | **0.25** |

The blind sandwich does nothing (the simulated critic rubber-stamps the judge). The
grounded sandwich moves every item toward the human score, MAE 2.06 → 0.25.

**But this is in-sample and near-tautological.** The grounded debate targets each item's
*own* human anchor, so `judge-7` landing next to the human value largely means "the
debate hit the number it was told to hit." It is *not* evidence of generalization — it's
the strongest possible reason to demand a held-out test.

## Generalization: leave-one-out CV (`cross_validate_calibration.py`)

Per-item grounding can't apply to an unseen item (there's no debate for it). The
**item-independent corpus prompt** is the only thing that *can* transfer, so it's what CV
tests. Cheap trick that makes this ~N calls instead of hundreds: training debates for
every fold are already cached, so a fold's corpus prompt costs nothing — only the N
held-out re-judges are new (baseline held-out scores are already in `judge-3`).

Run on 260714-09:57:04 (6 labeled items, leave-one-out; 6 live held-out re-judges):

| held-out | human | baseline | calibrated (corpus) | \|base−h\| | \|cal−h\| |
|---|---|---|---|---|---|
| prj-aberdeen::0 | 3.08 | 2.0 | 5.0 | 1.08 | 1.92 |
| prj-aberdeen::2 | 3.84 | 2.0 | 5.0 | 1.84 | 1.16 |
| prj-paris-2025::0 | 3.84 | 2.0 | 2.0 | 1.84 | 1.84 |
| prj-qc-testing-lunch::1 | 3.00 | 1.0 | 3.0 | 2.00 | 0.00 |
| prj-qc-testing-lunch::4 | 4.00 | 1.0 | 2.0 | 3.00 | 2.00 |
| prj-qc-testing-lunch::6 | 3.60 | 1.0 | 3.0 | 2.60 | 0.60 |

**Held-out baseline MAE 2.06 → calibrated 1.25** — a ~39% *out-of-sample* reduction from
a prompt that never saw the held-out item's label. That's real generalization (contrast
the tautological in-sample 0.25). 4/6 improved, 1 unchanged, **1 overshot**
(prj-aberdeen::0: 2→5 when the human was 3.08).

Two things this surfaced:

- **Corpus-prompt stability:** across all 6 folds the prompt names the same three
  recurring tendencies and the same under-scoring direction — the signal isn't carried
  by any one item, which is why it transfers at all.
- **Direction without magnitude overshoots.** The prompt said "you under-score" but not
  by how much, so the judge corrected upward and overshot. Fixed by stating the mean
  signed correction ("tended to under-score **by roughly 1.7 points**") — the mean delta
  *is* the average correction the review applied, so it gives the re-judge a target size,
  not just a sign. Implemented + unit-tested; a re-run of the LOO CV (~6 more live calls)
  is the next validation of whether the magnitude hint removes the overshoot.

Caveats: n=6 is directional, not statistically strong — repeat on a larger labeled set.
And the corpus prompt only encodes *direction+magnitude+bias-modes*, so it's a global
recalibration, not a per-item fix; a full three-way A/B (uncalibrated / old verbose
per-item / new lean corpus) via `core/eval/metrics.py` + `postprocessing/align.py::
build_aligned_rows` is the recommended larger experiment before adopting it as default.

## Recommendation

Adopt the distilled per-item prompt as the default (pure win: 95% shorter, same
information, bounded). Treat the corpus `general_optimized_prompt` as the primary
*generalization* lever and validate it with the live A/B above before wiring it as a
dataset-wide Judge input (a natural next feature: a `general_calibration` socket on the
Judge node, distinct from the per-item `calibration` one).

## Verification done on this branch

- `pytest tests/unit tests/integration` — 313 passed (3 pre-existing unrelated
  `test_creds_parse.py` failures from the missing local `.env-raw`).
- `test_calibrated_result.py` rewritten: 14 tests covering the new wording, the
  tendency clause, guidance-clause capping, per-item boundedness, corpus aggregation
  (modes + direction + item-independence), and a taxonomy-key-sync guard.
- `web`: `tsc -b` clean; vitest 103 passed.
- E2E **not** run in this exploration worktree: it launches the backend via
  `python -m vejudge.interface.server`, which resolves to the main checkout's editable
  install rather than this worktree's code, and bootstrapping a worktree `.venv` +
  Chromium is disproportionate for exploration. The `OPTIMIZED_PROMPT_MARKER` in
  `web/e2e/specs/cl-adversarial.spec.ts` was updated to the new confirmed-case wording;
  the marker + corpus-display assertions should be validated by the E2E suite if/when
  this graduates to a merge branch.

---

# Individual calibration + semantic decision tree (live experiment)

Second experiment (same branch): does *individual A/B calibration → post-aggregation into
a fitted semantic decision tree* beat a plain bias correction on the M5 batch? Pipeline
(`core/calibration/debate/eval/run_prompt_calibration.py`): per item, a fresh **mechanism
A/B debate** (proxy sees the human *direction + notes* but **never the number**; goal =
name the *general reusable rule* the judge misapplied) → extract candidate boolean rules →
canonicalize a shared **question bank** → the judge answers the bank **cold** (base score +
booleans, no debate/label) → fit `[base_score + booleans] → human` and report in-sample +
leave-one-out MAE. Live, 6 M5 items, ~40 text calls + 6 video, run against real Gemini.

## What worked: the mining + aggregation

The individual debates + canonicalization produced a genuinely good, general, reusable
decision-node bank (verbatim):

- **q1** — Does the judge penalize the output for failing to meet requirements **not stated
  or implied in the prompt**?
- **q2** — Does the judge **mistake a valid stylistic choice or genre convention for a
  flaw**, rather than evaluating the quality of its execution?
- **q3** — Does the judge **overstate the scope of a flaw**, applying criticism of isolated
  issues to the entire output?

These are exactly the transferable rubric principles the earlier per-item transcripts hinted
at, now phrased as item-agnostic yes/no checks. The mining half of the idea is validated.

## What broke: the judge won't self-flag cold

When the same judge answers those questions **cold about its own output**, it answers **"no"
to all three, on every item** — including `prj-aberdeen::2`, the textbook case where the
debate *proved* it mistook user-script-mandated repetition (q2) for a flaw. Verified on the
raw response: `{q1:False, q2:False, q3:False}`. So every semantic feature is 0 →
non-discriminative by construction.

## Result (MAE vs human; baseline = uncalibrated judge)

| comparator | in-sample | LOO |
|---|---|---|
| (a) base only | 2.06 | 2.06 |
| (b) base + global bias | 0.49 | 0.59 |
| (c) linear[base+booleans] | 0.35 | 0.52 |
| (d) tree[base+booleans] | 0.35 | 0.52 |

The big drop (2.06 → ~0.5) is **entirely the global bias term** — the judge systematically
under-scores by ~2 points, and correcting that is most of the available signal at n=6. The
(c)/(d) edge over (b) comes only from fitting a 2-parameter `base→human` map instead of a
1-parameter shift; the **semantic booleans add nothing here because they're all zero**. On
this batch the semantic decision tree did **not** beat a plain bias correction — not because
the rules are bad, but because the judge won't answer the questions truthfully about itself.

Fitted rule (auditable) collapsed to a base-score split: `base≤1.5 → 3.53`, `base>1.5 →
3.59` — i.e. "predict ~the human mean regardless," the degenerate outcome when features
carry no signal at n=6.

## Takeaway + next step

- **Mining/aggregation (individual A/B → shared rule bank): works.** The rules are the
  reusable, generalizable artifact the whole effort was after.
- **Hybrid self-answer execution: does not.** A judge asked "are you being unfair?" in the
  same breath as scoring says no. The boolean answerer must be **independent of the judge** —
  a separate critic/verifier pass that answers the bank about the output (or derives the
  feature from a debate/critic), so the features become discriminative. That is the clear
  next experiment; the mining pipeline built here feeds directly into it.
- **n=6 caveat stands**: even with good features, a fitted tree at this size is directional
  only; a larger labeled set (≤13 M5 peanut items available) is needed for a real read.

Reproduce: `python -m vejudge.core.calibration.debate.eval.run_prompt_calibration
logs/exps/260714-09:57:04-exps --metric M5 --env-raw <path> --live`.

---

# De-leak + corpus socket + `cl_rule_tree` node with an independent critic (live)

Third pass (same branch): (1) **de-leaked** the per-item `optimized_prompt` (general
failure-mode tendencies only — no target score, no item narrative), (2) exposed the
item-independent corpus prompt as a `general_calibration` socket wired into the Judge
node dataset-wide, and (3) built the **`cl_rule_tree` interface node** that mines rules
from an upstream `cl_adversarial` node's debates, has an **independent critic** (a
separate LM, not the judge) answer them, and fits `[base_score + rule booleans] -> human`,
reporting in-sample + LOO MAE.

## Live smoke (direct node run on the cached 17-item M5 run; 13 have an M5 anchor)

Text-only critic (gemini), ~35 text calls, reusing the cached debates (no re-debate):

**The critic fix works.** 7/13 items got ≥1 non-zero rule boolean — vs the earlier
cold-self-answer version where the *judge* denied all its own errors (0/N, all-zero
features). A separate auditor flags what the judge won't.

Mined rule bank (all general, item-agnostic):
- q1 — penalizing the model for correctly following instructions / source-inherited flaws
- q2 — disproportionately penalizing flaws while undervaluing success on the core objective
- q3 — applying standards inappropriate for the task/genre/constraints

MAE vs human (lower better):

| comparator | in-sample | LOO |
|---|---|---|
| (a) base only | 1.83 | 1.83 |
| (b) base + global bias | 0.46 | 0.50 |
| (c) linear[base+rules] | 0.27 | 0.47 |
| (d) tree[base+rules] | 0.27 | **0.41** |

**The tree beats a plain bias correction held-out** (LOO 0.41 vs 0.50) — the semantic
rules add real, if modest, out-of-sample signal, unlike the null result before the critic
fix. The fitted tree splits on q2 (over-penalization) + base_score. Honest caveats: most
of the 1.83→0.50 gain is still the global bias term (the judge systematically
under-scores); the rules add ~0.09 LOO on top. n=13 is directional, not conclusive, and
the critic is conservative — several high-gap items (aberdeen::2, paris-2025, qc::4) still
got all-zero booleans, so it misses errors too. A larger labeled set (and possibly a
video critic) is the next step before trusting the margin.

Repro: build a graph `Dataset → Judge → cl_adversarial → cl_rule_tree` (critic engine
distinct from the judge engine) and open the Rule/Tree Calibration node's secondary tab,
or run the node directly on a cached run's `calibration_results`.

# Ontology-weighted Semantic Tree vs CART (live)

Assembled `semantic_tree_calibration_peanut_M5` (Dataset → Judge → cl_adversarial →
cl_semantic_tree → cl_rule_eval) and ran the new `cl_semantic_tree` node **live** (gemini
text critic, ~28 calls: mine + canonicalize + concept-tag + critic) on the cached 17-item
M5 `cl_adversarial` run (260715-10:22:11), 13 with an M5 anchor. Upstream debates reused
from cache (not re-run) — the live calls exercise the new node's full path only.

Concept-labeled features assembled from the ontology:
- `fm:<concept>` counts (from the debate's cited failure modes): source_drift_blindness,
  overconfident_rationale, scale_drift, category_imbalance.
- `rule:<concept>` critic booleans (mined rules tagged to concepts): overconfident_rationale,
  surface_realism_bias. (One mined question tagged to no concept and was dropped.)

MAE vs human (lower = better), same features for tree/semantic:

| comparator | in-sample | LOO |
|---|---|---|
| base | 1.825 | 1.825 |
| base + bias | 0.459 | 0.497 |
| linear | 0.135 | 0.424 |
| tree (CART) | 0.135 | 0.336 |
| **semantic (ontology-weighted)** | 0.171 | **0.315** |

**The semantic tree beats CART held-out (LOO 0.315 vs 0.336), and both beat bias (0.497).**
Semantic is *worse* in-sample (0.171 vs 0.135) but *better* held-out — the ontology prior
regularizes rather than overfits, which is the intended effect. The fitted tree is
structurally semantic: it splits on `rule:overconfident_rationale` then
`fm:category_imbalance` (named concepts, not positional qN).

Honest caveats: n=13, so the 0.315-vs-0.336 margin is directional, not conclusive; the bias
term still closes most of the 1.825→~0.5 gap, with the trees adding ~0.16-0.18 LOO on top.
The full workflow's `cl_adversarial` stage was reused from cache (a from-scratch live run
would re-debate all items). Next: larger labeled set / other metrics for a less-noisy margin.

# VE-Bench judge baseline — human-alignment vs the paper (live)

Brought the public **VE-Bench DB** into the system as a separate calibration track
(`dl_vebench` loader + `vebench_source` node + `edit_quality` MOS labels materialized as
per-item humaneval JSON; appearance/content editing, not peanut assembly). Stood up a
**VE-Bench judge framework** — a custom video judge (Judge Prompt `preset=custom`, 1–10
edit-quality) → Judge node → Eval node reporting SROCC/PLCC/KRCC vs the human MOS — as a
baseline/comparison point, and ran it live on a **120-item subset** (gemini-2.5-pro,
temp 0).

Paper (VE-Bench, MOS 1–10, 24 raters, 8 editing methods, 1170 edits):

| method | SROCC | PLCC |
|---|---|---|
| CLIP-F (zero-shot) | 0.228 | 0.186 |
| PickScore (zero-shot) | 0.227 | 0.245 |
| DOVER (VQA) | 0.612 | 0.630 |
| FastVQA (VQA) | 0.633 | 0.633 |
| StableVQA (VQA) | 0.689 | 0.678 |
| **VE-Bench QA (trained on this data)** | **0.742** | **0.733** |

Our zero-shot VLM judge on the 120-item subset:

| judge variant | SROCC | PLCC | KRCC |
|---|---|---|---|
| edited video only (v1) | 0.365 | 0.367 | 0.263 |
| **source + edited video (v2)** | **0.545** | **0.508** | **0.415** |

Read: showing the **source** alongside the edited video (the principled fix — VE-Bench
raters compared edit-vs-source) lifts SROCC 0.365 → 0.545. Our zero-shot judge clearly
**beats the paper's zero-shot metrics** (CLIP-F/PickScore ~0.23) and **approaches the
specialized VQA models** (DOVER 0.61), while trailing the trained VE-Bench QA (0.742) — a
model fit on this exact data. That is the expected, honest position for a zero-shot
LLM-judge baseline, and it gives a real comparison point on an external human-scored set.
Framework changes: `run_custom_judge` now attaches a `source_video_path` before the edited
video when present (no-op for peanut); Eval reports PLCC (Pearson) alongside SROCC.

Caveats: n=120 subset (not the full 1170); VE-Bench ships only an aggregated MOS (no
per-rater), so no inter-rater ceiling; a single overall 1–10 score (VE-Bench QA uses a
richer multi-branch model). Closing the last gap to 0.742 would mean training/calibrating a
metric, not a zero-shot prompt — which is where the adversarial-calibration + semantic-tree
work would come in as the next step on this dataset.
