# Protected accuracy development, v37 onward

The user updated the target to strictly **over80% overall three-class accuracy**,
including fallbacks and failures, while retaining all99 original training
examples underlying144 slots. The visual-semantic candidate now reaches
**222/276 (80.4%)** in independently replayed source-held development, with
**99/99 and144/144** retained. All915 generic encoder/judge predictions match
the frozen artifact. See `docs/calitree_visual_policy_v69.md` for scope and use.
The historical sections below describe the earlier85% target and its studies.
The serving policy remains unchanged during these studies. The latest approved
540-output matched-editor expansion is complete: its fixed comparison does not
beat the prior **216/276 (78.3%)** boundary policy. The best expanded policy with
unchanged coverage reaches 211/276; a tighter gate reaches 215/276 with fewer
tree routes. Original 99/99 accuracy is retained by the selected prior policy.

## Completed development screens

The 80-output pilot and 36-output forward study are now development data: 116
outputs from 52 decoded-pixel source groups, disjoint from the original training
pool. Each held source and all its siblings are excluded from a fold. Original
training examples stay in every fit. Predictors are closed semantic/task
predicates and frozen regular/expert outputs; case/source/editor identifiers,
object names and observed-signature lookups are prohibited as predictors.

| Study | Candidates | Evaluation | Best overall result | Original training |
|---|---:|---|---:|---:|
| v37 semantic classifier/router | 9 | 52 held-source folds | 82/116 routed (70.7%) | 99/99 in every fit |
| v40 explicit expert regions and domain weights | 8 | 52 held-source folds | 82/116 routed (70.7%) | 99/99 in every fit |
| v41 intent/completion boosting | 5 | 5 fixed source-group folds | 79/116 (68.1%) | 99/99 in every fit |
| v43 continuous-score versus label learning | 6 | 52 held-source folds | 82/116 classifier control; regressors at most 76/116 | Direct 99/99; regression routing fails retention |
| v44 simpler vocabularies and confidence fallback | 6 | 52 held-source folds | 77/116 passing the conservative screen | Initial all-threshold screen; actual gates audited separately below |
| v45 compatible cached evidence augmentation | 5 | 52 held-source folds | 79/116 augmented; 82/116 unaugmented control | 99/99 in every fit |

The v41 forest control achieves 76/116 on its own five-fold split; do not compare
fold schemes as if their training sets were identical. The best v37 router gets
59/80 pilot outputs and 23/36 forward outputs correct. Its source-held predictions
were independently reproduced, and all 22 configurations were recounted in
`logs/exps/261020-accuracy-development-audit-v37-r1`.

The correct human label is among the frozen regular/expert outputs on 110/116
cases (94.8%). This is an oracle action-availability bound, not attainable router
accuracy. It distinguishes insufficient available labels from failure to choose
the right expert. Missing evidence still uses regular fallback; failed cases
remain in denominators.

## Approved stronger-judge diagnostic

v38 compares the unchanged regular prompt with six visual calibration examples
from other original training sources, two examples per class. The 24 query cases
are class balanced and source distinct. Entire query sources are excluded from
retrieval. Model: GPT-6.1 Sol, medium reasoning, no temperature. This is a
training-only diagnostic, not evidence of unseen generalization.

Exactly 48 attempts were made: 43 completed and five SSL/connection failures were
retained without retry. Cached Luna, direct Sol, and calibrated Sol each achieve
15/24 including failures. On the 19 cases where both fresh arms complete, each
achieves 14/19. Thus this small diagnostic does not justify replacing the judge
or purchasing a larger Sol validation run.

Known usage is 174,192 input tokens and 3,961 completion tokens. Counting the five
failed output reservations gives 44,921 completion tokens/reservations. At the
reviewed Sol rates this is $0.388 for recorded usage, or $0.798 including failed
output reservations, plus any unknown failed-request input charges. These are
estimates, not an invoice. Full requests and responses are in the durable ledger.

## Reserved evaluation and additional fitting

v39 reserves 80 outputs from 80 distinct sources, category balanced and editor
balanced. Selection is independent of labels and predictions. All sources are
disjoint from current fitting and recent exclusions. Older repository exposure
is disclosed: this cohort is fitting-disjoint, not globally pristine. Its labels
are not retrieved or scored here. A complete policy must be frozen before a
separately approved validation run. Strictly over 85% requires at least 69/80,
with failures retained and per-class performance reported.

The separately approved v42 training expansion collects all five editors for 32
additional sources (160 outputs, four sources per category), excluding all 80
reserved sources. It reuses compiler-v3, observer-v2, interpreter-v5 and the
regular Luna judge. Maximum 544 requests and 4,784,128 completion tokens include
up to 32 compiler repairs; transport retries are disabled. Training references
are joined after label-blind extraction. Collection is complete and independently
audited: 159 valid feature records and one retained SSL failure; all 160 regular
judgments complete, with 110/160 correct (68.8%). No compiler repairs or transport
retries were used.

The run makes 511 requests: 32 compilations, 160 image observations, 159 semantic
interpretations, and 160 regular judgments. Of these, 510 complete and one fails.
Known usage is 1,392,812 input and 255,446 completion tokens. Including the failed
16,384-token output reservation gives 271,830 completion tokens/reservations,
inside both approved caps. Estimated recorded usage costs $0.267; including the
failed output reservation gives $0.275, plus any unknown failed-input billing.
This is a usage estimate, not an invoice. Full histories replace root placeholders;
initial preflight logs remain byte-for-byte in `preflight_logs/` and are checked
against their original hashes.

v43 tests continuous released human means against categorical classification
using the same declared features. It keeps the public half-point thresholds
fixed. Regression does not improve accuracy. v44 finds only 206 distinct varying
columns among the 955 original columns on the current dataset, but fold-local
duplicate/constant-column removal also fails to improve accuracy. Meaning-only
feature subsets fail the reported all-threshold screen. That screen required
confidence >=0.9 instead of executing actual fallback; the later audit corrects
eligibility per threshold instead of excluding all thresholds together.

v45 admits 213 compatible cached compiler/observer views after checking image
hashes, instructions, references, physical bindings, and semantic interpretation
bindings. These are alternate fitting views of the same known source groups,
not additional independent examples. All views of a held source are excluded.
No extra inference calls are introduced. Augmentation does not beat its control.

The v46 learning curve uses matched source-group folds to compare zero,
half, and full expansion volume plus one original-domain weighting variant. The
half-volume subset is selected by a fixed source hash without labels or model
predictions. Collection and its independent request/feature audit finish before
enlarged-data fitting starts.

## Enlarged-data results and verified candidate

The current pool has 375 outputs from 182 source groups. Five fixed source-group
folds evaluate 276 development outputs from 84 sources; the original 99 examples
(98 sources) remain in every fit. All siblings of a held source are excluded.
The 80 reserved validation sources remain unused.

| Matched-fold learning curve | Overall | Prior 116 | New 160 |
|---|---:|---:|---:|
| No expansion fitting | 202/276 (73.2%) | 80/116 | 122/160 |
| Half expansion fitting | 212/276 (76.8%) | 86/116 | 126/160 |
| Full expansion fitting | 212/276 (76.8%) | 88/116 | 124/160 |
| Full expansion, original weight 0.1 | 213/276 (77.2%) | 88/116 | 125/160 |

All four retain 99/99 original examples in every fold. Additional volume helps,
but the curve does not establish that further volume alone will reach 85%.

The v47 audit recounts 27 enlarged-data configurations: continuous learning,
simplified inputs, cached augmentation, volume controls, and six v48 boosting
repeats. The best verified selector removes training-only duplicate/constant
columns and excludes frozen expert labels from its inputs. It still chooses only
among labels available from those experts and the regular judge. Valid evidence
is routed; missing evidence uses regular fallback. This optional research
candidate does not replace the serving coverage policy.

| Cohort | Regular judge | Verified selector |
|---|---:|---:|
| Pilot 80 | 53/80 (66.3%) | 65/80 (81.3%) |
| Forward 36 | 20/36 (55.6%) | 24/36 (66.7%) |
| Expansion 160 | 110/160 (68.8%) | 126/160 (78.8%) |
| Overall development | 183/276 (66.3%) | **215/276 (77.9%)** |

Macro F1 improves from 0.537 to 0.657. Always predicting No gets 187/276 (67.8%).
All 99 original cases representing all 144 slots remain correct in every selected
source-held fold. These are development results after model selection. Strictly
over 85% requires 235/276: 20 additional correct cases.

The audit finds a regression-mode bookkeeping error: fixed score thresholds
retain 99/99 direct training labels, but nearest-available-action routing chooses
the lower label at exact half-point ties. All four regressors get only 95/99
routed labels correct in the reproduced first fold, on both data sizes. They are
excluded as routed candidates. Frozen study files stay unchanged; corrected
eligibility and counterexamples are in `261020-expanded-policy-audit-v47`.

The selected full-data model is saved in
`logs/exps/261020-frozen-semantic-policy-v49/selector.json`. The optional runtime
validates closed Boolean predicate names and hashes, averages 128 tree probability
vectors, chooses an available judge label, and keeps missing-evidence fallback.
No case/source identifiers or example lookups enter inference. The full fit uses
194 columns and zero expert-label input columns; the frozen experts still supply
available actions. JSON execution reproduces all 375 sklearn predictions.
Original retention is 99/99, with all those cases covered. Full-pool fitting
accuracy is 363/375 and valid-evidence coverage is 372/375; neither is a
generalization result. Serving defaults are unchanged.

## Artifacts and verification

- Runners: `run/calitree_accuracy_headroom_v37.py`,
  `run/calitree_adjudicator_diagnostic_v38.py`,
  `run/reserve_calitree_validation_v39.py`,
  `run/calitree_expert_region_policy_v40.py`,
  `run/calitree_goal_progress_policy_v41.py`,
  `run/calitree_training_expansion_v42.py`,
  `run/calitree_continuous_policy_v43.py`,
  `run/calitree_simplified_policy_v44.py`,
  `run/calitree_evidence_augmentation_v45.py`,
  `run/calitree_training_curve_v46.py`,
  `run/calitree_expanded_boost_policy_v48.py`,
  `run/freeze_calitree_semantic_policy_v49.py`.
- Independent audit: `run/verify_calitree_accuracy_development_v37.py`.
- New collector auditor: `run/verify_calitree_training_expansion_v42.py`.
- New actual-route auditor: `run/verify_calitree_expanded_policies_v47.py`.
- Optional runtime: `critical/core/calibration/semantic_expert_policy_v49.py`.
- Forty-eight focused tests passed before adding v43; 11 new-study focused tests
  pass after adding the train-only feature-selection check. The final focused
  suite has 52 passing tests, including available-action enforcement, confidence
  fallback, missing evidence, and forbidden identifiers. All are offline. No UI
  files changed, so browser end-to-end tests are not applicable.

**The historical >85% target was not achieved.** The updated80% target is met on
source-held development; the separate reserved evaluation remains unrun.

## Follow-on investigation

The v50 sparse semantic conjunction screen does not improve on the selected
forest: best eligible 201/276, exact forest control 215/276. The error audit
finds 53 errors with the correct action available, eight unavailable-label
errors, and 20 harmful overrides. Only ten development cases have multiple
requirements, limiting what an aggregation-only change could recover.

A fresh-paired Luna/Sol observer comparison is prepared in
`261020-observer-diagnostic-v51-r1`, with unchanged compiled questions, Luna
interpretation, cached regular judgments, and source-excluded controllers.
The twelve selected training cases and 48-request/589,824-token limit are
documented in `docs/calitree_observer_diagnostic_v51.md`. The user subsequently
authorizes and completes all 48 requests: fresh Luna gets 6/12, Sol 4/12, with no
failures, retries, fitting or serving changes. The independent audit estimates
$0.298 and verifies both caps. Fresh Luna changes predicates on seven examples
and final predictions on three versus cache. This selected diagnostic supports
investigating predicate stability, not swapping observers on the existing rules.

The independent v52 cached-field study retains source/view confidence fields
without accessing the fresh diagnostic outputs. Its seven source-held policies
all retain original 99/99 cases but reach at most 214/276; exact control 215/276.
Reserved-source evaluation remains unused, and the >85% target remains unmet.

The v53–v56 follow-on screens independently replay a small new best: 216/276
(78.3%) using balanced progress/completion/success boundary experts and weakest
boundary support. Original 99-case retention holds across all folds and full fit;
the one-case gain is six fixes and five losses. Reproducibility priors, language
qualifiers and whole-frame fidelity cues do not improve the 215/276 control.

The user approved and completed 540 missing outcomes from the other four editors
on 135 existing single-editor tasks. The pool now has 915 outputs, 183 per editor,
without new source groups. All 540 slots are retained, including nine missing
feature records; 1,612 request slots and 922,087 completion tokens/reservations
stay within the original caps. Independently audited usage is $0.812 recorded,
or $0.893 including failed output reservations plus unknown failed input charges.

Eight prespecified v58 configurations preserve the original 276-case source-held
folds and exclude every added sibling of each held source. The prior boundary
policy remains best at 216/276. The best expanded same-coverage policy gets
211/276; gate .5 recovers 215/276 but reduces tree acceptance from 273 to 247.
The new models improve No recall and lose Partial/Yes recall. Unweighted forests
also lose original accuracy; weight-5 controls restore 99/99 but not the old
development score. Independent replay verifies 99/99 and all 144 local slots.
The optional v59 JSON artifact freezes the selected prior boundary policy and
matches all 915 pool predictions, without fitting on the new rows or changing
serving defaults. The >85% target remains unmet. See
`docs/calitree_training_coverage_v57.md` for the complete results and artifacts.
