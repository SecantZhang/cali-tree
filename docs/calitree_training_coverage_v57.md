# Matched-editor training coverage

The user subsequently lowered the target to **over80%**. The visual-semantic
follow-on reaches **222/276 (80.4%)**, retaining99/99 originals and144/144 slots,
with independent source-held refits and actual915-case inference replay. See
`docs/calitree_visual_policy_v69.md`. The sections below preserve the completed
matched-editor expansion findings and the historical85% objective.

At the end of the matched-editor study, the independently replayed candidate reaches **216/276
(78.3%)**, compared with 215/276 for the previous forest. It preserves the
original 99 examples in every source-held fold and in the full fit. The gain is
one case (six corrections, five new errors), not evidence that the >85% objective
is achieved. The fixed primary evaluation still requires 235/276.

## Completed expansion and comparison

The approved run processed all **540 outputs**, producing **531 valid feature
records**. It used 1,612 durable request slots (within 1,620) and 922,087
completion tokens/reservations (within 14,376,960). The independent audit rebuilt
every request identity, reused program, evidence projection and released-label
join. There were 20 retained failed slots: eight observations, one interpretation
blocked before HTTP by the stop latch, and eleven regular judgments. No failed
slot was retried. The training-only regular result is 352/540; it is not the
primary evaluation result.

Recorded usage is 4,319,385 input and 760,295 completion tokens: **$0.812086** at
the reviewed Luna rates. Including failed output reservations gives
**$0.892982**, plus any unknown failed-request input charges. All original caps
and reserved-source exclusions passed audit.

The fixed comparison uses the **same 276 cases, 84 source groups and five folds**
as before, excluding every added sibling of each held source. Results include
fallbacks and failures:

| Policy | Correct / 276 | Accuracy | Tree accepted / 276 | Original accuracy |
|---|---:|---:|---:|---:|
| Regular judge | 183 | 66.3% | — | Comparison baseline |
| Prior balanced boundary policy | **216** | **78.3%** | **273 (98.9%)** | **99/99; 144/144 slots** |
| Expanded forest, original weight 5, same coverage | 211 | 76.4% | 273 (98.9%) | 99/99 |
| Expanded boundary policy, support gate .5 | 215 | 77.9% | 247 (89.5%) | 99/99 |

The eight prespecified configurations include zero, half and full sibling
coverage for both model families plus full-coverage weight-5 controls. Half
coverage reaches at most 209/276. Unweighted expanded forests fail original
retention (minimum 98/99 for half, 97/99 for full) and are ineligible. Stronger
original weighting restores retention but does not improve development accuracy.
The best expanded gate loses 26 tree routes and still falls one case below the
previous boundary policy. **The expansion does not justify replacing it.**

The expanded same-coverage model improves No recall from 89.8% to 92.5%, but
Partial recall falls from 53.6% to 41.1% and Yes from 54.5% to 45.5%. With the
tighter gate, Partial/Yes recover to 44.6%/51.5%. The new examples are 408 No,
102 Partial and 30 Yes; editor balance does not imply label balance. This is an
observed class-discrimination tradeoff, not proof that label frequency alone
caused the regression.

The pooled representation has 806 distinct semantic vectors for 915 examples,
with 20 contradictory-label groups. Two original examples (N054 Partial and
N082 Yes) acquire indistinguishable counterparts with different labels, helping
explain why unweighted forests lose local accuracy. Equality permits at most
892/915 correct across this pool; this is a descriptive information bound, not
an achievable unseen accuracy or an inference lookup table.

Independent v58 replay confirms all five held-source predictions and the full
fit, 99/99 original examples, and the actual 144 training slots. The first audit
attempt counted 294 local-plus-outside cohort rows as training slots; the audit
was corrected to select the explicit 48 local rows per bank. All 294 broader
replays also agree. The prior winning policy is retained and frozen optionally
as `261021-frozen-matched-policy-v59/policy.json`; all 915 serialized predictions
match sklearn. It fits the prior 375 rows, not the added 540. Pool/fitting replay
scores are not generalization results. Serving defaults remain unchanged.

## Completed offline investigations

| Study | Fitting configurations | Best added-method result | Exact control |
|---|---:|---:|---:|
| v53 cross-view reproducibility priors | 7 | 215/276 | 215/276 |
| v54 evidence-description language cues | 7 | 213/276 | 215/276 |
| v55 progress/completion/success boundary experts | 7, with declared scoring alternatives | 216/276 | 215/276 |
| v56 deterministic whole-frame fidelity cues | 7 | 212/276 | 215/276 |

Reproducibility estimates use alternate views from original fitting sources
only; no evaluated source or fresh v51 diagnostic contributes. Language cues are
predeclared generic mentions of extent, uncertainty, change and negation, not
object names or factual-oracle assertions. Fidelity cues measure whole-frame
structure/color/blur with fixed thresholds, not task-target identity, source IDs,
hashes or coordinates. The image/context-only variants lose original training
accuracy and are ineligible.

The v55 candidate has three explicit decision boundaries: No/Partial (progress),
Partial/Yes (completion), and No/Yes (clear failure versus success). Its selected
score takes each label's weakest relevant boundary and chooses among existing
available judge labels. Scores are normalized support, not calibrated confidence.
New-label proposals require strict wins over both alternatives; ties and cycles
give no proposal. Expanding label availability does not improve this candidate.
The v55 audit refits all five source-held winning models and verifies the full
fit's original 99-case retention. Serving defaults remain unchanged.

## Coverage gap before collection

All 99 original training examples use the same finetuned MagicBrush editor.
The 135 original sampled tasks (training plus reviewed forward development)
contained only that editor's output. The 16 pilot tasks and 32 expansion
tasks already contained all five editors. This made the 375-output fitting
pool uneven across editors:

| Editor group | Before collection | Added outputs | Completed pool |
|---|---:|---:|---:|
| Finetuned MagicBrush | 183 | 0 | 183 |
| GenHowTo | 48 | 135 | 183 |
| Instruct-Pix2Pix | 48 | 135 | 183 |
| MagicBrush reproduction | 48 | 135 | 183 |
| MGIE | 48 | 135 | 183 |
| Total | 375 | **540** | **915** |

Completing those same tasks supplies matched success/failure outcomes under the
same instructions and scenes. This addresses a measured fitting-coverage gap;
it does not guarantee an accuracy gain. Editor identifiers remain provenance and
sampling information, never inference predicates.

## Collection protocol

`logs/exps/261021-sibling-training-v57` contains 540 label-free input entries,
separate training references, 135 cached compiled programs, image hashes and the
bounded collection protocol. The cases cover 135 tasks/134 decoded-pixel source
groups already in fitting/development. No new source group is introduced. All
80 reserved sources and all original sampled-manifest excluded groups are absent.

Each output receives at most three Luna requests: bound image observation,
instruction-relative interpretation and unchanged regular judgment. Programs are
reused exactly; no compilation or repair calls. Failed slots are retained with
no transport retries. Four workers use **separate per-output durable ledgers**;
the aggregate limit is the sum of 540 disjoint allowances:

- Maximum **1,620 requests**.
- Maximum **14,376,960 completion tokens**.
- Maximum 26,624 completion tokens per output (16,384 + 8,192 + 2,048).
- Shared provider stop latch after a rejection or three consecutive transport
  failures; at most four requests can already be in flight.

The empirical forecast is **$0.853**, extrapolating the completed v42 non-compiler
usage including its failed output reservation. Expected range **$0.80–$1.40**.
The full completion allowance costs **$7.18848 plus input charges**, using
[official Luna rates](https://developers.openai.com/api/docs/models/gpt-6-luna),
rechecked on 2026-10-21 UTC. No cache discounts assumed; this is not an invoice
or a hard dollar cap.

The complete offline rehearsal mocks credentials and model engines, exercises
all 1,620 slots in 540 independent ledgers with four concurrent mock requests,
and verifies aggregate limits and bound projections. It creates no real
authorization or paid ledger in the prepared run. Provider-stop and approval
guards have dedicated tests.

## Evaluation and status

The completed comparison tests fixed policies with zero, half and full matched
outcome coverage. It keeps the same **276 primary cases and source-group folds**,
excluding every held-source sibling from fitting. The 80 reserved sources remain
separate; no validation labels were retrieved or scored here.

The user authorized this collection in response to
`call_7d51d82440a14f8e9e9524b3d5dec413`. The bounded four-worker run completed;
its durable per-output ledgers retain failed slots without retries.
There is no serving change and the >85% objective remains active and unmet.

The first transport epoch stopped at 340 completed outputs after three
consecutive SSL failures. A credential-free official-API TLS check succeeded
(expected HTTP 401). The continuation keeps the original stop/failure records
and all 1,019 prior durable slots byte-identical; it permits at most 596 new
stages on 200 unfinished outputs, for at most 1,615 total slots under the same
original caps. Completed stages are read from cache, failed stages stay failed,
and no failed request is resampled. A full 596-stage mocked rehearsal verified
this behavior with four concurrent workers before live continuation.

The offline v58 protocol was saved before collection completed. It declares
eight fits per source fold: forest and balanced boundary policies with zero,
half and full sibling coverage, plus full-coverage controls with original
examples weighted five times. Half coverage chooses two of four missing editors
per task by a label-independent hash. Both direct and available-expert routing
are measured, with support gates at 0, .5, .65, .8 and .9 recomputed after fitting.
Eligibility requires actual original-case decisions to remain 99/99 in every
fold and in the full fit; confidence alone is not a retention test.

The v59 portable JSON runtime supports both candidate families, explicit
available-expert routing/direct output and the selected support gate. It accepts
only the closed Boolean feature vocabulary and bound evidence; IDs, editor
names, raw descriptions and image fingerprints are absent from its interface.
Its forest and binary-head tests match fitted scores, cover ties/fallbacks and
reject undeclared inputs. The freeze step verified all 915 pool predictions
against the fitted model before saving the optional artifact.
It does not change the serving default.
