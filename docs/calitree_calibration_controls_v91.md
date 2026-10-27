# Calibration scope and ordered-grade controls

The full 276-case development predictions are complete. Neither experiment improves the retained **225/276 (81.5%)** optional-expert policy. Keep the current policy; **235/276** is still required to exceed 85%.

## Separate calibration fitting views

Earlier correction learning deliberately combined genuinely source-excluded inner-teacher predictions for nonoriginal source groups with supervised fitting views for original source groups. V89 separates these two populations. In the source-excluded-only arm, the original cases remain hard accuracy constraints, but do not enter calibration fitting. The two scopes use exactly the same 30 cached inner teachers and six fixed outer/full memberships.

This is a fitting-data ablation, not a retrospective finding of outer-fold leakage. Every held source and sibling remains excluded. The fresh 24-case contrastive pilot responses never enter this fitting experiment.

| Calibration control | Mixed fitting views | Only source-excluded fitting views |
|---|---:|---:|
| Class boundary biases | 224/276 | 223/276 |
| Biases with affirmative grade warrants | 222/276 | 222/276 |
| Semantic additive score, regularization .01 | 221/276 | 223/276 |
| Semantic additive score, regularization .1 | 224/276 | 221/276 |
| Semantic additive score, regularization 1 | 223/276 | 223/276 |

Each class-bias model chooses among 49 predeclared candidates using fitting-source accuracy, conservative tie rules and a hard original-case veto. The additive models use the existing v82 explicit equation, at most 24 named semantic/claim terms and fitting-only feature normalization/selection. Neither arm uses raw embeddings, identifiers, new image inference or new API responses. Every V89 fit retains 99/99 original cases, 144/144 local slots and the same 273/276 bound-evidence coverage.

## Ordered visual grades

The earlier v62 ordinal and continuous-score experiments preceded paired vision. V90 applies those fixed objectives to exactly the stronger v64/v69 feature selection and source folds, without changing the labels or observation cache:

- Two binary classifiers estimate human grade above No and human grade above Partial. Completion support is projected below progress support before deriving three class masses. These outputs estimate grade thresholds, not certified physical progress or completion.
- A shared-split regressor predicts the released human mean and the within-task centered mean; inference uses only the global mean with the unchanged .5/1.5 boundaries.
- Fixed blends give the new model weight .25, .5 or 1, with an optional affirmative same-requirement grade warrant for every changed label.

| Objective / new-model weight | Unrestricted | Affirmative warrant |
|---|---:|---:|
| Ordinal / .25 | 225/276 | 225/276 |
| Ordinal / .5 | 221/276 | 224/276 |
| Ordinal / 1 | 216/276 | 222/276 |
| Relative mean / .25 | 225/276 | 225/276 |
| Relative mean / .5 | 222/276 | 224/276 |
| Relative mean / 1 | 205/276 | 220/276 |

The .25 unrestricted blends each gain two cases and lose two; their warranted counterparts reproduce all existing primary predictions. There is no accuracy/compression reason to add these models. The direct continuous-score arms also fail original-case retention and are ineligible even apart from their worse development accuracy. No failed local-retention model is promoted.

Both experiments preserve the original v72/v87 rule context and priority: existing semantic decisions execute with the old teacher scores, and only remaining teacher decisions can be recalibrated. Missing bound evidence keeps the regular fallback. Coverage is the unchanged upstream evidence coverage, not an assertion that every covered prediction is correct.

## Verification and artifacts

The independent [v91 audit](../logs/exps/261023-verified-calibration-controls-v91-r2/verification.json) passes: **24 native models and 132 score equations** reproduce all saved predictions. Fitting/source memberships, reference labels, original 144-slot retention, model eligibility and unchanged coverage are checked. All ten V89 controls and ten of twelve V90 controls retain all originals in every outer/full fit. The two direct continuous-score controls fail retention and are explicitly ineligible; the audit verifies those failures instead of silently removing them. The best eligible result remains 225/276.

The focused offline collector/routing/calibration/ordinal suite passes **24 tests**. No serving default changed and no API calls were added beyond the separately approved 72-request pilot.

- [Calibration controls](../logs/exps/261023-source-excluded-calibration-v89-r1/results.json).
- [Ordered visual study](../logs/exps/261023-ordered-visual-rubric-v90-r1/).
- [Independent auditor source](../run/verify_calitree_calibration_controls_v91.py).
- [Completed paid pilot and collateral-cap diagnosis](calitree_contrastive_pilot_v88.md).
- [Counterfactual cap audit](../logs/exps/261023-collateral-cap-context-v92-r2/results.json).

These controls distinguish score calibration, observed semantic evidence and human grading policy. Neither score adjustment nor changing the ordinal objective supplies the missing ten correct cases. The collateral diagnostic also rejects a blanket cap removal: four original human Partial cases would wrongly qualify for Yes. More context about task-relevant preservation is needed before changing that rule.
