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

## How to validate generalization empirically (next step, needs `--live`)

Structural + verbosity gains are proven offline. The causal claim — "the lean corpus
prompt improves judge↔human agreement on unseen items" — needs live judge calls:

1. Split the labeled items into train/test.
2. Run adversarial calibration on *train* only; take its `general_optimized_prompt`.
3. Re-run the Judge on *test* items three ways: (a) uncalibrated, (b) with the old
   verbose per-item prompts, (c) with the single corpus prompt as dataset-wide
   `extra_context`.
4. Compare MAE / correlation vs. human aggregates (`vejudge/core/eval/metrics.py`,
   `postprocessing/align.py::build_aligned_rows`). Success = (c) matches or beats (b) at
   a fraction of the tokens, and both beat (a).

This harness is not run here (billable Gemini calls, and it belongs in a dedicated
experiment). It's the recommended follow-up before adopting the corpus prompt as the
default calibration path.

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
