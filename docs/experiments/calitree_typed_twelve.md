# Twelve-case typed evidence optimization

## Latest result: completed

The second authorized continuation, `logs/exps/261008-typed-twelve-resumed-v2`, completed all twelve case outcomes and reserved final verification. Ten cases had executable common seeds; DVD and cylinder-color compilation failed and remain recorded failures in both arms. All 24 selections froze before any final draw. Final observations did not reopen optimization.

| Method | Seed → selected reference matches / 60 scheduled final draws | Selected resolved draws / 60 | Verified locally robust leaves |
|---|---:|---:|---:|
| Criterion-only | 17 → 31 | 47 | 4 |
| Nested-required | 16 → 24 | 39 | 0 |

Each case has five final draws per program and method. The full denominator retains invalid seeds as failures. These are local fitting measurements on previously observed data; repeated draws do not increase the number of independent cases. The four robust criterion-only leaves are pencil drawing, paper-into-cup, comic style and chalk drawing. The helmet candidate passed confirmation but failed fresh final coverage. Some selected candidates regressed relative to their seeds, so this is not a universal improvement.

Nested comic and chalk each matched the reference in 5/5 fresh final draws. Each had one failed confirmation call, giving only 4/5 confirmation coverage and missing confidence. They therefore remain unconfirmed under the frozen policy; final success cannot replace failed confirmation or trigger another repair. Other nested scopes retained seed fallbacks without an eligible added check or failed agreement/coverage/audit gates.

The earlier seven repeated nested-mug proposal slots remain an explicit protocol deviation. Its charges are retained and that scope is excluded from valid robustness/fair-comparison claims. Excluding the affected mug case from **both** methods yields an eleven-case paired subset: criterion-only 17 → 31 matches out of 55; nested-required 16 → 24 out of 55. This subset is no longer class-balanced. The raw twelve-case rows remain available for transparency.

Combined usage across the original attempt and both continuations: **2,364 calls**, **420,200 charged completion tokens**, **306,536 provider-reported completion tokens**, and **7,288,931 input tokens**. There were 2,292 completed requests and 72 transport failures. Search/preparation used 1,757 calls; fresh final verification used 607. The final continuation added 951 calls to its inherited 1,413. All usage remains within 3,600 calls / 4,608,000 completion tokens; inherited ledgers must not be counted twice. TLS diagnostic probes made no model calls.

Source/image/program hashes, label and media isolation, deterministic edit replay, original requirement preservation, final-after-freeze ordering, monotonic inherited accounting and zero-call replay all passed. The repaired continuation repeated **no** inherited logical slots and preserved all prior frozen selections. Offline checks before execution: 1,276 passed, 23 skipped. Code, staging and experiment history remain uncommitted; no push was made.

Readable per-case results, confidence, checks, failure reasons and cost are in `logs/exps/261008-typed-twelve-resumed-v2/comparison_report.md`. Reproduce the saved-data analysis without contacting a provider:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-twelve-resumed-v2/analyze_continuation.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-twelve-resumed-v2/write_comparison_report.py
```

`replay_frozen_analysis.py` restores the original scoring runtime if repository code changes. The following sections retain the interrupted attempts and their diagnostics as historical records.

## Protocol

Run directory: `logs/exps/261008-typed-twelve-v2`. The frozen manifest reuses the exact twelve previously observed AURORA cases from `261006-optimizer-comparison-v1`: four `yes`, four `partial`, four `no`, with distinct source-pixel groups and verified image hashes. This is local fitting, not held-out evaluation.

Each case receives one fresh label-free seed containing exactly two support checks and one fulfillment readout. Criterion-only and nested-required share that seed and its fresh semantic audit, but have independent observations and optimization histories. The legacy v2 program is explicitly bridged to a v3 compilation reference with the same immutable requirement ledger, instruction, rubric and requested outcome. Saved legacy inference is not reinterpreted.

Both greedy arms allow up to fifteen repair rounds and two proposed transactions per round. Their 109-call search allowances can end search sooner. The nested arm requires an inserted check with ancestor evidence context to qualify. Five confirmation draws are provisional; five fresh final seed and selected executions are reserved separately. Every selection must freeze before any final execution.

Model: GPT-6 Luna at the official OpenAI endpoint, temperature zero, reasoning `none`; returned identity `gpt-6-luna`. Global limits are 3,600 calls and 4,608,000 completion tokens. Reserve 960 final calls / 983,040 completion tokens. Two independent cases can make concurrent HTTP calls through one serialized durable accounting ledger; native TextGrad backward calls remain serialized.

## Interrupted live attempt

The attempt stopped after three consecutive TLS transport failures at 684 calls. The final errors were `SSLV3_ALERT_BAD_RECORD_MAC` during nested confirmation. These are failed requests, not visual evidence. The failure latch remains set. No failed slot is retried, and no provider substitution is permitted.

- Six cases reached seed preparation. Five compiled valid seeds; the DVD case was rejected because a support question duplicated the fulfillment question.
- Nine of 24 case-arm scopes have frozen outcomes: seven saved optimization results and the DVD's two recorded preparation failures.
- Two criterion-only selections passed all confirmation gates: pencil drawing and helmet. Neither has fresh final verification.
- No final calls have occurred. Final agreement, coverage and local robustness are **unmeasured**, not zero accuracy.
- 659 requests completed; 25 encountered transport failures. Completion-token accounting charges 133,385 tokens, including reserved charges for failures; provider-reported completion tokens total 96,521. Input tokens total 2,055,093.

| Case | Arm | Completed rounds | Search outcome |
|---|---|---:|---|
| White DVD | Both | — | Invalid seed; no semantic feedback fabricated |
| Closed jacket | Criterion-only | 7 | Search allowance exhausted during round 8 |
| Closed jacket | Nested-required | 15 | Round limit; no qualifying selection |
| Pencil drawing | Criterion-only | 2 | Confirmation qualified; final pending |
| Pencil drawing | Nested-required | 10 | Search allowance exhausted during round 11 |
| Helmet | Criterion-only | 4 | Confirmation qualified; final pending |
| Helmet | Nested-required | 15 | Round limit; no qualifying selection |
| Basketball court | Criterion-only | 6 | Search allowance exhausted during round 7 |
| Basketball court | Nested-required | — | Interrupted before selection froze |
| Mug position | Both | — | Interrupted/unattempted scopes |
| Remaining six cases | Both | — | Unattempted |

The seed compilation error is a separate failure from scoring mismatch or instability. The final-provider stop is a separate failure from unsuccessful optimization. The raw runner `report.md` retains provisional zero placeholders; use `analysis.md` for the corrected interpretation of pending final measurements.

## Reproducibility and verification

The directory retains its exact manifest, code/template snapshots, jobs, per-check observations, constructions, preparations and frozen leaves. `component_analysis.json`, `usage_summary.json`, `class_metrics.json` and `protocol_verification.json` are derived using saved data only. `analysis.md` shows pending final measurements explicitly. Run the saved-data analysis from the repository root:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-twelve-v2/analyze_saved_run.py
```

`replay_frozen_analysis.py` restores the pinned sources when repository code changes. Analysis verifies program/source/image hashes, original coverage, typed transaction replay, label isolation, media/dependency contracts, budgets and actual round counts. Completed full-experiment zero-call replay is unavailable because the live experiment is interrupted.

Before live execution, focused typed suites passed 35 tests. The full offline unit suite passed 1,272 tests with 23 skips. A transport continuation requires explicit authorization after the stop; it must retain failed slots, charges, existing frozen selections, configuration and final reservations.

## Authorized continuation: second transport stop

Following the user's request to resume, `logs/exps/261008-typed-twelve-resumed-v1` inherited the full durable state and released one transport-stop latch. The exact saved optimizer, templates, program references, model and limits were retained; existing frozen selections were not reopened. New calls proceeded only after replay tests and source/image/dependency preflight. The offline unit suite ultimately passed 1,276 tests with 23 skips.

The continuation stopped again after three consecutive TLS failures at **1,413 combined calls**, including **729 additional calls**. Ten cases reached preparation and **17 of 24 case-arm outcomes froze**. No final draws occurred. The original stop and continuation stop both remain preserved; final agreement, coverage and robustness remain unmeasured.

Four criterion-only selections passed confirmation: pencil drawing (round 2), helmet (round 4), paper-into-cup (round 2), and comic style (round 1). They are provisional. The comic nested arm and chalk nested arm were interrupted before their selections froze. Frog and cylinder-color fitting are still unattempted.

Combined usage: 1,364 completed requests and 49 transport failures; 293,366 charged completion tokens, 214,518 provider-reported completion tokens, and 4,715,746 input tokens. The remaining allowance is 2,187 calls and 4,314,634 charged completion tokens. All 960 final-call reservations are still intact.

### Recorded replay deviation

During resume, a retained transport-error slot raised a different diagnostic string from its original attempt. That changed downstream proposer payload hashes. Seven nested-mug proposal rounds (indices 2–8) were consequently requested again. No failed execution key was retried, but the promise to run only unattempted logical work was violated for this scope. These calls and their consequences remain charged; no accounting or saved result was rolled back. The affected nested-mug scope is excluded from valid robustness claims and fair method comparisons. Its saved measurements remain available for inspection.

`protocol_deviations.json` lists the original/new request references. `continuation_verification.json` independently verifies immutable inherited jobs and selections, observation prefixes, monotonic accounting and unchanged limits, while explicitly marking `unattempted_work_only: false`. This deviation must not be hidden behind the fact that payload-dependent durable keys were unique.

The continuation driver now replays the original transport/invalid-response diagnostic without contacting the provider. A regression test verifies that the downstream proposal is loaded from its existing slot, with zero extra calls. Future continuations also pin the driver in `continuation_snapshot/` and record its hash and replay protocol separately from the unchanged scoring manifest. This repair changes replay bookkeeping, not visual criteria, selection thresholds or reference labels. It cannot retroactively repair the affected scope.

Saved-data verification:

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-typed-twelve-resumed-v1/analyze_continuation.py
```

The script makes no API calls. The original interrupted attempt remains unchanged. Another release of the transport stop requires explicit continuation authorization; invoking the same stopped continuation does not automatically reset it.
