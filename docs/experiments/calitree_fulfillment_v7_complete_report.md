# Complete report: CaliTree weighted fulfillment experiment

Experiment: `261009-fulfillment-v7`. Status: **completed after an explicitly authorized continuation**.

## 1. Decision-relevant findings

Weighted fulfillment achieved **48/60 correct final runs (80.0%)**, versus **35/60 (58.3%)** for this experiment's strict binary readout: **+21.7 percentage points**. All-five-correct cases improved from **7/12 to 8/12**. The entire draw-accuracy gain was on partial-reference cases.

These results support graded scoring under this shared observer, but **do not establish a new best optimizer**. The preceding v6 Luna-only experiment scored **52/60 (86.7%)**, and also had eight all-five-correct cases. Its Boolean observer differed. Switching thresholds alone on binary-optimized v7 programs actually changed accuracy from **35/60 to 34/60**; the improvement required criteria/anchors adapted to fulfillment scoring.

This remains local fitting on twelve previously observed cases. It establishes neither cross-case generalization nor correctness of each atomic judgment. Ten seeds and most selected programs contain one broad condition; the result is **not evidence that a decomposed prompt tree outperforms a broad judge**.

## 2. What was tested

The exact prior twelve AURORA cases were reused: four satisfied, four partial, four nonsatisfied, with distinct source-pixel groups and verified source/edited image hashes. All labels can guide their own leaf's fitting. Historical observations and feedback were excluded from the new run.

One label-free compilation per case produced a common decomposition, binding, score anchors and weight ledger. The two arms received identical seed conditions, differing only in their saved scoring mode. Both used GPT-6 Luna, temperature zero, reasoning none, with independent optimization histories and observations. No Sol proposer, semantic auditor or model-based final readout ran.

**Important baseline definition:** this pair uses an anchored numerical observer in both arms. The binary arm converts score **1** to a fully-complete vote and every known score below 1 to an incomplete vote; all/some/none determines its label. It is **not a rerun of the historical v6 model's Boolean pass/fail prompt**. This distinction limits claims about replacing the existing best implementation.

## 3. Scoring definitions

Each required component produces a fulfillment degree `f_i` in [0,1], grounded by saved examples for no achievement, half achievement and full achievement. Confidence is a separate estimate of certainty. A condition can be half fulfilled with high confidence; confidence never increases its score or weight.

For applicable required conditions, `F = sum(w_i × f_i) / sum(w_i)`:

| Fulfillment | Label |
|---|---|
| F >= 0.9 | Satisfied |
| F <= 0.1 | Nonsatisfied |
| 0.1 < F < 0.9 | Partial |

Code assigns equal immutable requirement budgets, then equal shares to their seed facets. Splitting divides the parent share equally while preserving its root. Auxiliary additions have zero weight. Required positive mass cannot be removed, and neither weights nor thresholds can be proposed by the model. Exact rational arithmetic protects threshold boundaries.

Unknown/invalid/transport-failed scores contribute a possible range [0,1], never a zero vote. The aggregate resolves only when its entire lower-to-upper range occupies one label band. Example: one half-weight condition at .5 and one unmeasured condition yield [.25,.75], safely partial **under the declared scores**. The missing atom remains explicit and can fail confidence/robustness gates.

## 4. Optimization and verification procedure

1. Compile the shared seed without reference labels or optimization feedback.
2. Independently screen each arm's program once. Confirm resolved matching candidates with five fresh draws.
3. Use node-level native TextGrad feedback and label-blind visual discovery to propose at most two immutable transactions per round, up to fifteen rounds. Allowed edits are revision, conserved splitting, zero-weight auxiliary addition and auxiliary removal.
4. Retain the seed and valid intermediates; reject broken coverage, weights, endpoints, schema or four-check limits. Rejected diagnostics return to later proposals.
5. Qualification requires 5/5 target agreement and resolved coverage, confidence >=.8 on executed checks, requirement/check consistency >=.8, and at least three eligible observations. This is empirical qualification without semantic-audit approval.
6. Freeze **all 24 selections before any final draw**. Execute each seed and selected program five fresh times. Final outcomes cannot trigger edits or candidate replacement.

The numerical observer receives the condition/anchors, source and edited images, and original requirement. It receives **no reference label, feedback, scoring mode, thresholds or weights**. Every trace records both deterministic readouts on its scores. Models cannot return the final category directly.

One transport-only recovery check per report is permitted in a distinct durable slot, selected in execution order without labels. Every other observation remains exact. Valid wrong/uncertain, schema-invalid and interrupted observations are never resampled. Raw results, both attempts and all charges remain saved.

## 5. Metrics and column meanings

- **Accuracy:** final labels matching the reference divided by 60 planned selected runs per arm. Unresolved draws are incorrect. Twelve cases × five repeats produces 60 measurements, not 60 independent cases.
- **Coverage:** fraction of runs producing a resolved label; a wrong answer still has coverage.
- **All-five-correct case ratio:** cases matching their reference in all five final runs divided by twelve. This matches the user's accurate-and-repeatable definition.
- **Locally robust:** qualified confirmation plus fresh final agreement, coverage, atomic consistency and confidence gates. Overall label stability alone is insufficient.
- **Seed → selected:** correct fresh final runs before/after local optimization; both measured independently. The seed was retained when no acceptable replacement survived.
- **Raw / effective:** scheduled observations before / after the one-check transport-recovery allowance.
- **Fulfillment score:** degree of completion; **confidence:** certainty of the observation. Neither is a calibrated probability of correctness.
- **Rounds started / completed:** dispatched repair rounds / rounds without infrastructure interruption. Started rounds still count against the fifteen-round cap.

## 6. Aggregate outcomes

| Metric | Binary | Weighted fulfillment |
|---|---:|---:|
| Seed correct final runs | 27/60 (45.0%) | 30/60 (50.0%) |
| Selected correct final runs | 35/60 (58.3%) | 48/60 (80.0%) |
| Selected resolved runs | 60/60 (100%) | 59/60 (98.3%) |
| Raw all-five-correct cases | 5/12 (41.7%) | 6/12 (50.0%) |
| Effective all-five-correct cases | 7/12 (58.3%) | 8/12 (66.7%) |
| Strict locally robust cases | 7/12 | 8/12 |
| Selected programs changed | 2/12 | 4/12 |

| Reference class | Binary matches | Fulfillment matches |
|---|---:|---:|
| Satisfied | 15/20 (75%) | 15/20 (75%) |
| Partial | 0/20 (0%) | 13/20 (65%) |
| Nonsatisfied | 20/20 (100%) | 20/20 (100%) |

The case-level gain was only one additional perfect case, despite thirteen additional correct draws. Pencil and chalk each matched four times rather than all five. A small dataset and within-case repeated measurements do not support a statistical significance or generalization claim.

## 7. All twelve cases

The match columns count correct final runs **out of five**, shown as seed → selected. Names are the original instructions. The last column describes the selected fulfillment program's final labels.

| # | Instruction | Reference | Binary matches / 5 | Fulfillment matches / 5 | Fulfillment selected labels |
|---|---|---|---:|---:|---|
| 1 | transform the black DVD into a white DVD | Nonsatisfied | 2 → 5 | 0 → 5 | Nonsatisfied × 5 |
| 2 | Make her close her jacket fully | Satisfied | 0 → 0 | 0 → 0 | Nonsatisfied × 5 |
| 3 | Change the image into pencil drawing | Partial | 0 → 0 | 5 → 4 | Partial × 4, Satisfied × 1 |
| 4 | Give the woman a helmet | Satisfied | 5 → 5 | 5 → 5 | Satisfied × 5 |
| 5 | Change the background into a basketball court | Satisfied | 0 → 5 | 0 → 5 | Satisfied × 5 |
| 6 | Move the mug to the right of the headphones | Partial | 0 → 0 | 0 → 5 | Partial × 5 |
| 7 | Move the book behind the flower | Nonsatisfied | 5 → 5 | 5 → 5 | Nonsatisfied × 5 |
| 8 | Stuffing the paper into the cup | Nonsatisfied | 5 → 5 | 5 → 5 | Nonsatisfied × 5 |
| 9 | Make this look like a comic book photo | Nonsatisfied | 5 → 5 | 0 → 5 | Nonsatisfied × 5 |
| 10 | Turn the image into a drawing made from chalk | Partial | 0 → 0 | 5 → 4 | Partial × 4, Unresolved × 1 |
| 11 | Put a frog in the toilet | Partial | 0 → 0 | 0 → 0 | Satisfied × 5 |
| 12 | the small gray rubber cylinder becomes brown | Satisfied | 5 → 5 | 5 → 5 | Satisfied × 5 |

## 8. What caused the difference

**Pencil:** the binary arm predicted nonsatisfied four times and satisfied once, with scores .65, .65, .85, .85 and 1. The fulfillment arm predicted partial four times and satisfied once, at .85, .65, 1, .75 and .85. Grading captured intermediate fulfillment, but one complete-score estimate still broke repeatability.

**Mug:** binary remained satisfied in 5/5. Fulfillment revised source-object binding and score anchors after four rounds, then returned .5 / partial in 5/5. Its saved binding explicitly discusses the original blue mug, a blue remnant, and multiple new candidate mugs. The model inferred partial movement; the original mug's identity remains ambiguous. Matching the reference does not certify correct object tracking.

**Chalk:** binary repeatedly scored .85 but converted every incomplete endpoint to a negative vote, yielding nonsatisfied in 5/5. Fulfillment correctly mapped .85 to partial in four runs. A failed primary call and failed recovery left one score unmeasured [0,1], so that case remained unresolved and not locally robust.

**Jacket:** both arms repeatedly scored 0 against a satisfied reference. **Frog:** both repeatedly scored 1 against a partial reference. Softer aggregation did not resolve these persistent disagreements. The experiment does not establish whether the visual interpretation, criteria or annotation is responsible.

## 9. Same-observation counterfactuals

These computations reuse the exact selected-program observations; they make no new model calls and do not select new candidates.

| Program family and observations | Binary readout correct | Fulfillment readout correct |
|---|---:|---:|
| Binary-optimized programs | 35/60 | 34/60 |
| Fulfillment-optimized programs | 35/60 | 48/60 |

On binary-optimized programs, the fulfillment mapping gained nine partial-case matches but lost ten nonsatisfied matches: DVD mean .25 and comic means .175–.275 became partial. Fulfillment optimization instead drove their observed degree to 0 using revised criteria/bindings. Therefore **switching the aggregation formula alone was insufficient**. The combined scoring-aware optimization performed better within this pair.

Independent optimization and fresh measurements still differ between arms. The counterfactuals isolate deterministic readout effects on each program's saved observations; they do not simulate how the other optimization path would evolve.

## 10. Search effort and rejected proposals

| Measurement | Binary | Fulfillment |
|---|---:|---:|
| Repair rounds started | 77 | 39 |
| Repair rounds completed | 68 | 37 |
| Proposed transactions | 51 | 25 |
| Structurally valid transactions | 48 | 21 |
| Duplicate candidates | 7 | 1 |
| New candidates screened | 41 | 20 |

Binary used 488 case-scoped calls and 100,017 charged completion tokens; fulfillment used 367 calls and 57,132 tokens. The twelve shared compilation calls consumed another 3,329 completion tokens. These are recorded usage comparisons on this set, not universal efficiency estimates.

Three binary and four fulfillment transactions were rejected. Three rejections across both arms contained the word “progress” in a question; four tried to change the saved endpoint string. Duplicates were retained in history but not screened again.

**Guard limitations:** the jacket fulfillment proposal in round 11 asked whether the jacket was fully closed, partly closed with visible progress, or unchanged, while preserving its endpoint. The lexical progress guard rejected it. This could be a legitimate graded question, so the guard is more restrictive than a semantic check. Frog proposals that clarified a “newly added frog” were rejected for changing the endpoint text. Exact string equality can reject meaningful refinements. These candidates were not measured, and we cannot claim they would have improved accuracy. The rejections are implementation constraints, not semantic-audit judgments.

## 11. Transport, continuation and accounting

The initial run stopped at **188 calls / 51,046 charged completion tokens** after three consecutive TLS BAD_RECORD_MAC errors, with four selections frozen and zero final draws. The user explicitly authorized one continuation. Failed slots remained charged and were not retried; later unattempted work proceeded under identical sources/configuration.

The completed run used **867 calls / 160,478 charged completion tokens**, plus **2,239,059 returned input tokens**. All returned model identities were `gpt-6-luna`. There were **845 completed attempts and 22 transport failures**, split into fourteen search and eight final failures. Final execution included seven recovery calls: six succeeded and one failed. The remaining chalk unknown is a transport failure, not a negative observation or valid visual uncertainty.

All selections froze at call **580**, followed by **287 final calls**. There were zero semantic-audit, Sol-proposer or model-readout calls, no automatic schema repair, no model substitution and no certificate-verification changes.

Approved ceilings: 3,600 calls / 4,608,000 completion tokens. Each case-arm had 107 search and 42 final calls, with 1,008 final calls / 1,032,192 tokens reserved globally. Caps were 1,024 tokens per checker, 2,048 per compiler/gradient/discovery and 4,096 per proposal. Actual call use was 24.1% of the ceiling.

## 12. Historical comparison

| Saved experiment / arm | Selected draw accuracy | All-five-correct case ratio |
|---|---:|---:|
| v5 counting, Luna-only | 44/60 (73.3%) | 8/12 (66.7%) |
| v5 counting, Luna→Sol | 36/60 (60.0%) | 7/12 (58.3%) |
| v6 endpoints, Luna-only | 52/60 (86.7%) | 8/12 (66.7%), after recovery |
| v6 endpoints, Luna→Sol | 42/60 (70.0%) | 6/12 (50.0%), after recovery |
| v7 paired binary | 35/60 (58.3%) | 7/12 (58.3%), after recovery |
| v7 fulfillment | 48/60 (80.0%) | 8/12 (66.7%), after recovery |

The same case identities appear across these experiments, but compiler prompts, observation formats, criteria, search/confirmation rules and transport-recovery policies differ. They are descriptive comparisons. **V7 fulfillment did not beat the prior v6 Luna-only draw accuracy, and did not increase its perfect-case ratio.** The fresh paired binary baseline is strict completeness from numerical scores, not the prior Boolean judge.

## 13. Verification and reproducibility

Before live execution: **1,390 offline unit tests passed, 23 skipped**; all 22 focused fulfillment tests passed. A directly measured synthetic pixel demo, with zero model calls, verified 0/.5/.95/1 mapped to nonsatisfied/partial/satisfied/satisfied, while strict binary stayed nonsatisfied until full completion.

After completion, current-source and pinned-source replay passed with model calls forbidden. Independent verification recomputed exact rational bounds and both readouts, checked protected mass and common seed parity, label/mode/weight isolation, original image hashes/source groups, final freeze, unique durable slots and both-attempt recovery costs. Replays preserved results and accounting. No final outcome changed a selected program or threshold.

```bash
.venv/bin/python logs/exps/261009-fulfillment-v7/analyze_saved_run.py --replay
.venv/bin/python logs/exps/261009-fulfillment-v7/replay_frozen_analysis.py
.venv/bin/python logs/exps/261009-fulfillment-v7/generate_complete_report.py
```

Saved programs execute their original bindings, anchors, weights and thresholds. Previous v2–v6 artifacts retain their explicit version dispatch. No commit or push was made.

## 14. Conclusions and next experiments

1. Retain fulfillment as a useful representation of incomplete individual conditions; its partial-case benefit is demonstrated within this graded pair.
2. Do not assume softer thresholds improve every existing program. Nonsatisfied anchors/bindings need to distinguish genuine requested completion from unrelated/source features.
3. Replace overly broad lexical rejection with a typed distinction between graded endpoint questions and generic helper progress, and evaluate any relaxation separately. Do not treat endpoint paraphrases as automatically equivalent without explicit provenance.
4. Review jacket and frog images/annotations and the exact saved criteria; do not relabel solely to match the model. Fixed aggregation cannot correct a consistently wrong degree estimate.
5. Address transport reliability before expanding repeated image calls. Preserve raw/effective metrics and failed-slot accounting; never selectively resample valid wrong answers.
6. If testing decomposition itself, explicitly compare grounded multi-condition versus broad graded programs. Ten single-condition seeds in this experiment cannot establish a tree advantage.
7. Freeze any revised anchors/thresholds before a new evaluation. No numerical fulfillment ground truth was available here; subjective degree and reported confidence are not calibrated.

The result supports **scoring-aware local fulfillment optimization**, while leaving semantic correctness, calibration and cross-case generalization unproven.

## 15. Artifact index

- [Frozen manifest and exact case/image identities](../../logs/exps/261009-fulfillment-v7/manifest.json)
- [Machine-readable final results](../../logs/exps/261009-fulfillment-v7/results.json)
- [Summary](../../logs/exps/261009-fulfillment-v7/summary.json)
- [Class metrics](../../logs/exps/261009-fulfillment-v7/class_metrics.json)
- [Usage by returned model](../../logs/exps/261009-fulfillment-v7/usage_by_model.json)
- [Independent protocol verification](../../logs/exps/261009-fulfillment-v7/protocol_verification.json)
- [Frozen-selection hashes](../../logs/exps/261009-fulfillment-v7/selection_freeze.json)
- [Complete saved leaf bundle](../../logs/exps/261009-fulfillment-v7/leaves.json)
- [Full machine-readable report details](../../logs/exps/261009-fulfillment-v7/complete_report_statistics.json)
- [Earlier v6 report](calitree_counting_endpoints_v6.md)
- [TLS diagnostic findings](calitree_tls_diagnostics.md)

## Appendix: every selected question, weight, anchor, score and confidence

### 1. transform the black DVD into a white DVD

Reference: **Nonsatisfied**. Case identity: `aurora-task-49616ac011dcfc46a053::magic_reproduce_epoch=47-step=12999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/kubric/8159/input.jpg>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/kubric/8159/magic_reproduce_epoch=47-step=12999.png>)

#### binary

Final seed → selected matches: **2 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: yes. Checks: 2 → 2.

Search rounds: 1 started / 0 completed. Stop: `confirmation_qualified`. Calls: 19 search + 20 final. Charged completion tokens: 5,746.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/0.json). Selected program hash: `5aec98f222ec463b10fc5fc417af8d615f1e2d37c39a4b41b126a00245efc595`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 50.0% | Is the source DVD visibly transformed to white in EDITED? |
| d2 | 50.0% | Does the transformed object remain identifiable as the same DVD shown in SOURCE? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.98, d2: 0.88 |
| 2 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.98, d2: 0.91 |
| 3 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.98, d2: 0.88 |
| 4 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.98, d2: 0.91 |
| 5 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.98, d2: 0.91 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** The source DVD remains black, is absent without evidence of its transformation, or no requested color change to that same object is visible; unrelated white objects do not count.
- **d1 — 0.5:** There is concrete but incomplete evidence that the same source DVD is changing toward white, while substantial black coloration remains or correspondence to the source object is genuinely ambiguous.
- **d1 — 1:** The same DVD shown in SOURCE is clearly identifiable by its position, outline, and surrounding scene context in EDITED and is visibly white rather than black, allowing natural lighting, texture, and photographic variation. Whiteness of another object alone is not full achievement.
- **d2 — 0:** The source DVD is not identifiable in EDITED and there is no concrete evidence linking an edited object to it, or the apparent change concerns a different object.
- **d2 — 0.5:** Position or surrounding scene cues provide some evidence that an edited object corresponds to the source DVD, but changed outline, competing objects, or other ambiguity prevents clear identification.
- **d2 — 1:** The transformed object is clearly identifiable as the same DVD shown in SOURCE through its position, outline, and surrounding scene context; disc-like appearance alone is insufficient.

#### fulfillment

Final seed → selected matches: **0 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: yes. Checks: 2 → 2.

Search rounds: 2 started / 2 completed. Stop: `confirmation_qualified`. Calls: 24 search + 20 final. Charged completion tokens: 5,103.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/0.json). Selected program hash: `3a5bcf3d00274075582fa45a7afaf70a91f2668180c3275975c8f3b1de578d2d`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 50.0% | Is the source DVD visibly transformed to white in EDITED? |
| d2 | 50.0% | Does the transformed object remain identifiable as the same DVD? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.91, d2: 0.98 |
| 2 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.94, d2: 0.98 |
| 3 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.96, d2: 0.98 |
| 4 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.91, d2: 0.96 |
| 5 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.94, d2: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The source DVD remains black, no requested color change is visible on an object supported as that DVD, or only an unrelated/new white disc is visible.
- **d1 — 0.5:** Evidence supports that an edited candidate is the source DVD and it shows a concrete but incomplete change toward white, with substantial black coloration remaining; unresolved correspondence alone is not evidence of partial color fulfillment.
- **d1 — 1:** The source DVD is supported as the same object in EDITED by its location, shape, or visible features, and that object is visibly white rather than black, allowing natural lighting, texture, and photographic variation.
- **d2 — 0:** The DVD is not identifiable in EDITED, or the apparent change concerns a different object.
- **d2 — 0.5:** Visible location, shape, or feature continuity supports identifying the edited object as the source DVD, but substantial ambiguity remains about whether it is the same object; DVD-like appearance alone is not partial identity fulfillment.
- **d2 — 1:** The transformed object is clearly identifiable as the same DVD shown in SOURCE through continuity of its location, shape, or visible features.

### 2. Make her close her jacket fully

Reference: **Satisfied**. Case identity: `aurora-task-4d9932789529604a30e8::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/ag/6ALEL.mp4_3_left/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/ag/6ALEL.mp4_3_left/finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999.png>)

#### binary

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Nonsatisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 15 completed. Stop: `round_limit`. Calls: 54 search + 10 final. Charged completion tokens: 9,268.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/1.json). Selected program hash: `a86b35c6382ff2e6ab338f112a441cb3e03e14d4f15ace2d11da41d568fac044`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is her jacket fully closed? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.91 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.91 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** The jacket shows no requested progress toward closure compared with SOURCE.
- **d1 — 0.5:** The jacket is partly closed, with concrete progress toward closure but a visible opening remaining.
- **d1 — 1:** The jacket is fully closed, with no visible opening remaining along its closure.

#### fulfillment

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Nonsatisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 14 completed. Stop: `round_limit`. Calls: 54 search + 10 final. Charged completion tokens: 13,571.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/1.json). Selected program hash: `b1b41963fcbe749f5059b57ebc48e31d2fc47e8add9dd831905de48ad308c535`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is her jacket fully closed? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.96 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.94 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.96 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.91 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** The jacket shows no requested progress toward closure compared with SOURCE.
- **d1 — 0.5:** The jacket is partly closed, with concrete progress toward closure but a visible opening remaining.
- **d1 — 1:** The jacket is fully closed, with no visible opening remaining along its closure.

### 3. Change the image into pencil drawing

Reference: **Partial**. Case identity: `aurora-task-52fd3fa52d915723d12d::mgie`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/1606/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/1606/mgie.png>)

#### binary

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Nonsatisfied × 4, Satisfied × 1. Status: `unstable_and_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 10 completed. Stop: `round_limit`. Calls: 60 search + 10 final. Charged completion tokens: 28,590.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/2.json). Selected program hash: `24e4f6b9bcc5c37b6c283df4adf67650f3ee69a8e6a2cb3810b2d735a2e46da7`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the image rendered as a pencil drawing? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.65 | Nonsatisfied | d1: 0.65 | d1: 0.88 |
| 2 | 0.65 | Nonsatisfied | d1: 0.65 | d1: 0.88 |
| 3 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.91 |
| 4 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.91 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Nonsatisfied × 4, Satisfied × 1. Same-observation readout accuracy: binary 0/5, fulfillment 4/5.

Saved fulfillment anchors:

- **d1 — 0:** No requested pencil-drawing change is visible; unrelated edits do not count.
- **d1 — 0.5:** About half of the image’s visual content has a concrete pencil-drawn treatment, while substantial content remains in its original non-pencil rendering.
- **d1 — 1:** The image’s visual content is rendered throughout in a recognizable pencil-drawing style, allowing natural variation in texture and lighting.

#### fulfillment

Final seed → selected matches: **5 → 4 / 5**. Selected labels: Partial × 4, Satisfied × 1. Status: `unstable_and_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 11 final. Charged completion tokens: 2,568.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/2.json). Selected program hash: `3239526671595bd6940c7d42d7330af945af1a179eca06e6b3e6eba4e876663b`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the image rendered as a pencil drawing? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.85 | Partial | d1: 0.85 | d1: 0.91 |
| 2 | 0.65 | Partial | d1: 0.65 | d1: 0.88 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |
| 4 | 0.75 | Partial | d1: 0.75 | d1: 0.91 |
| 5 | 0.85 | Partial | d1: 0.85 | d1: 0.91 |

Acceptance failures: target_mismatch.

Raw labels before recovery: Partial × 4, Satisfied × 1. Same-observation readout accuracy: binary 0/5, fulfillment 4/5.

Saved fulfillment anchors:

- **d1 — 0:** No requested pencil-drawing change is visible; unrelated edits do not count.
- **d1 — 0.5:** About half of the image’s visual content has a concrete pencil-drawn treatment, while substantial content remains in its original non-pencil rendering.
- **d1 — 1:** The image’s visual content is rendered throughout in a recognizable pencil-drawing style, allowing natural variation in texture and lighting.

### 4. Give the woman a helmet

Reference: **Satisfied**. Case identity: `aurora-task-538ef5e1e9d068bbfe6d::magic_reproduce_epoch=47-step=12999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/magicbrush/385037_Give_the_woman_a_helmet..png/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/magicbrush/385037_Give_the_woman_a_helmet..png/magic_reproduce_epoch=47-step=12999.png>)

#### binary

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 842.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/3.json). Selected program hash: `0ad986f28ec6f739df135d46d808f133a031b8ea22cf76c3a0a6ad2ab609d523`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Does the woman visibly have a helmet on her head? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: none.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The woman has no helmet on her head in EDITED; unrelated edits do not count.
- **d1 — 0.5:** A helmet is partly added or only partly on her head, with concrete visible deficiencies preventing the requested endpoint.
- **d1 — 1:** The woman visibly wears or otherwise has a helmet on her head in EDITED.

#### fulfillment

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 11 final. Charged completion tokens: 1,889.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/3.json). Selected program hash: `6762f4baea0a0022884293d5998e6c08d1eca6256c8d22ae4d1cc24928249a9e`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Does the woman visibly have a helmet on her head? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: none.

Raw labels before recovery: Satisfied × 4, Unresolved × 1. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The woman has no helmet on her head in EDITED; unrelated edits do not count.
- **d1 — 0.5:** A helmet is partly added or only partly on her head, with concrete visible deficiencies preventing the requested endpoint.
- **d1 — 1:** The woman visibly wears or otherwise has a helmet on her head in EDITED.

### 5. Change the background into a basketball court

Reference: **Satisfied**. Case identity: `aurora-task-65581617ad341fa398cb::magic_reproduce_epoch=47-step=12999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/982/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/982/magic_reproduce_epoch=47-step=12999.png>)

#### binary

Final seed → selected matches: **0 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: yes. Checks: 1 → 1.

Search rounds: 1 started / 0 completed. Stop: `confirmation_qualified`. Calls: 11 search + 11 final. Charged completion tokens: 4,302.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/4.json). Selected program hash: `a05ba4762eb955f0087ab9868eab2bf174ca75e45cab82f0942fc3d8c87fc942`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Has the image background been changed into a recognizable basketball court? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: none.

Raw labels before recovery: Satisfied × 4, Unresolved × 1. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The EDITED background remains the original setting or shows no concrete basketball-court cues; unrelated edits do not count.
- **d1 — 0.5:** The EDITED background has some court-related cues, but they are isolated or ambiguous and do not establish a recognizable basketball-court setting.
- **d1 — 1:** The EDITED background is recognizably a basketball court from coherent visible court cues, such as a playing surface with markings and/or basketball equipment. Limited framing, darkness, or ordinary visual imperfections do not prevent full achievement when the court identity is clear.

#### fulfillment

Final seed → selected matches: **0 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: yes. Checks: 1 → 1.

Search rounds: 2 started / 2 completed. Stop: `confirmation_qualified`. Calls: 19 search + 10 final. Charged completion tokens: 3,708.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/4.json). Selected program hash: `f7c329098a67d7410cd588a5e31cfe7280bf3ccace1df1d7847740912d98cf2d`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Has the image background been changed into a recognizable basketball court? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: none.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The background shows no requested change toward depicting a basketball court; unrelated edits do not count.
- **d1 — 0.5:** The background has concrete basketball-court cues, but the background as a whole remains genuinely ambiguous or incomplete as a playing court—for example, basketball equipment appears without enough visible playing-surface or court context to establish the setting.
- **d1 — 1:** The background as a whole is clearly recognizable as a basketball court from visible court context, markings, or basketball equipment integrated with a playing surface. Sparse or stylized context is acceptable when the court identity is clear; a dark or featureless area elsewhere in the background does not prevent full achievement when the visible playing surface and court cues establish the setting. Natural variation in lighting, texture, or photographic appearance is acceptable.

### 6. Move the mug to the right of the headphones

Reference: **Partial**. Case identity: `aurora-task-7b78f1229d9bb014bcc5::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/whatsup/mug_left_of_headphones/input.jpeg>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/whatsup/mug_left_of_headphones_Move_the_mug_to_the_right_of_the_headphones.png/finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999.jpg>)

#### binary

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Satisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 15 completed. Stop: `round_limit`. Calls: 59 search + 10 final. Charged completion tokens: 20,423.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/5.json). Selected program hash: `19afbd2336f150d0558f5e5ae3d7c7fceb1fe7c86e871480a16dca9b0937f67b`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the mug visibly positioned to the right of the headphones in the edited image? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.94 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** The mug has not moved to the right of the headphones; unrelated edits do not count.
- **d1 — 0.5:** The mug has moved toward the right of the headphones but is not yet positioned to their right, with a concrete remaining positional deficiency.
- **d1 — 1:** The mug is visibly positioned to the right of the headphones.

#### fulfillment

Final seed → selected matches: **0 → 5 / 5**. Selected labels: Partial × 5. Status: `locally_robust`. Program changed: yes. Checks: 1 → 1.

Search rounds: 4 started / 4 completed. Stop: `confirmation_qualified`. Calls: 22 search + 10 final. Charged completion tokens: 6,489.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/5.json). Selected program hash: `7b2fa515690bea0cfa09a0e2ca66ac9923f8cfa21f1be5ac4f2feed6a4782b5c`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the source mug visibly positioned to the right of the headphones, or does the edited image show concrete displacement of that mug toward the headphones? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.5 | Partial | d1: 0.5 | d1: 0.88 |
| 2 | 0.5 | Partial | d1: 0.5 | d1: 0.84 |
| 3 | 0.5 | Partial | d1: 0.5 | d1: 0.84 |
| 4 | 0.5 | Partial | d1: 0.5 | d1: 0.88 |
| 5 | 0.5 | Partial | d1: 0.5 | d1: 0.91 |

Acceptance failures: none.

Raw labels before recovery: Partial × 5. Same-observation readout accuracy: binary 0/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** There is no concrete visual evidence supporting that the source mug moved toward the right of the headphones; a blur at its original location or a different mug appearing elsewhere, without supporting continuity, does not count as movement.
- **d1 — 0.5:** The edited image provides concrete visual evidence consistent with the source mug having moved toward the headphones, but does not establish that the source mug reached a position to their right. Consider the blue remnant at the former location together with plausible intermediate placement, while weighing multiple candidates and appearance changes. If the evidence genuinely cannot support either movement or no movement, use an unresolved score rather than partial credit or zero.
- **d1 — 1:** The source mug is clearly identifiable in the edited image and is visibly positioned to the right of the headphones.

### 7. Move the book behind the flower

Reference: **Nonsatisfied**. Case identity: `aurora-task-88caae46533b0440f452::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/whatsup/book_left_of_flower/input.jpeg>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/whatsup/book_left_of_flower_Move_the_book_behind_the_flower.png/finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999.jpg>)

#### binary

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 1,290.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/6.json). Selected program hash: `82d57a20f5432826130f3745134a110d47b79aa76d26a9c3c57b13460b835c29`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the book visibly positioned behind the flower in the edited image? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.94 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The book’s position relative to the flower shows no requested change from SOURCE to EDITED; unrelated edits do not count.
- **d1 — 0.5:** The relative position has changed toward placing the book behind the flower, but the book is not clearly behind it or the flower is not clearly in front.
- **d1 — 1:** The EDITED image clearly shows the book behind the flower, with the flower in front.

#### fulfillment

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 1,309.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/6.json). Selected program hash: `9520fe4917fbd97a5f163b694b043512d519d7d78fe2910a37a5731136802a50`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the book visibly positioned behind the flower in the edited image? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.94 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.96 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The book’s position relative to the flower shows no requested change from SOURCE to EDITED; unrelated edits do not count.
- **d1 — 0.5:** The relative position has changed toward placing the book behind the flower, but the book is not clearly behind it or the flower is not clearly in front.
- **d1 — 1:** The EDITED image clearly shows the book behind the flower, with the flower in front.

### 8. Stuffing the paper into the cup

Reference: **Nonsatisfied**. Case identity: `aurora-task-9a1ea55edac097679512::mgie`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/something/216236/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/something/216236/mgie.jpg>)

#### binary

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 1,167.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/7.json). Selected program hash: `0a939cfda29d93d6581d378ba7aec38713fcfbaa5a4e207689c750868ea3664e`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the paper visibly inside the cup and stuffed into it? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The paper has not been moved into the cup; it remains outside or only rests on the rim.
- **d1 — 0.5:** The paper is partly inserted or partly stuffed into the cup, but concrete evidence shows the requested placement is incomplete.
- **d1 — 1:** The paper is visibly placed inside and stuffed into the cup.

#### fulfillment

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 1,165.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/7.json). Selected program hash: `6c194f5c28d3dcd3bfa0fa10fc6b95579be988417e24366cf57760e61badd277`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the paper visibly inside the cup and stuffed into it? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 2 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 3 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 4 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |
| 5 | 0.0 | Nonsatisfied | d1: 0 | d1: 0.99 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The paper has not been moved into the cup; it remains outside or only rests on the rim.
- **d1 — 0.5:** The paper is partly inserted or partly stuffed into the cup, but concrete evidence shows the requested placement is incomplete.
- **d1 — 1:** The paper is visibly placed inside and stuffed into the cup.

### 9. Make this look like a comic book photo

Reference: **Nonsatisfied**. Case identity: `aurora-task-bfa82afe32a86d47dfdf::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/2808/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/2808/finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999.png>)

#### binary

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 2 → 2.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 13 search + 21 final. Charged completion tokens: 4,555.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/8.json). Selected program hash: `f6fa9be41b715ce090f24083c30bba845c460345e8b5b152a95c6d202dfa4d3d`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 50.0% | Does the edited image visibly have a comic-book visual style? |
| d2 | 50.0% | Does the edited image retain the photographic subject matter while presenting it as a comic-book photo? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.175 | Nonsatisfied | d1: 0, d2: 0.35 | d1: 0.94, d2: 0.88 |
| 2 | 0.175 | Nonsatisfied | d1: 0, d2: 0.35 | d1: 0.98, d2: 0.91 |
| 3 | 0.275 | Nonsatisfied | d1: 0, d2: 0.55 | d1: 0.97, d2: 0.91 |
| 4 | 0.25 | Nonsatisfied | d1: 0, d2: 0.5 | d1: 0.96, d2: 0.94 |
| 5 | 0.175 | Nonsatisfied | d1: 0, d2: 0.35 | d1: 0.97, d2: 0.91 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 4, Unresolved × 1. Same-observation readout accuracy: binary 5/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** No requested comic-book styling is visible in EDITED compared with SOURCE; unrelated edits do not count.
- **d1 — 0.5:** Some comic-book styling is visible, but it is limited or inconsistent, with concrete areas remaining substantially unstylized.
- **d1 — 1:** Comic-book styling is clearly visible across the image under the ordinary interpretation of the request.
- **d2 — 0:** EDITED does not retain recognizable photographic subject matter from SOURCE; unrelated changes do not count.
- **d2 — 0.5:** The subject remains partly recognizable or photographic, but substantial parts of the image no longer read as the supplied photo.
- **d2 — 1:** The supplied subject matter remains recognizable and the result reads as a photograph given comic-book styling.

#### fulfillment

Final seed → selected matches: **0 → 5 / 5**. Selected labels: Nonsatisfied × 5. Status: `locally_robust`. Program changed: yes. Checks: 2 → 2.

Search rounds: 1 started / 1 completed. Stop: `confirmation_qualified`. Calls: 18 search + 21 final. Charged completion tokens: 4,569.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/8.json). Selected program hash: `3a6d0865bd094675397fe676e683bcd0bbf95cb5bd9999d58056229f03cd978b`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 50.0% | Does the edited image visibly have a comic-book visual style? |
| d2 | 50.0% | Does the edited image present the recognizable subject matter of the supplied photograph with visible comic-book styling? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.96, d2: 0.97 |
| 2 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.98, d2: 0.97 |
| 3 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.98, d2: 0.97 |
| 4 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.96, d2: 0.98 |
| 5 | 0.0 | Nonsatisfied | d1: 0, d2: 0 | d1: 0.96, d2: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** No requested comic-book styling is visible in EDITED compared with SOURCE; unrelated edits do not count.
- **d1 — 0.5:** Some comic-book styling is visible, but it is limited or inconsistent, with concrete areas remaining substantially unstylized.
- **d1 — 1:** Comic-book styling is clearly visible across the image under the ordinary interpretation of the request.
- **d2 — 0:** EDITED either does not retain recognizable photographic subject matter from SOURCE or shows no visible comic-book styling compared with SOURCE; unrelated edits and ordinary photographic changes do not count.
- **d2 — 0.5:** The supplied subject remains recognizable and there is concrete visible comic-book treatment, but the treatment is limited or inconsistent, or substantial parts still read only as an ordinary photograph.
- **d2 — 1:** The supplied subject matter remains recognizable and visible comic-book styling is clearly applied across the image, so the result reads as a photograph given comic-book styling under the ordinary interpretation of the request.

### 10. Turn the image into a drawing made from chalk

Reference: **Partial**. Case identity: `aurora-task-ce641cb29939011016cc::mgie`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/3404/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/emu/3404/mgie.png>)

#### binary

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Nonsatisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 15 completed. Stop: `round_limit`. Calls: 51 search + 10 final. Charged completion tokens: 9,349.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/9.json). Selected program hash: `446288e1f506ae32e2adcff12b61d783f3f9e076a2c83cd8597f35dbb3218426`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Does the edited image depict the source image as a drawing made from chalk? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.9 |
| 2 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.91 |
| 3 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.9 |
| 4 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.91 |
| 5 | 0.85 | Nonsatisfied | d1: 0.85 | d1: 0.91 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Nonsatisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The edited image shows no requested chalk-drawing transformation of the source image; unrelated edits do not count.
- **d1 — 0.5:** The source image has a concrete but incomplete chalk-drawing treatment, with substantial visible aspects still not rendered as a chalk drawing.
- **d1 — 1:** The edited image presents the source image as a drawing made from chalk, allowing natural variation in lighting, texture, and photographic detail.

#### fulfillment

Final seed → selected matches: **5 → 4 / 5**. Selected labels: Partial × 4, Unresolved × 1. Status: `unresolved`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 11 final. Charged completion tokens: 3,517.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/9.json). Selected program hash: `54615a378dbf48a6f4de06d9f34747119a70069e178541d24a882a0cde48938a`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Does the edited image depict the source image as a drawing made from chalk? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 0.85 | Partial | d1: 0.85 | d1: 0.9 |
| 2 | 0.85 | Partial | d1: 0.85 | d1: 0.88 |
| 3 | [0.0, 1.0] | Unresolved | d1: None | d1: None |
| 4 | 0.85 | Partial | d1: 0.85 | d1: 0.91 |
| 5 | 0.85 | Partial | d1: 0.85 | d1: 0.91 |

Acceptance failures: unresolved, target_mismatch, confidence.

Raw labels before recovery: Partial × 4, Unresolved × 1. Same-observation readout accuracy: binary 0/5, fulfillment 4/5.

Saved fulfillment anchors:

- **d1 — 0:** The edited image shows no requested chalk-drawing transformation of the source image; unrelated edits do not count.
- **d1 — 0.5:** The source image has a concrete but incomplete chalk-drawing treatment, with substantial visible aspects still not rendered as a chalk drawing.
- **d1 — 1:** The edited image presents the source image as a drawing made from chalk, allowing natural variation in lighting, texture, and photographic detail.

### 11. Put a frog in the toilet

Reference: **Partial**. Case identity: `aurora-task-e0f9b97dc3bc00415cf2::mgie`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/magicbrush/483348_Put_a_frog_in_the_toilet..png/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/magicbrush/483348_Put_a_frog_in_the_toilet..png/mgie.png>)

#### binary

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Satisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 13 completed. Stop: `round_limit`. Calls: 55 search + 10 final. Charged completion tokens: 13,561.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/10.json). Selected program hash: `4749172b2c046c27603c4d0403954fd940113ebaa993fe1efd82bc48a48abb03`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is a frog visibly placed inside the toilet bowl? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** No frog has been added inside the toilet bowl; unrelated edits do not count.
- **d1 — 0.5:** A frog is partly placed in the bowl, with concrete evidence of placement but a substantial part of the requested placement still unfulfilled.
- **d1 — 1:** A frog is visibly placed within the toilet bowl.

#### fulfillment

Final seed → selected matches: **0 → 0 / 5**. Selected labels: Satisfied × 5. Status: `stable_but_mismatched`. Program changed: no. Checks: 1 → 1.

Search rounds: 15 started / 14 completed. Stop: `round_limit`. Calls: 49 search + 10 final. Charged completion tokens: 11,304.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/10.json). Selected program hash: `0b6dc2fcb3bd0253473126688ff75197b121d495759ae9b22fe69842270a7b42`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is a frog visibly placed inside the toilet bowl? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.99 |

Acceptance failures: target_mismatch, confirmation_missing_or_unqualified.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 0/5, fulfillment 0/5.

Saved fulfillment anchors:

- **d1 — 0:** No frog has been added inside the toilet bowl; unrelated edits do not count.
- **d1 — 0.5:** A frog is partly placed in the bowl, with concrete evidence of placement but a substantial part of the requested placement still unfulfilled.
- **d1 — 1:** A frog is visibly placed within the toilet bowl.

### 12. the small gray rubber cylinder becomes brown

Reference: **Satisfied**. Case identity: `aurora-task-f335b1c6c0f2062b2cfd::finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999`.

[Source image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/clevr/006040/input.png>) · [Edited image](</Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/data/aurora/bench/human_ratings/clevr/006040/finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999.png>)

#### binary

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 10 final. Charged completion tokens: 924.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/binary/11.json). Selected program hash: `05b93be92557f9593706e9bd015cd9b42b7584f549040dd4c4b370e752350290`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the small gray rubber cylinder brown in the edited image? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.96 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.96 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Satisfied × 5. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The cylinder shows no requested color change and remains gray, or any edits are unrelated to its color.
- **d1 — 0.5:** The cylinder’s color has changed partway toward brown, but it is not yet brown; concrete evidence of the remaining color difference is visible.
- **d1 — 1:** The cylinder appears brown in the edited image.

#### fulfillment

Final seed → selected matches: **5 → 5 / 5**. Selected labels: Satisfied × 5. Status: `locally_robust`. Program changed: no. Checks: 1 → 1.

Search rounds: 0 started / 0 completed. Stop: `confirmation_qualified`. Calls: 6 search + 11 final. Charged completion tokens: 1,940.

[Exact saved program, candidates and edits](../../logs/exps/261009-fulfillment-v7/frozen/fulfillment/11.json). Selected program hash: `8202a4c774b26aac823b9127b2ecb7381d8f4825ba027c120799c45575278583`.

| Check | Weight | Saved question |
|---|---:|---|
| d1 | 100.0% | Is the small gray rubber cylinder brown in the edited image? |

| Final draw | Fulfillment point / bounds | Predicted label | Per-check scores | Per-check confidence |
|---|---|---|---|---|
| 1 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 2 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 3 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 4 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |
| 5 | 1.0 | Satisfied | d1: 1 | d1: 0.98 |

Acceptance failures: none.

Raw labels before recovery: Unresolved × 1, Satisfied × 4. Same-observation readout accuracy: binary 5/5, fulfillment 5/5.

Saved fulfillment anchors:

- **d1 — 0:** The cylinder shows no requested color change and remains gray, or any edits are unrelated to its color.
- **d1 — 0.5:** The cylinder’s color has changed partway toward brown, but it is not yet brown; concrete evidence of the remaining color difference is visible.
- **d1 — 1:** The cylinder appears brown in the edited image.
