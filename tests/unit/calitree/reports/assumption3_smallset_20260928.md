# Assumption 3: bounded decision-set development — 2026-09-28

> Historical experiment record. The J16 follow-up prototypes and runners described below were subsequently removed from active code at the user's request. Their commands are historical, not supported current entry points. Saved results and snapshots remain in `.cache/calitree-tests/`. The active design is the simpler frozen-criteria/image-check baseline, with optional neutral observations and uncertain-case review.

## Simplification decision and rollback boundary

The source snapshots from `assumption3-approved2-20260928` establish the rollback boundary, before the repeated J16 follow-up work. Both `decomposition_twoway.py` and `decision_sets.py` are restored exactly to those saved versions. The pre-existing structured/vision strategies, modular controllers, leaf/merge behavior, and canvas implementation are unchanged.

| History branch | Outcome of rollback |
| --- | --- |
| Frozen criteria, ordinary image checks, optional independent neutral observations | Retained as the simple baseline. |
| Evidence-only condition grading, citation contracts, supplemental evidence combination | Removed from active code, templates, and follow-up runners. |
| Paired observation, generated boxes, Grounding DINO setup/runner, grounding-candidate screen | Removed from active code and executable setup scripts. |
| Reviewed-region runner, focused atomic crops, projected-extent categories/reducer | Removed from active code, templates, and runners. |
| Explicit uncertain-case review, J16 registry, call-budget/transport protections | Retained; these handle case quality and costs without a special J16 observer. |

Twenty later files (runners, tests, templates, and detector setup) were removed. Tests for deleted interfaces were removed from the shared test files; baseline observation, artifact, checkpoint, and budget tests remain. This is removal, not merely disabling the new APIs. Historical outputs, original annotations, reviewed regions, and the explicit user review are preserved. The isolated detector environment and cached weights are inactive local artifacts, not runtime dependencies of the remaining code.

A recoverable copy of every removed/edited source file is stored in `.cache/calitree-tests/j16-simplification-backup/before.zip`, with file hashes and the chosen baseline in the neighboring `manifest.json`. The later detailed sections remain intact as the experiment history. Their historical accuracy and budget totals are not recomputed or improved by this rollback. No paid calls were made during simplification.

Rollback verification: **252 tests passed, 23 skipped** across CaliTree, calibration components, modular/manual node integration, and structured-output/budget controls. Both restored core files match the selected historical snapshots byte-for-byte, all archived source hashes verify, and no removed experimental API or runner remains referenced in active Python/shell code. J16's `uncertain` review and original `partial` annotation are preserved. `git diff --check` passed.


The objective is reliable, reusable decision-set observations, starting with the existing fitted cases and expanding only after a small test succeeds. Human labels below are recorded annotations, not presumed ground truth; agreement and semantic correctness must be distinguished. This update adds reusable execution and evidence bindings, followed by an approved two-case live test. **The first live comparison failed its expansion gate:** saved neutral evidence corrected J01 but did not retain J16’s fitted decision. An evidence-only follow-up is promising at the condition level; it does not yet establish full-case stability.

## Starting evidence and selected cases

The [32-case fitted study](casewise_decomposition32_20260926.md) reached 32/32 after disclosed case-specific criterion selection and label feedback. The final two corrections used saved neutral measurements, with one selected checker pass each. Their repeatability is untested.

| Case | Instruction | Human target | Saved optimized raw prediction | Saved fitted statuses | Saved fitted prediction |
| --- | --- | --- | --- | --- | --- |
| J01 | Make them close the curtains | no | partial | Curtain state: partial; person/action association: absent; preservation: complete | no |
| J16 | The fork pulls one piece of fish out of the can | partial | yes | Extraction: partial; other two conditions: complete | partial |

These two cases directly test the current observation weakness: requested action can bias interpretation of ambiguous image evidence. The three criteria per case stay frozen, including their fitting provenance. No new compiler or optimizer is needed for the first comparison. Neither a correct fitted label nor the historical conjunction reducer establishes that the observations are true.

## Algorithm change

`FrozenCriteriaExecutor` lives in the existing consolidated `decomposition_twoway.py`. It is an experimental observation component, not a new default strategy or a replacement for the policy aggregator.

1. Bind the selected criteria to the exact prompt and instruction. Store whether label feedback selected them; exclude that feedback and rubric-conflict records from checker inputs.
2. Describe neutral probes using a property, object class, and optional reference class. Render questions through fixed templates. Give each descriptor a stable hash; discard obsolete local condition IDs. This is lexical identity, not proof of semantic equivalence across concepts.
3. For fresh evidence, send the same questions to each image separately. The observer receives no edit instruction, desired outcome, role marker, rubric, or human annotation. Caller-supplied class nouns still require semantic audit: a schema cannot prove that arbitrary text contains no desired state.
4. Bind the returned measurements to the ordered image-byte hashes. Reject incomplete answers or mismatched evidence before running condition checks. Imported evidence is validated using the same contract.
5. Check one frozen condition at a time on both images, with optional neutral measurements. Treat those measurements as fallible evidence and compare them against the pixels. Keep source/edited observations, status, and rationale.
6. Export complete/partial/absent/**unknown** without manufacturing a final label. Export local criterion fingerprints and probe signatures for later alignment audits. A shared concept map and learned tree remain separate work.
7. Cache each validated request with its payload, template, schema, engine settings, and image identities. Reuse per-image neutral observations when only the other image changes. Persist completed work after interruption; use a new checkpoint namespace for an independent repeat.

A saved neutral artifact cannot be reused against different or swapped image identities. Regenerating or reconstructing an artifact from correctly bound per-image observations may explicitly reorder the pair. Compilation fidelity is also separate: binding a fitted criterion to a prompt records its origin; it does not prove the criterion preserves the prompt's meaning.

## Offline evidence

The tests cover prompt/instruction invalidation, changed image bytes, image ordering, malformed and incomplete answers, removal of obsolete IDs, absence of feedback records in checker inputs, preservation of unknown, checkpoint restoration, fresh namespaces, and recovery after a failed second-image call. Existing decomposition and component regressions also run without model calls. Verification: `pytest tests/unit/calitree tests/unit/calibration/test_calitree_components.py -q` completed with **205 passed, 23 skipped**; live experiments remained skipped. Python compilation, documentation links, and `git diff --check` also passed.

A real-artifact replay used the saved J01/J16 neutral answers and selected condition responses through the new observer/checker path:

| Case | Saved responses replayed | Result | New provider calls |
| --- | --- | --- | --- |
| J01 | 2 observations + 3 checks | no | 0 |
| J16 | 2 observations + 3 checks | partial | 0 |

The replay establishes migration and execution compatibility only. It is not another successful model draw and must not be added to an accuracy or repeatability denominator. Its full output is in `.cache/calitree-tests/assumption3-offline-neutral2-20260928/results.json`.

## Cost-controlled experimental ladder

Each batch is a separate decision gate. Do not run the full ladder automatically merely because the preceding command exited successfully.

| Gate | Frozen inputs and variable under test | Planned calls before format repairs | Decision |
| --- | --- | --- | --- |
| A: two cases | Saved prompts, criteria, pixels; compare fresh condition checks with and without saved neutral evidence | 12 condition checks | Inspect every condition and both final labels. Advance only if the neutral arm retains both intended case decisions, introduces no unsupported decisive observation, and is no worse than the direct-check arm. A tie supports feasibility, not superiority. |
| B: same two cases | Same typed probes and criteria; regenerate per-image observations and recheck | 4 observations + 6 checks = 10 | Inspect whether the decisive evidence and both labels survive without relying on one favorable saved observation. Any contradiction or decisive unknown triggers diagnosis before expansion. |
| C: modest expansion | Keep J01/J16; add J09 watercolor, J13 egg, J22 expression, J29 spatial relation | Preflight from actual frozen condition/probe counts | Include the positive control and different operations. Audit existing neutral-probe provenance before reuse; do not fabricate missing artifacts. Compare case outcomes and atomic findings, not just pooled accuracy. |

These gates are development criteria, not statistical evidence of broad stability. If a criterion is revised using the observed target, begin a new fitted revision and repeat its checks; do not call it independent validation. If a checker fails, separate plan meaning, target identity, visual evidence, and reducer errors before spending more tokens on prompt revisions.

The runner defaults to a no-call preflight:

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_probe \
  --output-dir .cache/calitree-tests/assumption3-bound2-next \
  --case J01 --case J16
```

The default compares `direct` and `neutral` condition-check arms. Here `direct` means checking frozen conditions **without neutral evidence**, not raw-prompt judging. `neutral` reuses saved neutral evidence, so it tests checker repeatability conditional on those observations. Select `--arm fresh-neutral` for gate B. `--executor legacy` permits comparison with the prior experiment harness; fresh neutral execution requires the default `bound` executor.

Actual execution additionally requires `--live`. The default total limits are 14 requests and 16,000 completion tokens, with up to 4,096 completion tokens reserved before each call and at most one format repair per request. A request cannot start unless its reservation fits. This may stop before all planned checks finish. Failed/interrupted calls retain their reservation; resuming keeps the spent allowance and completed checkpoints. Prompt tokens are recorded separately; the completion allowance is not a dollar-cost ceiling. Provider failure stops the batch rather than repeating failures across cases.

The first live attempt obtained no model outputs because provider connectivity failed. A subsequent network request required explicit payload/destination authorization. The user then approved the two-case GPT-4.1 pilot to `api.openai.com`; it completed successfully. No larger cohort has been tested.

## Approved live comparison and evidence-only follow-up

The first batch used the frozen fitted criteria, identical verified image bytes, GPT-4.1 at temperature zero, and saved neutral observations. All 12 condition responses were valid; no format repairs were needed.

| Case | Human target | Fresh checks without neutral evidence | Fresh checks with saved neutral evidence | Difference from selected fitted checks |
| --- | --- | --- | --- | --- |
| J01 | no | partial | no | Without neutral evidence, person/action association changed absent → partial; neutral evidence restored absent. |
| J16 | partial | yes | yes | Both arms changed extraction partial → complete. |

On these two selected difficult cases, the fresh direct-condition arm matched **0/2**, and the saved-neutral arm matched **1/2**. The historical fitted 2/2 result was not reproduced. These are named-case development outcomes, not generalization estimates. The baseline here is decomposed condition checking without neutral evidence, not a fresh raw-prompt evaluation.

The J01 direct checker described hand contact as uncertain/proximity yet returned partial despite the frozen criterion explicitly requiring visible contact. The J16 neutral checker asserted an unambiguous gap and claimed the measurements agreed. The actual neutral reports described fish partly inside and partly above the can, without establishing a distinct piece or visible gap. This exposes a specific failure: the image-aware checker can add unsupported certainty while applying the requested criterion.

The remaining two calls within the approved 14-call limit tested **evidence-only interpretation** of the two decisive conditions. `evaluate_neutral_condition(...)` receives the same bound observations and frozen criterion, but no images. It must distinguish reported facts from unreported relations and preserve unknown when the evidence cannot select a state. Image-byte identities are still validated locally. No human feedback or previous grading output is sent.

| Decisive condition | Image-aware check with saved evidence | Evidence-only check with the same evidence | Evidence-only rationale |
| --- | --- | --- | --- |
| J01 person/action association | absent | absent | Reports explicitly deny person–curtain contact and place the hands on another object. |
| J16 extraction/separation | complete | partial | Reports support lifting/partial extraction but do not establish a fully distinct piece or an unambiguous gap. |

This is an exploratory follow-up selected after seeing the failed pilot, not a preregistered superiority result. Only the decisive conditions were rechecked: **do not report 2/2 full-case accuracy for this follow-up** by silently borrowing the other conditions. It suggests separating observation from criterion interpretation deserves a fresh-observation check before further development.

The combined approved batch used **14 calls, 3,458 completion tokens, and 20,749 prompt tokens**. There were no provider failures or format repairs. The main 12-call result and the follow-up are separate artifacts and share one persisted budget counter:

- `.cache/calitree-tests/assumption3-approved2-20260928/results.json`
- `.cache/calitree-tests/assumption3-approved2-20260928/neutral-only-diagnostic/results.json`
- `.cache/calitree-tests/assumption3-approved2-20260928/budget.json`

A separately approved six-call repeat regenerated the four single-image observation reports and rechecked only these two decisive conditions. It completed with **6 calls, 1,759 completion tokens, and 5,225 prompt tokens**, below its 8,000-completion-token allowance. No schema repairs were allowed or needed. J01 again returned **absent** and J16 again returned **partial**. The report is `.cache/calitree-tests/assumption3-fresh-evidence2-20260928/results.json`, with separately saved per-case neutral artifacts and exact request histories.

Across the two evidence-only passes, the decisive statuses match, including one pass using freshly regenerated observations. However, the fresh J16 SOURCE count report describes at least three visible fish, whereas the older neutral report described one clearly visible fish. The stable final condition must not conceal this measurement disagreement. The observations are model reports, not independent ground truth; the count requires review before being treated as a reusable feature.

Across both approved batches, successful requests total **20 calls, 5,217 completion tokens, and 25,974 prompt tokens**. These totals exclude the earlier failed connectivity attempt. No raw-prompt optimization, criterion rewriting, larger cohort, or additional unapproved batch was run.

### Current decision and next gate

Keep the evidence-only interpretation path as an experimental component. Do not replace the default executor or claim whole-case accuracy from two selected conditions. The full-case continuation below now covers all three criteria and confirms unresolved coverage and attribution problems, especially preservation. Add or audit neutral scene-context coverage before asking an evidence-only checker to judge preservation; otherwise it should return unknown. Review the inconsistent count observation separately rather than tuning the final label around it.

Only after full-case evidence coverage, unknown handling, and the relevant atomic measurements pass should the cohort grow modestly to the four additional cases named above. This is a more conservative expansion gate than advancing solely because the two decisive labels matched. Further paid calls require a new allowance; all three approved request limits have been used.

## Full-case continuation completed

The reusable `evaluate_neutral(...)` method now composes all condition checks using one bound neutral-evidence artifact. It retains exact single-condition checkpoint identities, exports local features and unknown condition IDs, and makes no implicit choice of grading reducer. The experiment runner reports an unresolved label when any condition is unknown; it does not count unknown as a correct `no` under the historical reducer.

The no-call preflight against the completed fresh-observation run verified two compatible cached checks and exactly four missing checks:

| Case | Reused | Missing |
| --- | --- | --- |
| J01 | Person/action association | Curtain state; scene preservation |
| J16 | Extraction/separation | Can identity; scene preservation |

The user approved the separate allowance of four text-only GPT-4.1 calls and 8,000 completion tokens. The continuation completed all four checks, reusing the two decisive-condition checkpoints. It used no new images, observer calls, compilation, or criterion fitting. Actual usage was **4 calls, 1,163 completion tokens, and 5,318 prompt tokens**, with no format repairs or provider failures.

| Case | Full condition vector | Conservative full-case result |
| --- | --- | --- |
| J01 | Curtain state: unknown; person/action: absent; preservation: partial | Unresolved |
| J16 | Extraction: partial; can identity: complete; preservation: unknown | Unresolved |

**Resolved coverage is 0/2.** This is not a claim that the system made two wrong labels, nor that it achieved 2/2 accuracy. It abstained under the experiment's all-conditions-known reporting rule. Although the historical conjunction could output `no` for J01 from the absent action condition, that would not establish that its entire feature row is measured reliably. The learned-feature objective requires retaining the missing evidence rather than hiding it behind a correct final label.

The new checks identify concrete defects:

- **J01 curtain state:** the neutral reports describe curtain presence and color, but the EDITED report does not measure window coverage or remaining gaps. The evaluator correctly returns unknown rather than inferring closure from the instruction.
- **J16 preservation:** the reports focus on the fork, fish, and can, with no sufficient account of the unrelated background. The evaluator correctly returns unknown.
- **J01 preservation:** the text-only evaluator says the SOURCE had two curtains, calls its background stable/unchanged, and treats an object mentioned only in the EDITED report as a scene change. The SOURCE reports do not establish the first two claims, and omission from one report does not establish absence in that image. Its `partial` status is therefore not trustworthy evidence of preservation, even though it does not resolve the overall case.
- **J16 can identity:** the evaluator returns complete despite the reports describing the SOURCE can as held above a plate and the EDITED can as on a plate. Sparse descriptions and viewpoint uncertainty do not independently establish unchanged position or identity. This needs audit rather than treating `complete` as proven truth.

The expansion gate remains closed. The next algorithm revision should improve **property coverage and evidence attribution**, not just strengthen grading instructions: collect task-neutral window-coverage and scene-context measurements, distinguish unreported from observed-absent facts, and keep interpretation claims separate from quoted observations. Evidence quotations can verify attribution but do not by themselves establish visual truth or logical entailment. Any new prompt/probe revision requires another disclosed small-set run before expanding.

Artifacts: `.cache/calitree-tests/assumption3-complete2-20260928/results.json`, `calls.jsonl`, and `verification.json`. Across all three successful approved batches: **24 calls, 6,380 completion tokens, and 31,292 prompt tokens**. No additional paid batch or larger cohort was launched.

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_complete \
  --from-run .cache/calitree-tests/assumption3-fresh-evidence2-20260928 \
  --output-dir .cache/calitree-tests/assumption3-complete2-20260928
```

Without `--live`, this only validates bindings and counts missing checks; it initializes no provider and creates no new run directory. Before live execution, it requires the approved request allowance. The runner copies compatible checkpoints into a separate output directory, leaving the original observation run intact, and persists the new allowance independently. Focused verification after this change: **23 tests passed**, covering partial-check reuse, unknown handling, no-call planning, bindings, budgets, and interruption recovery.

## Coverage and attribution revision tested

The next revision changes two components in response to the full-case failures:

1. **Supplement the measurement coverage.** New fixed neutral properties include `coverage` (covered/uncovered regions and visible gaps between an object and reference) and `scene_inventory` (major objects, layout, background, lighting, and occlusions in one image). J01 adds curtain/window coverage plus scene inventory. J16 adds can existence/attributes plus scene inventory. These observers still receive only neutral questions and one image, never the instruction, desired outcome, role, or human label.
2. **Attribute interpretation to actual measurements.** `attribution="citations"` makes the condition evaluator return measurement IDs, status, support state, unresolved evidence, and an interpretation rationale. Python builds the source/edited observation fields from the **complete original answers**, including uncertainty, rather than accepting invented paraphrases. Invalid or duplicate IDs fail validation. A known status requires references from both roles and no declared unresolved evidence; insufficient/conflicting support requires unknown with an explanation. This enforces structural consistency, not semantic entailment or visual truth. The rationale remains explicitly unverified interpretation.

`NeutralEvidence.combine(...)` merges supplemental and prior evidence only when the ordered image-byte identities agree. It retains the original records and rejects conflicting measurements for the same probe instead of silently choosing a favorable answer. This permits four new observer calls without repeating the six original property probes. Changed combined evidence invalidates earlier condition checks, so all six criteria are re-evaluated in the cited mode. The old summary mode and its checkpoints remain available.

The prepared experiment is **10 calls maximum**: four supplemental single-image observations and six text-only condition evaluations, with a separate 12,000-completion-token cap and zero format repairs. It uses the same two cases, prompts, and fitted criteria. It performs no optimization, compilation, new label feedback, or cohort expansion. The new observer coverage and attribution change together, so any improvement would be a result of the joint revision, not evidence isolating one component's causal effect.

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_coverage \
  --from-run .cache/calitree-tests/assumption3-complete2-20260928 \
  --output-dir .cache/calitree-tests/assumption3-coverage2-20260928
```

The preflight passed without model calls. Live execution requires the separately requested allowance and `--live`. Both cases must have supported full-condition observations, traceable interpretations, and no concealed unknowns before calling this promising enough to expand. A superficially correct label with unsupported preservation claims does not pass that gate.

Offline verification after the revision: **218 passed, 23 skipped**, plus Python compilation and `git diff --check`. Tests include exact measurement materialization, mode-specific caches, invalid references, unknown consistency, contradictory evidence rejection, added-probe binding, restart reuse, and the complete four-observation/six-check composition using deterministic engines. The approved live results and the subsequent offline revision are recorded below.

## Ten-call revision outcome and annotation policy

The approved coverage/citation run consumed **10 calls, 2,991 completion tokens, and 15,670 prompt tokens**. All provider responses arrived; two failed semantic schema validation. No responses were retried. After each rejection, the remaining independent planned conditions were attempted under the same shared ten-call counter; the original failed run and continuation artifacts remain separate.

| Case | Condition | Outcome under the frozen cited-v1 protocol |
| --- | --- | --- |
| J01 | Curtain coverage | Valid absent; new coverage reports described largely uncovered window panes in both images. |
| J01 | Person/action association | Valid absent. |
| J01 | Preservation | Rejected: supported partial with a nonempty unresolved-evidence list. The response still asserted an unestablished original curtain count. |
| J16 | Extraction | Rejected: supported partial with unresolved separation ambiguity. |
| J16 | Can identity | Valid unknown. |
| J16 | Preservation | Valid unknown. |

Neither case yields a validated full-case label. Supplementary observations improved coverage for the curtain condition, but they did not establish a reliable reusable feature set. The cohort remains at two cases.

The J16 rejection exposes a response-contract issue: the existing partial criterion explicitly permits ambiguous separation. That uncertainty can support partial without blocking status selection. It should be distinguished from unresolved evidence that prevents choosing between statuses. The **cited-v2** revision therefore adds `non_decisive_uncertainties` separately from `unresolved_evidence`. A known status can retain the former; decision-blocking gaps still require unknown. The version, schema, and template change invalidate prior cited checks. Rejected cited-v1 outputs have not been retroactively changed into valid predictions. The subsequent live check is recorded below.

The experiment runner now records an invalid model response as a failed case and can continue independent cases within the same allowance. It preserves the raw response and failed check identity. Provider failures, input-binding errors, budget exhaustion, and cancellation still stop the run. Restarting does not silently retry an already recorded failed case.

The user also clarified that human annotations are **not a golden standard**. Future comparisons should be described as agreement with provisional annotations unless adjudication supports a stronger correctness claim. Explicitly uncertain annotations are quarantined from fitting and primary agreement metrics, preserving originals and reasons; no case is automatically excluded because a model disagrees. J01 and J16 remain unreviewed development cases, not newly certified targets or automatically discarded failures. Their previously fitted criteria remain disclosed as label-influenced.

Artifacts are under `.cache/calitree-tests/assumption3-coverage2-20260928/`: `results.json`, `continuation-results.json`, `remaining-results.json`, their call histories, and the original source snapshots. Across all four successful-provider batches: **34 calls, 9,371 completion tokens, and 46,962 prompt tokens**. No further paid run is authorized by the used allowances.

Offline validation after annotation quarantine and cited-v2 changes: **424 regression tests passed, 23 live tests skipped**. A subsequent focused run covering the explicit uncertain category and partial-compatible uncertainty passed **65 tests**. Annotation quarantine is available in workflow/API metadata; no automatic annotation adjudication or new frontend review editor was added.

## Six text-only cited-v2 checks completed

The user approved six text-only GPT-4.1 checks with an 8,000-completion-token cap. This run restored the saved neutral observations, including the supplemental coverage measurements, and evaluated all six frozen criteria under cited-v2. It sent no images, human labels, rubric-conflict history, or previous judgments. The criteria themselves remain historically label-influenced; omitting labels from this request does not make the experiment independent of prior fitting.

All **6/6 responses passed structural validation**, without retries or repairs. Usage was **1,996 completion tokens and 14,074 prompt tokens**. Provider histories confirm zero media attachments and the expected `api.openai.com` destination. Local image hashes in the condition log bind the evidence; they do not indicate images were attached to these calls.

| Case | Condition statuses | Full feature-row coverage | Full-case result under the existing all-known rule |
| --- | --- | --- | --- |
| J01 | Curtain state: absent; person/action: absent; preservation: unknown | 2/3 known | Unresolved |
| J16 | Extraction: partial; can identity: unknown; preservation: unknown | 1/3 known | Unresolved |

The J16 extraction response now correctly places ambiguity permitted by its partial criterion in `non_decisive_uncertainties`, leaving the decision-blocking list empty. This demonstrates that the revised contract can express the intended distinction. It does **not** verify that the fish observation or fitted criterion is correct. Across both cases, 3/6 condition statuses are known and **0/2 full cases are resolved**. No full-case agreement rate is available; this is neither 0% accuracy nor evidence that either human annotation is wrong.

Inspection of the saved evidence and rationales still finds limitations:

- J01 curtain reports support a largely uncovered window in both images. The checker interprets this as no progress, but the coarse descriptions do not establish a precise before/after coverage difference. Its status remains an interpretation to audit, not a verified measurement.
- J01 preservation is now unknown instead of asserting a supported partial change. However, its rationale describes sheer curtains as not present in SOURCE when the SOURCE report merely does not mention them. Valid citations have not eliminated omission-to-absence errors. The condition also needs a clearer boundary between the requested curtain change and unrelated scene preservation.
- J16 can identity remains unresolved because the reports describe a rectangular gold can versus a cylindrical green-labeled can. This could reflect actual change, viewpoint, or observer error. A single-image observer cannot explicitly certify cross-image identity; lack of such certification should not become an impossible evidence requirement.
- J16 preservation explicitly retains uncertainty about whether differing descriptions reflect real changes or reporting differences. Its rationale also draws on can attributes outside the cited scene-inventory answers, showing that valid citation IDs alone do not establish complete attribution.

The next development step is an evidence audit on these same images: check object correspondence, can shape, curtain coverage, and which region belongs to the allowed edit. Preserve unreported attributes as unreported, and separate correspondence from per-image descriptions. Do not keep rewriting the final checker to obtain the provisional human labels. Any revised observations or criteria need new versions and a disclosed fresh check. The gate for a larger cohort remains closed.

Annotation review remains separate: J01 and J16 are unreviewed development cases, not automatically quarantined because this evaluator abstains. If review finds an ambiguous task or unreliable target, retain the original record and mark its annotation uncertain with a documented reason; exclude that target from supervised fitting and primary agreement metrics. Unknown model features alone do not justify this decision.

Artifacts: `.cache/calitree-tests/assumption3-cited-v2-two-20260928/` contains `results.json`, `verification.json`, request and provider histories, the budget ledger, and hashed source snapshots. Verification checked all six reservations settled, zero repairs, allowed payload fields, zero media, source snapshot hashes, and token totals. Across the five completed approved batches: **40 calls, 11,367 completion tokens, and 61,036 prompt tokens**. The six-call allowance is exhausted; no larger cohort or further paid calls were launched.

## Original-image audit and paired-observer prototype

A subsequent Codex visual inspection loaded the original four local image files after verifying their SHA-256 bindings. It made no additional provider calls. This is an assistant inspection informed by earlier failures, **not independent human adjudication**, and does not replace any dataset annotation.

| Image evidence | Inspection finding | Consequence for the algorithm |
| --- | --- | --- |
| J16 can | Both images visibly show a rectangular open tin with a folded-back lid. The edited observer's cylindrical-can description is inconsistent with the visible outline. | An observation error can create a false identity conflict even when downstream interpretation correctly preserves uncertainty. Repair the measurement boundary before tuning grading. |
| J16 fish and fork | The source tin contains multiple visible elongated contents. The edited image has a conspicuous fish-like piece extending across the tin edge near the fork. Exact piece boundaries and separation are less clear. | Do not promote a fish-count narrative to a verified count or infer complete separation from salience. The exact meaning of a “piece” also needs care. |
| J01 curtains | Both images retain bright uncovered window regions; curtain appearance and arrangement differ visibly. | Largely open in both images does not establish an exact zero change in coverage. A comparison needs consistent regions and uncertainty about the overexposed boundaries. |
| J01 person | The person remains seated with hands extended; this inspection does not establish hand–curtain contact. | Retain uncertainty where a small contact cannot be resolved; do not infer the intended action from pose alone. |
| Scene context in both pairs | Major corresponding elements are recognizable, with changed framing, geometry, and local details. | A broad inventory cannot prove every unmentioned object unchanged. Separate correspondence and visible differences from the grading policy's permitted changes. |

The smallest next experiment changes observation rather than the grading prompt. `FrozenCriteriaExecutor.observe_neutral_pair(...)`, implemented in the existing consolidated executor, sees both images with neutral FIRST/SECOND identifiers and the same typed property questions. It returns per-image descriptions plus a comparison for each question. It receives no editing instruction, condition rubric, saved observer report, or human label. The comparison asks for visible correspondence and differences, keeping viewpoint/occlusion alternatives explicit. Joint viewing may improve correspondence but can also spread a hallucination across both descriptions; this must be tested rather than assumed.

The output is a distinct `calitree-neutral-pair-evidence-v1` diagnostic artifact, with ordered image hashes, probe identities, separate measurements, checkpoint identity, and an artifact hash. It is deliberately **not accepted as independent `NeutralEvidence`** or wired into the grader. No merged or corrected observations are synthesized from conflicting prior reports. Compilation and the default workflow executors are unchanged.

The prepared runner uses **two calls maximum**, one per existing case with two images each, **8,192 completion tokens total**, at most 4,096 per call, and zero repairs. It performs no condition checking or optimization. A no-call preflight succeeded; **39 focused tests passed**, covering pair roles, complete comparison coverage, replay, swapped-image invalidation, isolation from single-image evidence, no-call preflight, two-call runner recovery, and existing budget/decision-set contracts. The subsequent approved live result is below. The output directory is not created by preflight.

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_pair_observation \
  --from-run .cache/calitree-tests/assumption3-cited-v2-two-20260928 \
  --output-dir .cache/calitree-tests/assumption3-paired-two-20260928
```

Only after a new explicit allowance may this run with `--live`. Audit its reports against the images before adding a grading adapter: check can geometry and correspondence, distinguish a partial fish view from a certain piece count/separation, preserve uncertainty at the bright curtain boundaries, and avoid interpreting description omissions as changes. Neither matching provisional labels nor satisfying JSON validation passes this gate. This is still development on the original two cases, not cohort expansion.

### Approved paired-observer result: do not promote

The user approved the prepared two-call run. Both responses completed and passed structural validation, using **2,701 completion tokens and 2,617 prompt tokens**, with zero schema repairs. The paired observer received no labels, task instructions, prior reports, or grading criteria. No condition evaluator was called.

| Property | Paired result | Audit and consequence |
| --- | --- | --- |
| J16 can geometry | Rectangular open metallic can in both images | Corrects the conspicuous cylindrical-can error in the earlier single-image report. This improvement is confined to one property. |
| J16 fish position | Fish inside the can in both images; no visible spatial change, reported with low uncertainty | Misses the conspicuous fish-like piece at the tin's edge in the edited image. This fails the predeclared evidence gate. It cannot be accepted as a reusable fish-position feature. |
| J16 piece count | At least one visible piece, additional pieces uncertain | More cautious than an exact count, but repeats essentially the same description for both images and does not recover the missing position difference. |
| J01 curtain coverage | More inward coverage and narrower gaps in the second image | Differs from the earlier checker conclusion of no increase. The comparison reports low uncertainty even though both per-image descriptions report medium uncertainty at the bright boundaries. Requires review; do not choose the version producing a desired label. |
| J01 scene/body state | Nearly identical descriptions; other major locations said to be unchanged | The pair has visible framing and local differences. Broad sameness language suppresses differences and does not justify a preservation score. |

The per-image scene-inventory descriptions for J01 are verbatim identical, and its body-state descriptions are nearly identical; J16's fish-position descriptions are also verbatim identical. Identical wording is not itself proof of an error, but here it accompanies a missed visible change. The pattern is consistent with joint viewing encouraging copied descriptions or a bias toward sameness; this is a hypothesis, not a demonstrated causal mechanism from two calls.

An offline transport audit reconstructed message assembly without initializing credentials or making requests. It confirmed two ordered image blocks per case containing the exact original file bytes. The implementation does not resize these images or set an explicit image-detail override. Provider history's `n_media=4` includes the two FIRST/SECOND text blocks, not four images. Raw HTTP payloads and provider-side image processing were not recorded, so this audit does not prove how the provider internally processed the images. The available evidence supplies no basis for attributing the failure to a local resize or swapped images.

**Do not add a grading adapter or expand the cohort on this result.** Retain paired observation as a failed diagnostic prototype. The next algorithm change should target the missed atomic measurement: measure each image's object boundaries/positions independently, retain locations and uncertainty, and only then compare the bound measurements. A broad joint description is not a reliable replacement for those measurements. Before another paid test, prepare an explicit property-level audit with positive visible changes and unchanged controls; do not use the final human label as the criterion for selecting an observation.

Both dataset annotations remain unreviewed. No annotation was changed, quarantined, or certified by this experiment; observer failure is not evidence of an incorrect human target. No new final predictions or accuracy measurements were generated.

Artifacts are in `.cache/calitree-tests/assumption3-paired-two-20260928/`, including `results.json`, `verification.json`, the call/budget histories, and source snapshots. Total recorded successful completions across the six approved batches are **42**, with **14,068 completion tokens and 63,653 prompt tokens**. These are engine-level recorded successes; the transport supports automatic HTTP retries, which the experiment ledger does not independently enumerate. A future strict HTTP-attempt cap needs transport-level enforcement. The current two-call allowance is exhausted, and no further paid calls were made.

## Independent localization experiment

The failed paired comparison motivates a narrower J16-only observation test. `FrozenCriteriaExecutor.localize_neutral(region_names, image_path=...)` measures one image without a role, companion image, edit instruction, rubric, previous description, or human label. The prepared selectors are **can opening**, **all visible fish material**, and **fork tines**. They name regions rather than desired outcomes. Selector choice was informed by the observed failure and is development intervention, not an independent evaluation design.

Each measurement exports visibility, a visible-extent bounding box, description, and uncertainty. Coordinates are `[left, top, right, bottom]` normalized to 0–1000. Unknown regions may have null boxes; visibly absent regions must. Validators reject malformed, inverted, nonfinite, or out-of-range boxes and incomplete target coverage. The artifact binds image bytes, selectors, schema, template, and engine settings. It is **not a segmentation**, and overlapping envelopes do not prove contact, physical separation, or extraction. No conversion into condition truth or overall grades is implemented.

The existing observation runner now has `--mode localize-j16`, with **two single-image calls**, **4,096 completion tokens total** (2,048 maximum per call), and zero repairs. It preserves the original evidence and the failed paired run. Before another grading experiment, audit boxes over the original images: whether they enclose the visible fish extent rather than just the tin contents, whether the can opening is distinguished from its folded lid, and whether fork-tine localization retains occlusion uncertainty. A format-valid box or agreement with the provisional class label cannot pass this visual gate.

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_pair_observation \
  --mode localize-j16 \
  --from-run .cache/calitree-tests/assumption3-cited-v2-two-20260928 \
  --output-dir .cache/calitree-tests/assumption3-localized-j16-20260928
```

The no-call preflight passed and created no output directory. **86 focused offline tests passed** across observation contracts, experimental runners, engine contracts, strict output handling, and budgets. They establish shape/binding/recovery behavior, not localization accuracy. The user subsequently approved the two-call allowance; the results follow.

The transport allowance gap found during the prior audit is now fixed for bounded experiments. Package `LMEngine` supports an optional `max_http_attempts` cap shared across retries and endpoint fallbacks. `BudgetedEngine` sets it to one per reserved operation. With a cap, automatic redirects are disabled; failures keep their completion reservation and cannot silently retry or switch mirrors. Offline timeout, 429, 500, 400, and redirect tests verified one HTTP invocation and no retry sleep. Ordinary engine construction keeps its previous retry defaults. This changes future execution, not the uncertainty about historical raw HTTP-attempt counts.

### Approved localization result: coordinates fail visual inspection

The two single-image calls completed with **384 completion tokens and 1,412 prompt tokens**, with no repairs or failures. Both histories record `max_http_attempts=1`, one image, and `api.openai.com`. Only the three neutral selectors were sent. Image and artifact hashes, source snapshots, budget settlement, and request fields passed local verification.

| Target | FIRST box | SECOND box | Reported uncertainty |
| --- | --- | --- | --- |
| All visible fish material | `[420, 222, 545, 304]` | `[410, 252, 527, 340]` | Low for both |
| Can opening | `[414, 186, 561, 263]` | `[410, 252, 527, 292]` | Low for both |
| Fork tines | `[484, 217, 537, 265]` | `[484, 263, 540, 304]` | Low for both |

Plotting these coordinates exactly as requested—x scaled by image width/1000 and y by image height/1000—places **all six boxes on the draining-board background**, above the can, fish, and fork. None encloses its named region. This is an assistant visual audit, not an independently annotated IoU benchmark. The rendered plot is `.cache/calitree-tests/assumption3-localized-j16-20260928/localization-audit.png`.

The descriptions sound plausible while their spatial grounding is wrong. All boxes remain inside the legal coordinate range and satisfy the schema, so structural validation cannot detect this failure. Their low-uncertainty reports are also unreliable for accepting these observations. The SECOND description again misses the conspicuous piece extending across the tin edge. Do not repair the coordinates with an unvalidated scale/offset chosen after looking at the image, and do not turn these boxes into learned-tree features.

**The localization gate failed.** No condition grading, overall prediction, training, merge acceptance, or annotation change followed. Both general paired descriptions and prompted coordinate generation have now failed on this same difficult case. Further prompt-only variants need stronger justification; the next useful step is a separately verified grounding mechanism or reviewed regions, followed by an independent check of the observation. This is a limitation of the tested observation procedures, not proof that the broader decomposition idea cannot work or that the human target is wrong. The cohort remains unchanged.

Artifacts in `.cache/calitree-tests/assumption3-localized-j16-20260928/` include results, verification, the overlay, budgets, request histories, and source snapshots. Cumulative recorded successful completions across the seven approved batches: **44 calls, 14,452 completion tokens, and 65,065 prompt tokens**. The new two-call allowance is exhausted. No additional paid calls were made.

## Grounding resource audit and unreviewed region proposals

The repository audit found no existing detector/segmenter implementation in the relevant core/database code, and the active project interpreter has no `cv2`, `torch`, `transformers`, or `skimage` installation. The local J16 directory contains the source and editor outputs; its AURORA metadata has pair-level fields and human scores but no object-region annotations. This is a statement about the inspected project environment, not the availability of external tools. No packages or model weights were downloaded.

A cheaper diagnostic can separate visual grounding from criterion interpretation by supplying reviewed regions. Six **assistant-selected, unreviewed proposals** were prepared for the same three J16 regions and saved in `.cache/calitree-tests/assumption3-region-proposal-j16-20260928/proposal.json`. The accompanying `region-proposals.png` shows each proposed envelope separately over the original image. The proposal retains exact image hashes, actual image sizes (456×256 and 512×320), pixel coordinates, origin, and `reviewed_by: null`. These boxes were selected by visual inspection, not by rescaling the failed model boxes.

The user has been asked whether these envelopes are adequate for a controlled diagnostic or whether to pursue automatic grounding only. **No review result has been assumed.** Region review concerns visible extent and occlusion; it neither certifies the dataset class target nor proves contact, separation, or intent. No proposal is currently accepted as a measured feature, and no new provider request has been made.

If reviewed regions are used, report the result as **manually grounded interpretation**, separate from automatic decomposition. This can diagnose whether interpretation still fails when object location is supplied, but cannot establish automatic localization or replace the original end-to-end assumption. Keep the automatic failure results and the same cohort denominator visible. A production grounding method would still require its own verification before expanding or training on those features.

### Automatic grounding candidate identified (research stage)

Read-only research identified **Grounding DINO Tiny** as a concrete local detector candidate. The official Transformers integration accepts an image and text categories, then returns boxes, scores, and associated text; its postprocessor takes the actual image height and width to produce image-space boxes. This supplies a detector-based alternative to asking a generative checker to invent coordinates. It does not establish that the detector can distinguish a tin opening, fork tines, or this edited fish. [Official integration documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino).

The inspected official checkpoint is **689 MB**, published as safetensors under Apache 2.0 at revision `a2bb814dd30d776dcf7e30523b00659f4f141c71`, with SHA-256 `1a2412ef99bd74bcd3c2a246fa1e48581f8889a1300c9051974741314fc042f3`. Runtime dependencies would add disk use; the checkpoint size is not an estimate of total installation size or peak memory. [Official checkpoint file](https://huggingface.co/IDEA-Research/grounding-dino-tiny/blob/a2bb814dd30d776dcf7e30523b00659f4f141c71/model.safetensors).

The current environment is Python 3.13.2 on arm64; PyTorch and Transformers are absent. No compatibility, speed, or J16 detection result is claimed. No model, weights, or runtime packages were downloaded during this research, and no images were sent to a remote detection service.

A local trial should use an isolated environment and pinned checkpoint, keep runtime inference local, start with the two J16 images, and retain all detections and their scores. Distinguish whole-object detection (can/fish/fork) from part localization (opening/tines); a box for the can is not automatically a box for its opening. An empty detector output is unknown, not proof of absence. Detector scores are not calibrated probabilities of semantic correctness. Compare overlays with the original images and the still-unreviewed region proposals before any grading integration. This is an alternative grounding experiment, not a justification to expand the cohort.

### Local detector installed and tested on J16

The subsequent step installed an isolated `.venv-grounding` with PyTorch 2.7.1, torchvision 0.22.1, Transformers 4.51.3, huggingface-hub 0.30.2, and Pillow 11.2.1. Public packages and the pinned checkpoint were downloaded; the model checksum matched the official value above. The regular project interpreter was not modified. `run/setup_calitree_grounding.sh` makes setup explicit. It does not run during ordinary training or inference. The isolated setup/runner uses Python 3.11+ (`hashlib.file_digest`); the actual tested interpreter was Python 3.13.2 arm64.

The diagnostic runner `tests/unit/calitree/assumption3_detector.py` loads only local safetensors/configuration, disables remote code and hub access for inference, and runs on CPU with four PyTorch threads. Image hashes, model-file hashes, thresholds, package versions, query, and runner snapshot are retained. All returned detections are saved, including duplicates and vague text phrases. No human labels, fitted conditions, previous model descriptions, or proposed region boxes are supplied to the detector.

Two local queries were run over the same J16 image pair, **four image inferences total, zero paid calls**:

| Query | First-image findings | Second-image findings | Decision |
| --- | --- | --- | --- |
| `a fish. a can. a fork.` | Fish box broadly covers the tin; fork proposals overlap the fork but vary in extent. “Can” selects the green container in the sink. | A fish box tightly covers the conspicuous edited fish piece; duplicate broader fish/fork proposals remain. “Can” again selects the wrong container. | Encouraging edited-fish grounding; target identification is incomplete. |
| `an open rectangular metal tin. pieces of fish. a fork.` | Fish remains broadly localized; tin boxes include a large region or nearly the whole image. | Fish piece is localized again; tin boxes remain much too broad, and multiple fork extents remain. | More specific description does not resolve the tin. Do not accept a full feature row. |

The second query was chosen after inspecting the first query's wrong-container detection, using visible object descriptors rather than a desired class label. It is a disclosed development revision, not independent replication. Each image's preprocessing/inference/postprocessing took approximately **1.5–1.9 seconds** in this run, excluding model loading and setup. This is a measurement on this machine, not a throughput guarantee.

Unlike the prompted-coordinate boxes on empty background, the detector supplies a plausible location for the edited fish. However, this visual audit remains assistant inspection, not annotated detection accuracy, and fish-location consistency does not prove extraction, separation, or a final `partial` label. The tin-target error prevents the full grounding gate from passing. Detector scores must not be treated as correctness probabilities; whole-object boxes do not establish part boundaries.

Saved runs:

- `.cache/calitree-tests/assumption3-detector-j16-20260928/`: first query, full detections, overlay, manifest, source snapshot, verification.
- `.cache/calitree-tests/assumption3-detector-specific-j16-20260928/`: second query, the same artifacts, plus `environment.txt` recording all installed package versions.

Reproduce the second run in a new output directory after explicit setup:

```sh
CALITREE_GROUNDING_PYTHON="$PWD/.venv/bin/python" bash run/setup_calitree_grounding.sh
.venv-grounding/bin/python tests/unit/calitree/assumption3_detector.py \
  --from-run .cache/calitree-tests/assumption3-localized-j16-20260928 \
  --model-dir .cache/calitree-models/grounding-dino-tiny-a2bb814 \
  --output-dir .cache/calitree-tests/assumption3-detector-specific-j16-repeat \
  --query 'an open rectangular metal tin. pieces of fish. a fork.' --run
```

Omit `--run` for a no-model preflight. Two focused offline tests passed for preflight/no-output behavior and rejecting changed image bytes before model loading. The two real CPU runs and inspected overlays provide the substantive evidence; those unit tests do not prove detection correctness. No grading integration, cohort expansion, or annotation changes followed. The manually proposed regions remain unreviewed. Paid-call totals remain **44 recorded completions, 14,452 completion tokens, and 65,065 prompt tokens**.

### Target binding: relation text is not relation evidence

A bounded local follow-up recorded three queries before execution: `a can of fish.`, `a tin can.`, and `a food container.`, with unchanged detection/text thresholds of 0.25. The same two J16 images were used, for **six additional local image inferences** and zero paid calls. The plan is `.cache/calitree-tests/assumption3-detector-binding-plan-20260928.json`; each query has its own `assumption3-detector-{can-of-fish,tin-can,food-container}-j16-20260928` run directory. The combined inspected overlay is `.cache/calitree-tests/assumption3-detector-binding-queries-20260928.png`.

None resolves the tin reliably. “Can of fish” still returns the green sink container as “can” and separately finds the edited fish. “Tin can” primarily covers the sink or broad regions; “food container” also returns sink/plate-scale boxes. A phrase supplied to the detector does not establish the relation between its returned objects. No threshold was tuned to remove unfavorable detections, and no additional query was tried in this follow-up. Total local detector work is now **ten image inferences on J16**, with the earlier paid totals unchanged.

The new reusable `screen_grounding_candidates(...)` helper explicitly separates role proposals from semantic truth. It takes image-bound candidate boxes, caller-assigned roles, and declared necessary overlap constraints. It returns all compatible assignments and rejection reasons, with states for missing candidates, incompatible proposals, ambiguous proposals, or one unverified proposal. **Every state retains condition status unknown**: passing a 2D screen does not verify identity, physical contact, containment, or a label. Detector scores do not choose a winning assignment.

The screen was replayed over the original detector query without new inference. On the SOURCE, a diagnostic fish-in-container overlap precondition rejects both assignments using the distant sink-container candidate. On the EDITED image, only fish/fork overlap was required: **nine assignments remain ambiguous**. Fish/container overlap was deliberately not imposed after extraction, since a successful edit may place the fish outside the container. This distinction prevents the screen from inventing an incorrect postcondition. The preconditions themselves remain explicit development assumptions, not independently measured facts.

The replay is saved under `.cache/calitree-tests/assumption3-grounding-screen-j16-20260928/`. **37 focused tests passed**, including retention of unknown, missing candidates, ambiguous assignments, malformed coordinates, and the absence of an inherited container-overlap requirement after extraction. This is an improvement in failure detection and traceability, not an improvement in full-case accuracy. The helper is optional; it has not been inserted into the production grading workflow.

Automatic grounding remains unresolved, and the user review of the six region proposals is still pending. Further interpretation testing should use a reviewed grounding diagnostic or a separately verified grounder rather than treating these detections as accepted measurements. No class targets or review states were changed, and the cohort remains at the same cases.

### User region review and prepared interpretation diagnostic

The user subsequently responded **"looks pretty good to me"** to the six-region review. This is recorded as adequate approximate envelopes for the controlled diagnostic, not segmentation, piece-count or physical-relation annotations. The separate immutable review is `.cache/calitree-tests/assumption3-region-proposal-j16-20260928/review.json`; it binds the original proposal file and artifact hashes, the exact image hashes, the review text, and all six coordinates. The original `proposal.json` remains unchanged. Earlier statements that review was pending describe the state at those earlier experiment steps. J01/J16 class annotations remain unreviewed and provisional.

The concrete next request plan is `.cache/calitree-tests/assumption3-reviewed-regions-j16-plan-20260928/plan.json`. It contains the complete neutral questions, instructions, schema, image references and reviewed coordinates for **two independent single-image GPT-4.1 calls**, one per J16 image. Each request sends the original image, three approximate envelopes, and questions about fish position relative to the opening/rim, fork relation, and visible piece separation. It sends no task instruction, human label, fitted criterion, source/edited role, other image, or prior model answer. Image-plane overlap must not be treated as evidence of physical contact or containment.

The proposed allowance is two HTTP attempts total to `api.openai.com`, at most 2,048 completion tokens per call and 4,096 total, without repair calls or transport retries. **This allowance has not been authorized or used.** Preparation verified both image hashes and sizes, all six coordinate bounds, both new artifact hashes, and preservation of the original proposal. No model calls were made; paid and local-detector totals are unchanged.

After both observations are available, inspect their evidence and uncertainties against the originals before comparing them. Retain unresolved physical relations and invalid responses. Do not turn the result into an overall class prediction, change annotation eligibility, accept tree features, or expand the cohort automatically. This diagnostic can test whether interpretation improves with manually supplied locations; a single observation per image cannot establish repeat stability, and it cannot validate automatic grounding.

### Approved reviewed-region result: location hints do not resolve the observation error

The user approved the prepared two-call batch. Both independent single-image GPT-4.1 requests completed with no repairs or retries, using **810 completion tokens and 1,402 prompt tokens**. Each response contains all three requested observations and passes structural validation. The original plan remains unchanged as the preapproval record; the run manifest records the subsequent authorization.

| Observation | FIRST image response | SECOND image response | Audit |
| --- | --- | --- | --- |
| Fish position | Fish is contained within the opening; some edges are occluded. | Fish is contained within the opening and does not extend beyond it. | SECOND conflicts with the conspicuous fish material visible across the front/left tin edge. The important visual change is still missed. |
| Fork relation | Apparent contact; likely support or pressing, with depth unresolved. | Apparent contact; possibly supporting/lifting, but pressing versus lifting unresolved. | Overlap is described, but support and physical contact are not independently established. Preserve uncertainty. |
| Piece separation | Some boundaries suggest multiple pieces; exact count unclear. | A contiguous mass; distinct pieces cannot be separated confidently. | Ambiguity is retained. Neither response establishes a reliable exact count or fully separated piece. |

The audit is **assistant visual inspection**, not independently annotated relation truth. The reviewed boxes establish only adequate approximate location hints. They do not validate the response's containment/contact claims, and both responses use overlap to support stronger physical interpretations than the evidence establishes. Five of the six observations mark visibility `clear` despite qualifications about occlusion or unresolved depth. That field must not be treated as calibrated correctness.

**The observation gate failed.** Supplying reviewed coordinates did not correct the central edited-fish position error. This is a test of original images plus textual region hints, not a test with oracle segmentation or forced visual attention; it cannot distinguish ignored coordinates from incorrect visual interpretation. It also contains only one observation per image, so no repeat-stability conclusion follows. No final class prediction, accepted tree feature, merge result, cohort expansion, or annotation eligibility change followed. The J16 target remains provisional; this observer failure does not show that the human label is wrong.

Saved run: `.cache/calitree-tests/assumption3-reviewed-regions-j16-20260928/`, including manifest, runner/engine snapshots, full responses, request histories, budget ledger, and `verification.json`. Verification checked the frozen plan/review/image bindings and source hashes; offline wire reconstruction matched the budget's request hashes and retained the exact original JPEG bytes. Each history records one image, `api.openai.com`, `max_http_attempts=1`, and a normal stop. No explicit image-detail setting was supplied. Reconstruction verifies the local request path, not what a remote model attended to.

The reusable experiment runner is `tests/unit/calitree/assumption3_reviewed_regions.py`; its default preflight makes no model calls. Six focused offline tests passed across this runner and the prior paired/localization runner, including independent payloads, completed-call reuse, invalid-response preservation without repairs, and failure-reservation retention. These tests validate execution controls, not observation accuracy.

Cumulative paid totals are now **46 recorded successful completions, 15,262 completion tokens, and 66,467 prompt tokens** across eight approved batches. The two-call allowance is exhausted despite unused completion-token capacity. Local detector totals remain ten image inferences. Further automatic prompt variants are not justified by this result alone; first define independently reviewed, image-level relation observations (with unknown where needed) or test a materially different visual measurement procedure under a separately specified protocol. Do not use this failed observation row for training or automatically quarantine the underlying case.

### Atomic observation review prepared without new inference

The next step isolates the narrow projected-position proposition: **some visible fish material extends across the tin's front rim in this image**. The user was shown both original images and asked to review each separately as yes, no, or uncertain. This is a different review from accepting region envelopes; no answer has been inferred from the earlier region approval.

The pending packet is `.cache/calitree-tests/assumption3-atomic-review-j16-20260928/proposal.json`. It contains two exact-image-bound rows, an explicit target/reference/frame definition, true/false/unknown boundaries, and exclusions for physical separation, fork support, count, motion, and edit success. Both values and reviewer fields are null until actual answers arrive. The user has seen previous discussion, so any resulting review will be disclosed as non-blinded development review, not an independent benchmark. The packet binds the earlier review and observer result without including a target class or prefilled expected answer.

This supports a proposed decomposition revision: measure atomic per-image propositions, compare supported values, then interpret only the relations the compiled policy requires. In particular, a false→true change in projected rim crossing cannot directly imply successful extraction. No automatic observer improvement, feature acceptance, or accuracy is claimed by preparing this packet. No new paid or local model inference occurred.

### User-reviewed projected-position change and saved-observer comparison

The user explicitly answered **"No, it stays within the opening"** for the original image and **"Yes, it visibly extends across the rim"** for the edited image. These answers are recorded in `.cache/calitree-tests/assumption3-atomic-review-j16-20260928/review.json`, bound to the proposal, predicate definition, and exact image bytes. The pending proposal is preserved unchanged. This new review is restricted to image-plane rim crossing and leaves the case annotation and other physical relations untouched.

`comparison.json` in the same directory retains the relevant saved observer statements and their explicit manual coding:

| Image | User-reviewed rim crossing | Saved observer's claim | Agreement |
| --- | --- | --- | --- |
| Original | False | False: describes no fish material extending outside the opening. | Yes |
| Edited | True | False: says the material does not extend beyond the opening. | No |

Thus the saved observer agrees with **1/2 reviewed image-level observations** and reports an unchanged relation where the review identifies false→true. This is not a two-case accuracy estimate: there is one image pair, one local predicate, and a non-blinded development reviewer. No fresh repeat was run. Observer values were manually coded from explicit statements; no general rationale parser or semantic verifier is claimed.

The review makes the next algorithm gate concrete: an observer must recover these image-level values and their change without receiving the reviewed values or the case target. A new procedure must preserve unknown when the rim/target is unresolved and be inspected for whether it relies on image evidence rather than supplied box geometry. Only after fresh agreement should the same bounded procedure be repeated; expansion remains premature. Correct rim crossing alone still cannot establish the requested extraction, support, or count. Remaining relations need separate measurements or unknown states under the actual rubric.

This comparison used saved responses only, with **zero new model calls**. Paid totals remain 46 successful completions, 15,262 completion tokens, and 66,467 prompt tokens. Automatic feature acceptance and class-annotation review states are unchanged.

### Prepared focused-atomic observer variant (no new live calls)

`FrozenCriteriaExecutor.observe_atomic(...)` is now implemented in the consolidated `decomposition_twoway.py`. It asks one per-image proposition using the original image and a lossless RGB pixel crop of that same image. The model receives no coordinates, source/edited role, reviewed value, human class label, task instruction, or prior observation. Caller-supplied proposition fields define target, reference, frame, and true/false/unknown boundaries. The response records a value, visibility, visible evidence, and unresolved evidence, separately from condition grades. Known values with declared blocking gaps are rejected; unknown remains distinct from false. Semantic truth remains unverified.

The prepared J16 run is `.cache/calitree-tests/assumption3-focused-atomic-j16-20260928/`. The crop is the union of the three reviewed boxes plus padding equal to `ceil(0.25 * max(union width, union height))`, clamped to the source image. This same rule yields SOURCE `[189, 110, 297, 197]` (108×87) and EDITED `[179, 132, 351, 256]` (172×124). Both crops were visually inspected and retain the tin/fish/fork region. They are not rescaled or enhanced. Full images accompany crops to retain context. Cropping is manually guided, not a new automatic grounder.

Before model calls or checkpoint reuse, the executor verifies original/crop hashes, source identity, bounds, dimensions, and exact RGB crop pixels. Even a modified crop with a recomputed hash fails the source-pixel check. Request identity binds proposition, template, schema, engine settings, image bytes, and crop geometry. Artifacts have a distinct version and are not implicitly accepted as neutral evidence or inserted into grading/training.

**45 focused offline tests passed** across atomic observation, existing decision-set contracts, and the reviewed-region runner. Checks cover changed source/crop bytes, rehashed fake crops, incorrect geometry, altered propositions, cache reuse, known values with unresolved evidence, zero repair when disabled, exclusion of extra reference-answer fields, and no provider access/output writes during preflight. These tests do not prove that a model uses the crop or answers correctly.

The proposed live batch remains **two GPT-4.1 requests to `api.openai.com`, at most 2,048 completion tokens each / 4,096 total**, one HTTP attempt per call and no schema repair. This is a new protocol and needs a new allowance; no call has been made. It jointly changes input presentation and question granularity, so it is not a controlled crop-only ablation. Evaluate its saved true/false/unknown results against the separate reviewed values only after inference. A successful first pass would still need fresh repetition before broader testing, and would establish only this projected relation, not complete extraction or full-case accuracy.

Offline preparation command:

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_focused_atomic \
  --output-dir .cache/calitree-tests/assumption3-focused-atomic-j16-20260928 --prepare
```

Omitting `--prepare` gives a no-write preflight. Live execution must use the exact prepared manifest and source versions, with a separately approved allowance. Paid and local-detector totals remain unchanged.

A subsequent offline runner audit confirmed that the prepared source hashes still match, and that this run has neither a result file nor a budget ledger: live execution has not started. Two additional integration tests exercise the complete prepared-run path with deterministic fake responses and distinct source images. Completed execution consumes exactly two reservations, and replay makes no further engine calls; a failed first call retains its reservation and blocks silent resumption. The focused-atomic test file now has **11 passing tests**. No prepared protocol or model input changed during this audit, and no approval for the new batch has been received.

### Approved focused-atomic result: description changes, structured agreement does not

After explicit user approval, both requests completed without retries or repair calls, using **130 completion tokens and 1,870 prompt tokens**. Both returned valid structured responses with `visibility: adequate` and empty `unresolved_evidence` lists.

| Image | Reviewed projected rim crossing | Focused observer value | Observer description |
| --- | --- | --- | --- |
| Original | False | False | Visible material stays within the opening. |
| Edited | True | False | Fish is held above the rim by the fork and is clearly separated, so it does not cross the rim. |

Agreement is **1/2 image-level observations**, unchanged from the coordinate-hinted observer. The structured outputs still miss the reviewed false→true transition. However, the edited explanation no longer describes all material as contained inside the tin; it now describes fish above the rim. Preserve that qualitative difference without calling it a successful feature extraction. Its claims of fork support and clear physical separation are not established by the projected-position review or this experiment.

The result exposes a possible distinction between visual recognition and the interpretation of “across the rim.” It does not prove which component caused the false answer. Both descriptions and the fixed predicate/reference must remain intact for audit. In particular, do not reinterpret the returned false as true by reading its rationale, change the reviewed answer, or retrospectively change the tested definition. Any revised spatial predicate would require its own version and evaluation rather than being counted as success on this test.

**The structured observation gate failed.** No full-case grade, tree feature acceptance, automatic grounding claim, or cohort expansion follows. A single response per image cannot establish repeat stability. The user review remains a non-blinded, fallible development reference for projected position, separate from the original case annotation. No annotation eligibility was changed.

`verification.json` and `comparison.json` in the prepared run directory record the audit. Source snapshots, full-image/crop hashes, exact crop pixels, artifact hashes, checkpoint restoration, and request hashes passed verification. Offline reconstruction retained the exact image bytes and two image inputs per request (history `n_media=4` includes two text markers). Both calls used `api.openai.com`, the returned model was `gpt-4.1-2025-04-14`, and each logged `max_http_attempts=1` with normal completion. Checkpoint restoration was verified with provider generation disabled; the audit itself made no calls. This verifies local execution and provenance, not the model's attention or semantic correctness.

The new two-call allowance is exhausted. Cumulative totals across nine approved batches are **48 successful completions, 15,392 completion tokens, and 68,337 prompt tokens**. Local detector totals remain ten image inferences. Further paid repetition of this exact protocol is not justified as a stability test until the structured semantic mismatch is resolved; keep the same small cohort and address the distinction between visible projected extent and physical interaction before requesting another experiment.

### Projected-extent representation: distinguish outside from straddling (offline only)

The failed edited explanation conflated a possible physical separation from the rim with the requested projected extent. To address that representational gap, `FrozenCriteriaExecutor.observe_projected_extent(...)` now asks only for target/reference binding and possible 2D relations. It shares exact-crop validation with the prior atomic observer but uses its own template, schema, request keys, artifact version, and deterministic reducer version.

| Reported possibilities | Any visible extent outside opening | All visible extent inside opening | Extent straddles boundary |
| --- | --- | --- | --- |
| Inside | False | True | False |
| Straddling | True | False | True |
| Outside | True | False | False |
| Straddling or outside | True | False | Unknown |
| Inside or outside | Unknown | Unknown | False |
| Inside or straddling | Unknown | Unknown | Unknown |
| All three | Unknown | Unknown | Unknown |

This table is the complete reducer specification, not measured J16 predictions. The model returns a nonempty set of categories rather than a Boolean answer to “across.” Known consequences are those shared by every reported possibility. An unresolved target/reference binding must retain all categories; uncertainty between categories must include a reason. The reducer never reads explanatory prose. Neither an outside nor a straddling relation establishes physical contact, support, piece count, or extraction success. Single-category observations can still be confidently wrong; these checks cannot solve visual measurement by themselves.

**62 focused offline tests passed** across this representation, the focused observer/runner, and existing decision-set contracts. Tests exercise every nonempty subset of the three categories, unresolved bindings, false certainty, separation of prose from reduction, image/context invalidation, and runner dispatch with the smaller shared budget. Both actual earlier atomic artifacts also replayed identically from their saved checkpoints under the refactored code with provider calls disabled. Old requests, responses, reviews, and their source snapshots remain unchanged.

The new prepared directory is `.cache/calitree-tests/assumption3-projected-extent-j16-20260928/`. It contains the same full-image references and byte-identical focus crops, a fresh manifest, and current source/template snapshots. The model payload has only target/reference selectors and the image-plane frame; it contains neither the old expected Boolean values nor reviewed answers, labels, task instruction, or earlier responses. The change was designed after inspecting the J16 failure, so it is development on the same small set, not independent validation.

The proposed batch is **two GPT-4.1 requests to `api.openai.com`, at most 1,024 completion tokens each / 2,048 total**, with one HTTP attempt per call and no repair calls. It has not been authorized or executed. Preparation is reproducible with:

```sh
.venv/bin/python -m tests.unit.calitree.assumption3_focused_atomic \
  --measurement projected-extent \
  --output-dir .cache/calitree-tests/assumption3-projected-extent-j16-20260928 --prepare
```

This revised relation is about extent relative to the opening as a whole; the earlier human review specifically concerned the front rim. Preserve that scope difference when assessing future output. Do not recode the old false prediction into a new category or claim improved measured agreement before new evidence exists. The previous reviewed original-inside/edited-front-extension descriptions can inform an explicit audit, but do not supply a fine-grained straddling-versus-outside annotation. No new model calls, target changes, or cohort expansion occurred in this step.

### User classifies J16 as a weird/uncertain case; pending experiment withdrawn

After being shown the full J16 pair, instruction, original `partial` label and earlier model `yes` predictions, the user stated: **"i think this can be classified as weird cases if the model prediction has that much of agreement. Which is part of the process."** This explicit case review is recorded in `docs/experiments/calitree_case_reviews.json` as `annotation_review.status: uncertain`, `category: weird_case`. The record preserves the user's wording, exact ordered image hashes, instruction, reviewer identity, and original target. No replacement label is assigned.

The reason for exclusion is the explicit user review of the case, not an automatic rule that model consensus overrides annotations. The review does not establish that `yes` is the correct target or invalidate the earlier observed localization/semantic failures. J16 remains available as a diagnostic edge case. Prior full-case results, failed observer results, region reviews, and atomic-position reviews remain unchanged; the latter have narrower scopes than target-label eligibility.

The pending projected-extent experiment has been withdrawn without execution. Its immutable prepared manifest is retained, with a separate `execution_status.json` marking it suspended for this review outcome. The runner rejects suspended live execution before preparation, credential access, or model calls. The outstanding two-call allowance question is no longer needed for this case.

The shared pilot input loader now attaches the image/instruction-bound registry review and rejects uncertain cases by default for normal fitting/primary comparisons. Explicit diagnostic access can still restore the historical data together with its uncertain metadata; it does not certify or replace the target and must not feed disputed targets into fitting. Broader workflow exclusion uses the existing `annotation_review` metadata controls; this pilot registry does not silently rewrite all AURORA records.

The current pilot membership is **J01: provisionally eligible; J16: quarantined**—one of each. No new primary accuracy score was computed, and historical denominators are preserved. **42 focused tests passed**, including explicit-review exclusion, unchanged original targets, rejection of mismatched review/image identities, and stopping the withdrawn experiment before provider access. Paid totals remain **48 successful completions, 15,392 completion tokens, and 68,337 prompt tokens**. No new model calls were made.

Future assumption-3 work should continue on eligible cases with a bounded review step before expensive repeated repairs. A weird-case flag prompts review; it is not an automatic fourth grading target or permission to discard model errors. Expansion still requires promising observation evidence on the eligible small set.

## Remaining proof obligations

- Fresh consistency across all conditions, not only the two decisive ones; cached replay is insufficient.
- Independent inspection or annotation of ambiguous object contact, separation, and curtain coverage; scalar human labels do not supply condition truth.
- Criteria that align across different instructions without collapsing target/reference or partial-credit distinctions.
- Collision analysis after alignment: different labels with identical observed features indicate missing information, not a need for a deeper tree.
- End-to-end leaf/merge integration only after these observations are measured sufficiently reliable; the default modular/canvas decomposition path is unchanged.
