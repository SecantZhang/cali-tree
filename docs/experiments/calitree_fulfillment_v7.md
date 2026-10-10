# Weighted fulfillment versus binary aggregation

[Complete report with all twelve cases, selected questions/anchors, scores, confidence, search effort and failure analysis](calitree_fulfillment_v7_complete_report.md).

Artifacts: [manifest](../../logs/exps/261009-fulfillment-v7/manifest.json),
[report](../../logs/exps/261009-fulfillment-v7/report.md).

## Protocol

Same twelve previously observed AURORA cases, four per reference class, exact frozen identities/image hashes and distinct
source groups. Each is a local fitting problem. One fresh label-free compiler call creates a common anchored decomposition.
Two independent Luna-only arms use binary and fulfillment views; the shared seed's conditions, anchors and weight ledger
are identical, with only saved scoring mode different. No historical observations/feedback reused, no semantic audits,
no model-based final readout and no Sol calls.

The observer returns degree of fulfillment and confidence separately using explicit 0/.5/1 evidence anchors. It receives
no label, feedback, mode, aggregation thresholds or weights. Binary defines full endpoint achievement as score 1 and
uses all/some/none; fulfillment uses the protected weighted average with >=.9 satisfied, <=.1 nonsatisfied, otherwise
partial. Unknown scores are [0,1]; resolve only if the entire score range belongs to one label band. Every trace records
both same-observation labels for a computational aggregation comparison. The historical v6 Boolean observer used a
different prompt, so the fresh binary arm is not a literal reproduction of that model judgment.

Code fixes equal requirement budgets and initial facet shares. Splits divide a parent's share equally and preserve its
root; auxiliaries get zero; positive mass cannot be deleted or transferred across roots. Models cannot change weights,
thresholds or scoring mode. Criterion/anchor/binding refinements retain the requested endpoint. Four checks maximum.
These invariants prevent vote-count manipulation but do not prove semantic preservation or calibrate subjective grading.

Fifteen repair rounds, two transactions per round maximum. Screen once and confirm resolved matching candidates with
five fresh draws; qualification requires 5/5 agreement/coverage, confidence >=.8, consistency >=.8 and three eligible
observations. One transport-only recovery check per report in a distinct durable slot; preserve raw results and charges.
Valid wrong/uncertain/schema-invalid/interrupted observations are not resampled. All 24 selections freeze before five
fresh seed and five selected final draws. Final outcomes cannot retune candidates or weights.

Official OpenAI GPT-6 Luna, temperature zero/reasoning none. One HTTP attempt per slot, no substitution/schema repair,
stop on provider rejection or three consecutive transport failures. Ceilings 3,600 calls / 4,608,000 completion tokens;
107 search / 42 final per scope, 1,008 final calls / 1,032,192 tokens reserved. Compiler/gradient/discovery cap 2,048,
checker 1,024, proposer 4,096. Repeat measurements are not new cases and there is no generalization claim.

## Verification and results

Before live: **1,390 offline unit tests passed, 23 skipped**; 22 focused fulfillment tests passed. Pixel-grounded offline
demo verifies .5 fulfillment -> partial and .95 -> satisfied without model calls, while strict binary returns no for
both incomplete endpoints. Tests cover exact boundaries, unknown intervals/applicability, protected mass, zero-weight
helpers, immutable edits, exact save/load, confidence separation, label isolation, durable recovery and zero-call replay.

The initial live run **stopped after 188 calls / 51,046 charged completion tokens** at three consecutive TLS BAD_RECORD_MAC
failures. There were 180 completed calls and eight retained transport failures. Three cases compiled; four case-arm
selections froze (both DVD and jacket arms). Binary pencil search was interrupted; the fulfillment pencil arm and later
cases had not run. There were zero final-verification draws. Final accuracy and the all-five-correct case ratio
were then **unmeasured**, not zero. Search confirmation is not a substitute for the reserved fresh comparison. The user
subsequently explicitly authorized continuation; the same frozen experiment completed, as recorded below.

Both current-source and pinned-source zero-call replays passed for the partial run, preserving results, budgets and
interruption history. Verifier checked exact score arithmetic and unknown bounds, protected mass, shared-seed parity,
observer label/mode/weight isolation, immutable requirements, unique slots and retained recovery records. No audit or
model-readout calls occurred, and no stop latch was automatically released.

The final three failures were an image-bearing gradient, proposal and discovery call in the binary pencil search.
They are transport failures rather than failures of the weighted arithmetic. Prior [TLS diagnostics](calitree_tls_diagnostics.md)
reproduced BAD_RECORD_MAC on unauthenticated synthetic large uploads, with no confirmed root cause or consistently
successful client/TLS-version mitigation. This experiment did not change network settings or certificate verification.

The explicitly authorized continuation used this command with the same frozen settings and retained all failed charges:

```sh
.venv/bin/python -m run.calitree_adaptive_leaf --resume --live --release-transport-stop --output-dir logs/exps/261009-fulfillment-v7
```

## Completed results after authorized continuation

Completed all twelve cases and both arms, retaining the initial failures and charges. All 24 selections froze at call
580 before any final draw. Every case has five fresh seed and five fresh selected pipeline executions per arm. Unresolved
draws count as incorrect. Raw results precede the declared transport recovery; effective results include it.

| Scoring arm | Seed matches | Selected matches / accuracy | Selected coverage | Raw all-five-correct cases | Effective all-five-correct cases | Strict locally robust |
|---|---:|---:|---:|---:|---:|---:|
| Binary, strict fully complete votes | 27/60 | 35/60 (58.3%) | 60/60 | 5/12 (41.7%) | 7/12 (58.3%) | 7/12 |
| Weighted fulfillment, .9/.1 bands | 30/60 | 48/60 (80.0%) | 59/60 | 6/12 (50.0%) | 8/12 (66.7%) | 8/12 |

Weighted fulfillment gained **13 correct draws / 21.7 percentage points** over this fresh binary arm, and one additional
all-five-correct case. The entire draw-accuracy difference was on partial-reference cases: binary **0/20**, fulfillment
**13/20**. Both scored 15/20 on satisfied and 20/20 on nonsatisfied. Two binary selected programs changed, four fulfillment
programs changed. Ten seeds had one condition and two had two conditions; this is not forced-decomposition evidence.

| Partial-reference case | Binary final matches | Fulfillment final matches | Fulfillment final scores / reason |
|---|---:|---:|---|
| Pencil drawing | 0/5 | 4/5 | .85, .65, 1, .75, .85; the 1 estimate produced satisfied |
| Mug right of headphones | 0/5 | 5/5 | .5 in all five runs |
| Chalk drawing | 0/5 | 4/5 | .85 in four runs; one transport failure whose recovery also failed |
| Frog in toilet | 0/5 | 0/5 | 1 in all five runs, predicting satisfied |

The mug case demonstrates stable intermediate fulfillment directly: a single selected condition repeatedly scored .5
and returned partial. The binary mug program repeatedly scored 1 and returned satisfied, showing that independent
optimization also changed the grader's bindings/anchors. Both jacket arms repeatedly scored 0 and predicted nonsatisfied
against a satisfied reference. Neither a softer aggregate nor this local search resolved that disagreement.

## Same-observation aggregation checks

Every final draw also records the other deterministic readout on the exact same scores:

| Selected program family and observations | Binary readout matches | Fulfillment readout matches |
|---|---:|---:|
| Binary-optimized programs | 35/60 | 34/60 |
| Fulfillment-optimized programs | 35/60 | 48/60 |

Switching the readout alone on binary-optimized programs did not improve accuracy. Their DVD mean .25 and comic means
.175–.275 were accepted as nonsatisfied by strict all-failed votes, but became partial under fulfillment. Fulfillment
optimization instead produced zero scores for these nonsatisfied cases while preserving intermediate scores for genuine
partial predictions. Thus the measured gain depends on scoring-aware optimization, not universally on softer thresholds.

## Historical comparison and limits

The preceding v6 Luna-only experiment achieved **52/60 (86.7%)** selected draw accuracy and 8/12 all-five-correct cases.
V7 fulfillment's **80.0%** did **not** exceed that historical draw accuracy, and its case ratio was unchanged at 8/12.
The prior Boolean observer and programs differ from this common graded observer; the comparison is descriptive. The
fresh pair supports a gain over strict binary aggregation under the anchored grader, not a claim of beating the previous
best implementation or proving generalization/atomic truth. Model-estimated degree is subjective; anchors, literal quotes
and conserved mass do not calibrate it or certify every criterion.

## Completed usage and reproducibility

**867 total calls / 160,478 charged completion tokens**, including the original 188 attempts: 580 preparation/search
and 287 final calls. All calls used returned identity `gpt-6-luna`; no Sol calls, audit calls or model readouts. There
were 845 completed attempts and 22 TLS failures (14 search, eight final). Seven final recovery slots included six
successful calls and one TLS failure. No valid wrong or uncertain answer was resampled. The remaining chalk score was
unknown [0,1], never zero. One explicitly authorized stop release occurred; there was no automatic continuation.

Both final current-source and pinned-source replays passed with model calls forbidden. Verification independently
recomputed exact rational weighted bounds and both label functions, checked protected root mass, common seed parity,
label/mode/weight isolation, image/source identities, final freeze, unique durable slots and raw/effective recovery costs.
It preserved all results and accounting. No final outcomes retuned candidates, thresholds or weights.

```sh
.venv/bin/python logs/exps/261009-fulfillment-v7/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-fulfillment-v7/replay_frozen_analysis.py
```
