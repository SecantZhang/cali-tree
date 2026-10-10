# Endpoint counting repairs on the original twelve cases

Artifacts: [manifest](../../logs/exps/261009-counting-endpoints-v6/manifest.json),
[detailed report](../../logs/exps/261009-counting-endpoints-v6/report.md).

## Frozen protocol

The exact twelve previously observed AURORA cases are local fitting problems; all labels guide their own leaf only.
Image hashes, source groups and identities match the original manifest. Luna-only and Luna→Sol share a fresh label-free
v6 seed and have independent search histories/observations. No historical feedback is reused and no semantic audit or
model-based readout runs. Code counts required-condition observations: all pass yes, all fail no, mixed partial,
unknown unresolved. Missing evidence is never a negative vote.

The compiler prefers two or three distinct visual endpoint aspects, each with an exact requirement/rubric quote and
necessity explanation. Irreducible single conditions are allowed, with the partial-representation limitation reported.
Explicit progress/attempt questions and duplicate aspects fail validation. Repairs predict actual visual observations;
screen outcomes and missed predictions return in subsequent feedback. Source comparisons are emphasized. This does not
provide a semantic proof or automatically resolve annotation disagreements.

Search has fifteen rounds, at most two transactions per round, Luna-first and optional permanent Sol escalation after
three completed stalls. Only matching resolved screens receive five fresh confirmation draws. Qualification requires
five matching labels, five resolved draws, confidence at least .8 and condition/requirement consistency at least .8.
All twenty-four selections freeze before five fresh seed and five selected final draws. Final outcomes cannot retune
selection or trigger replacement candidates.

Each report allows at most one transport-only replacement CHECK in a new durable slot, chosen as the first failure in
execution order without considering labels. Other observations remain exact. Valid wrong/uncertain answers, schema
failures and interrupted attempts are never replaced. Raw and effective measurements and both attempts remain saved;
recovered results still have five draws, not six independent cases. Each HTTP slot has one attempt, no schema repair;
provider rejection or three consecutive transport failures stops the run without substitution or automatic release.

Official OpenAI: GPT-6 Luna temperature zero/reasoning none; only adaptive proposals use GPT-6.1 Sol medium reasoning
with temperature omitted. Ceilings: 3,600 calls / 4,608,000 completion tokens. Per case-arm 107 search / 42 final calls.
Reserve 1,008 final calls / 1,032,192 tokens. Shared preparation one call per case; planned maximum 3,588 calls.
Checker cap 1,024; compiler/gradient/discovery cap 2,048; proposer cap 4,096; at most 144 Sol proposal calls.

## Verification and results

Completed all twelve cases and both arms. **1,368 offline tests passed, 23 skipped** before live execution. Both the
current-source and pinned-source replays passed with API calls forbidden, preserving all results and accounting. The
verifier checks immutable requirements, exact images/source groups, label isolation, all selections frozen before final,
unique durable slots, counting parity, raw/effective recovery selection, unchanged sibling observations and both-attempt
charges. There were no audit or model-readout calls. Invalid programs and failures were not replaced with new cases.

The main metric is the fraction of twelve selected cases matching the reference in **all five** final pipeline runs.
The prior column uses the completed v5 scheduled final runs, which did not permit transport replacement. The raw v6
column likewise excludes recovery; the effective column includes the predeclared one-check recovery policy.

| Method | Prior v5 accurate/repeatable | V6 raw accurate/repeatable | V6 effective accurate/repeatable | Effective draw accuracy | Effective coverage |
|---|---:|---:|---:|---:|---:|
| Luna-only | 8/12 (66.7%) | 7/12 (58.3%) | 8/12 (66.7%) | 52/60 (86.7%) | 58/60 (96.7%) |
| Luna→Sol | 7/12 (58.3%) | 5/12 (41.7%) | 6/12 (50.0%) | 42/60 (70.0%) | 58/60 (96.7%) |

Effective seed agreement was 29/60 and 30/60 respectively. Both methods improved draw agreement from their fresh seeds,
and from historical selected v5 scores (44/60 and 36/60), but **the accurate-and-repeatable case ratio did not improve**.
Strict locally robust counts were eight and six. Six Luna-only selections changed, four adaptive selections changed;
four adaptive cases escalated. Seeds contained nine single conditions and three two-condition decompositions.

## Actual improvements and remaining failures

- **Pencil:** the seed distinguishes pencil contours from pencil shading, enabling partial without a progress helper.
  Luna-only matched all five final draws after recovering one TLS failure. Adaptive matched four, with one remaining
  transport failure after recovering the first of two primary failures. No valid wrong answer was replaced.
- **Mug:** both methods repaired the single-condition seed and matched partial in 5/5 final runs. Adaptive separates
  source-mug relocation from the requested right-of-headphones arrangement. Luna-only uses three conditions.
- **Comic:** both methods repaired the seed and matched unsatisfied in 5/5 final runs.
- **Chalk:** both found programs matching partial in 5/5 confirmation runs without explicit progress questions. Their
  final reports each had two TLS failures; one was recovered and one remained unresolved. Each matched 4/5, not 5/5.
- **Frog:** Luna-only qualified a four-condition program, then had two final TLS failures; recovery restored one, leaving
  4/5 matching and one unresolved. Adaptive retained its broad seed and predicted satisfied in 5/5 against partial.
- **Court:** both methods predicted satisfied in 4/5 and unsatisfied once. These were valid model predictions, not
  infrastructure failures, and were not resampled. Luna-only had previously qualified in confirmation.
- **Jacket:** both methods remained consistently wrong in 5/5. Adaptive DVD also remained wrong in 5/5.

Every remaining unknown in selected effective final reports was a transport failure, not valid visual uncertainty.
The one-recovery-per-report ceiling left four selected case-arms unresolved. This is a declared limit, not evidence
that a second replacement would necessarily have produced the correct answer. Earlier confirmation does not override
fresh final failures. Final outcomes never reopened search or selected a different candidate.

## Usage and replay

**1,077 calls / 146,232 charged completion tokens**: 720 preparation/search and 357 final calls, including seven
successful final recovery calls. There were 1,032 Luna calls and 45 Sol proposal calls; returned identities were
`gpt-6-luna` and `gpt-6.1-sol`. Thirty TLS failures (nineteen search, eleven final) remained charged. The three-consecutive
failure stop did not trigger. All 24 selections froze at call 720 before any final draw.

```sh
.venv/bin/python logs/exps/261009-counting-endpoints-v6/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-counting-endpoints-v6/replay_frozen_analysis.py
```

## Limits

Exact quotes and distinct aspect names are structural guards, not semantic proofs. Explicit progress questions are
rejected, but free-form endpoints can still introduce unsupported interpretations or poorly aligned question polarity.
For example, the Luna-only frog selection includes a no-extra-frogs condition, and the Luna-only mug selection asks
whether the original mug remains at its source position; the saved endpoint/criteria define how that fact maps to
pass/fail. These require human semantic review before claiming they are independently necessary scoring components.
No semantic auditor was silently reintroduced. Confidence is self-report and repeated reference agreement does not
certify component truth, calibration or cross-case generalization.

Historical v5 used a different compiler, feedback, confirmation scheduling and recovery protocol. Its Luna-only ratio
was 8/12 and adaptive 7/12 for five-out-of-five final agreement. A comparison measures the combined v6 corrections;
it does not isolate any single correction or establish generalization/atomic correctness. Matching labels alone does
not certify model-proposed endpoint semantics.
