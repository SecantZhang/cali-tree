# Verified weighted semantic review

The current verified source-held development score is **227/276 (82.2%)**, up from225/276 (81.5%). The strict over85% target remains **235/276**: eight more correct decisions are needed. All99 original inputs, all144 original evaluation slots and273/276 upstream covered cases are retained. This is a repeatedly reviewed development comparison, not an untouched validation result.

The newer[v112 exact compression](calitree_semantic_compression_v112.md) represents the same function with60 shared terms instead of100 branches. Its separate native/runtime audit preserves this accuracy and all routing outcomes; the original v105 artifacts below remain unchanged for provenance.

The subsequent[class-balanced training comparison](calitree_class_balanced_v142.md) keeps the same architecture and gives each fitting grade equal weight. Balancing both the main classifier and correction scores217/276 (78.6%) with67.4% balanced accuracy, versus227/276 (82.2%) and67.9% for this policy. Balancing the correction alone scores221/276. All original cases and upstream coverage remain protected; none of these arms replaces this policy.

The v105 audit independently re-induces six residual models, checks5,490 native-versus-portable residuals and runs915 cached judgments through the actual inference adapter. The largest numerical difference is6.11e-16. There are no new paid calls, observer calls or reserved-source reads in this verification. Forty-eight focused tests cover the local observation, existing expert behavior, warrants, weighted execution and binding.

## What the semantic policy does

The existing visual/semantic booster, compact v72 rubric and optional independent v87 expert keep priority. The new head executes only if upstream evidence is covered, no earlier rubric/expert rule applies, teacher maximum support is below.8, and a valid local task/preservation observation exists. Missing or invalid local observations retain the prior decision and stay in the scoring denominator. The support threshold is a model routing cue, not a calibrated correctness probability.

The local observer sees both images, the exact edit instruction and compiled requirement descriptions in one joint call. It reports target correspondence, endpoint, progress, collateral type, explicit preservation, goal relevance of collateral and identity necessity. It receives no human grade. Uncertainty alone cannot justify No; unrelated collateral does not automatically cap a successful edit at Partial.

The correction model learns interactions among named semantic concepts and teacher supports. It uses128 depth-two trees, then merges exactly equivalent branches into100 weighted clauses in the full-data artifact. Those clauses use29 concepts; each has at most two conditions. No raw visual vectors, case/source IDs, editor IDs or object-name lookup rules enter this correction. The old base still uses its frozen visual features.

For each class, add the weighted semantic residual to the existing teacher support, floor at1e-9, normalize and choose the largest mass. These are statistical human-grade scores, not physical facts or calibrated probabilities of correctness. A changed grade also needs either an affirmative single-requirement local warrant, or agreement with the independent regular visual judge plus a positive review reason. Otherwise retain the prior grade.

The human-readable rubric is the executable weighted policy: descriptions, float32 threshold semantics, weights and tie order are checked against the compiled artifact. It is larger than a few ordinary grading instructions; rendering it as prose does not make100 learned statistical clauses a simple universal rubric. Its benefit is inspectable task/preservation evidence and faithful execution rather than an unsupported natural-language explanation of a black-box output.

## Paired results and limits

The selected guarded policy makes three corrections and introduces one error versus225/276. It correctsP12M4 andT10M4 fromPartial toYes andT21M5 fromPartial toNo; it incorrectly changesT23M5 fromPartial toYes. The guard, local claims and numerical weights are fallible.

Only83/276 cases are in the actual local review region;82 have accepted observations. Of224 cached observation slots,220 are accepted and four remain failed at the256-token output limit. Collection used222 fresh attempts plus two exact smoke reuses,25,796 fresh completion tokens and no retries. An independent cache audit verifies36 native teachers, fixed source exclusions, all fold masks and request/response accounting.

The prior v87 policy also has only15 valid older, nonrandom Sol views among the primary cases. All other cases keep the earlier policy. This is neither a complete fresh-Sol benchmark nor evidence that the local observer alone achieves82.2%.

Eight bounded Boolean-rule searches reached215–224/276; twelve additive-score arms reached217–224. They were not promoted. The shallow nonlinear residual comparison reached227 in both guarded and unguarded forms; the guarded result has three gains/one loss versus six gains/four losses without the guard.

Follow-up source-held controls did not raise the maximum: fitting with actual original-case anchors ties227 with two gains/no losses versus v87; restricting fitting to primary outputs performs worse. Six direct expert-advantage policies reach223–226. These remain comparisons; the independently audited227 artifact is the opt-in result.

## Higher-resolution evidence experiment

A separate v108 cache completed the same224 frozen inputs using the same checkpoint, seven-field contract, prompt and constrained greedy decoding. It accepts219 records and uses27,164 output tokens. Its image budget increases from256 to1024 visual tokens per image, and its output allowance increases from256 to512 tokens. This is a separate profile; earlier failures remain unchanged. The frozen comparison scores219–225/276 and is not promoted. Computation is local with offline flags; no images, instructions or labels are uploaded.

The v110 one-shot supervisor completes its independent v109 cache audit and four residual fits in score/guarded forms. No arm beats227, so it performs no policy promotion or serving change. See[the observer diagnostics](calitree_observer_diagnostics_v126.md) for the complete results and the next local candidate.

## Evidence

- [Verified policy and runtime audit](../logs/exps/261023-verified-semantic-residual-v105-r1/verification.json).
- [Weighted clauses](../logs/exps/261023-verified-semantic-residual-v105-r1/rubric.txt) and [full portable policy](../examples/calitree_weighted_semantic_v105/policy.json).
- [Complete local-cache audit](../logs/exps/261023-local-review-cache-v98-complete-r1/verification.json).
- [Residual comparison](../logs/exps/261023-semantic-residual-v103-r1/results.json).
- [Anchor/pool controls](../logs/exps/261023-anchored-semantic-residual-v106-r1/results.json).
- [Direct expert-advantage controls](../logs/exps/261023-semantic-expert-advantage-v107-r1/results.json).
- [Higher-resolution protocol](../logs/exps/261023-high-resolution-local-view-v108-r1/protocol.json) and [supervisor state](../logs/exps/261023-high-resolution-pipeline-v110-r1/state.json).
