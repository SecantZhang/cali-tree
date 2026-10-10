# Flat counting leaf experiment

Artifacts: [frozen manifest](../../logs/exps/261009-counting-leaf-v5/manifest.json),
[detailed report](../../logs/exps/261009-counting-leaf-v5/report.md).

## Protocol

The experiment uses the exact original twelve previously observed AURORA cases: four per reference class, with verified
image hashes and distinct source-pixel groups. Each case is fitted independently; repeated executions are measurements
within cases, not additional examples or a held-out generalization test.

One label-free compiler call creates a flat seed with one to four independent required-condition decisions. Both arms
share that program, with independent fresh observations and optimization histories. All conditions run independently.
There are **zero semantic audit calls and zero model-based readout calls**. Code computes all pass → satisfied, all fail
→ unsatisfied, known mixture → partial. Any unknown, invalid or failed observation leaves the result unresolved.

Luna-only and Luna→Sol use the same thresholds and proposal allowances. The adaptive proposer switches permanently
after three completed stalled rounds. Image checks, native TextGrad feedback and visual discovery remain on GPT-6 Luna;
only proposals may use GPT-6.1 Sol with medium reasoning. Calls use official OpenAI, one HTTP attempt, with no model
substitution or automatic schema repair. Existing confidence/consistency/fresh-repeat gates govern empirical robust status,
without implying semantic approval of the decomposition.

Search allows fifteen rounds and two transactions per round, subject to 109 search calls per case-arm. Final verification
uses five fresh executions each of seed and selected programs after all 24 selections freeze. Forty final calls per arm
and 960 final calls / 983,040 completion tokens globally are reserved before search. Total ceilings are 3,600 calls and
4,608,000 completion tokens; every failed or interrupted attempt remains charged. Final results cannot retune selection.

## Verification

The full offline suite passed before this run: **1,352 tests passed, 23 skipped**. The counting-focused suite passed all
42 tests immediately before live execution. Tests cover all/some/none and unknown combinations, absence of auditor/readout
calls, independent execution after failures, immutable provenance/coverage, fresh slots, exact reload and zero-call replay.

The saved-data verifier checked each final label against the observed count and verified request isolation, identical case
identities, budget accounting, deterministic escalation and frozen selections. Current-source and pinned-source replays
both passed with model calls forbidden, preserving results and accounting. All 24 selections froze before final execution;
no logical slot was repeated. There were no auditor or model readout calls.

Reproduce without API calls:

```sh
.venv/bin/python logs/exps/261009-counting-leaf-v5/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-counting-leaf-v5/replay_frozen_analysis.py
```

## Results

Completed all twelve cases and both arms. Accuracy below counts reference matches across **60 final runs per arm**
(twelve cases × five repeats); unresolved predictions count as incorrect. Coverage counts resolved predictions,
including incorrect ones. Locally robust status requires qualifying search confirmation and fresh final verification.

| Method | Seed accuracy | Optimized accuracy | Optimized coverage | Locally robust leaves |
|---|---:|---:|---:|---:|
| Luna-only | 28/60 (46.7%) | 44/60 (73.3%) | 59/60 (98.3%) | 8/12 |
| Luna→Sol proposer | 28/60 (46.7%) | 36/60 (60.0%) | 60/60 (100%) | 6/12 |

Each arm changed three selected programs. Six adaptive cases escalated to Sol. Class-specific optimized matches were
15/20 satisfied, 9/20 partial and 20/20 unsatisfied for Luna-only; 15/20, 6/20 and 15/20 respectively for adaptive.

- **DVD:** Luna-only replaced its two-condition seed with a source-relative transformation question. Seed predictions
  were satisfied in 5/5; selected predictions were unsatisfied in 5/5, matching the reference. Adaptive retained the seed
  and remained wrong in 5/5.
- **Chalk:** Luna-only split the broad check into complete conversion and meaningful progress questions. Complete failed
  and progress passed in 5/5, yielding partial in 5/5. Adaptive used chalk medium and drawn representation conditions;
  selected predictions were unsatisfied in 4/5 and partial in 1/5, failing acceptance.
- **Pencil:** Adaptive selected predictions matched partial in 5/5 final runs, but search confirmation was unqualified.
  It remains unconfirmed rather than locally robust.
- **Frog:** Luna-only matched partial in 4/5, with one unresolved execution and failed confidence gate; it is not robust.
- **Jacket:** Both arms remained consistently wrong in 5/5. Counting and removing audits did not resolve this case.

Usage: **1,204 calls / 181,938 charged completion tokens**, including failed-attempt allowances. There were 924
preparation/search calls and 280 final calls; 1,141 Luna calls and 63 Sol proposal calls. Returned identities were
`gpt-6-luna` and `gpt-6.1-sol`. Fifteen TLS failures (thirteen search, two final) were retained without retries; no
consecutive-failure stop occurred. All twelve cases compiled structurally valid seeds.

## Interpretation

The reference labels are unchanged. Counting defines partial as a mixture of satisfied and unsatisfied required conditions,
which can differ from the previous model's judgment of editing progress. This run changes decomposition, execution view,
auditing and final aggregation together. Historical v4 comparisons are descriptive, not an isolated audit ablation.
Simple deterministic aggregation does not certify that model-proposed conditions are necessary, sufficient or correctly
observed. Confidence is self-report. No cross-case generalization or atomic semantic correctness is established.

Only one seed had two conditions; eleven had one broad condition. A single binary condition cannot produce partial
under all/some/none counting, and both arms scored 0/20 on the partial-class seed runs. This experiment therefore tests
structural splitting during optimization; it does not establish the advantage of initially forced decomposition.

The chalk improvement also exposes semantic drift: its selected “any meaningful progress” question is broader than an
endpoint condition, despite the proposal template's restriction on progress helpers. Structural validation preserved the
requirement ledger but did not enforce that semantic restriction. With auditing intentionally disabled, the reported
eight/six robust leaves certify local empirical gates only. They do not certify that every selected question implements
the intended independent required-condition design. Some seed-to-selected gains also occurred with an unchanged program
(for example Luna-only cylinder 3/5 → 5/5), so those gains cannot be attributed to a structural repair.
