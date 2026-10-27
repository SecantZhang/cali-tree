# Further balanced-accuracy experiments

**The best exploratory candidate reaches 71.1% balanced accuracy, versus 67.9% for selected v112.** Overall accuracy changes 227/276 (82.2%)→226/276 (81.9%). It raises Yes recall but lowers Partial recall 53.6%→42.9%, so the selected v112 default is retained. The 80% balanced-accuracy target is not achieved.

This round reports 37 fixed arms across four sequential development studies. Every per-fold fit excludes its outer held-source group and all sibling outputs. Families were developed after earlier diagnostics and the best arm is selected retrospectively from this search; this is a reviewed development result. No new images, model API calls, encoder/observer inference or reserved sources are used.

## Results

| Study | Declared primary balanced accuracy | Best reported balanced accuracy | Best overall accuracy |
|---|---:|---:|---:|
| Two-parameter final calibration | 64.0% | 67.9% | 82.2% |
| Up to four warrant-seeded semantic corrections | 67.9% | 71.1% | 81.9% |
| Up to four semantic independent-judge routes | 67.5% | 70.5% | 79.0% |
| Moderate main-classifier weighting | 64.9% | 64.9% | 79.3% |

The primary No→Partial-only patch retains the existing 67.9% result. The best 71.1% arm is the broader all-grade, loss-cost1, two-guard variant. The moderate-weight primary uses exponent 0.5 and the protected frozen semantic head; full class balancing (exponent 1) was already tested separately in v141 and did not win.

## Best compact semantic candidate

| Metric | Selected v112 | Four-rule candidate |
|---|---:|---:|
| Overall accuracy | 82.2% | 81.9% |
| Balanced accuracy | 67.9% | 71.1% |
| Macro F1 | 70.6% | 70.5% |
| No recall | 179/187 (95.7%) | 177/187 (94.7%) |
| Partial recall | 30/56 (53.6%) | 24/56 (42.9%) |
| Yes recall | 18/33 (54.5%) | 25/33 (75.8%) |

Seven previously wrong decisions become correct, eight previously correct decisions become wrong, and two wrong decisions change to another wrong grade. Net correct counts are No −2, Partial −6, Yes +7. The balanced mean improves by 3.14 percentage points, while the weakest-class recall becomes worse. This is the reason to retain v112 as the selected version.

The full-fit artifact adds 4 ordered correction rules using 11 named concepts to the existing v112 stack; it is not a standalone four-rule judge. Earlier rubric/expert overrides keep priority. A direct grade must begin with its affirmative same-requirement rubric or bound local-model warrant. Each conjunction has up to two extra guards and a current-grade region. At least two distinct positive fitting pixel sources support every clause; no IDs, object-name lookup rules or raw visual vectors are used.

The first two full-fit rules promote a Partial/No proposal to Yes when the bound local observer reports a completed goal under specific identity/collateral or independent-judge conditions. Those observer claims sometimes also occur on human-Partial cases, which accounts for the remaining false full-success predictions. The rubric text is an exact executable rule rendering, not an assertion that its learned decisions are physically correct.

- [Best full-fit rubric](../logs/exps/261025-balanced-patches-v144-r1/fold5/all_grades_loss1.0_guards2.txt).
- [Best full-fit rule artifact](../logs/exps/261025-balanced-patches-v144-r1/fold5/all_grades_loss1.0_guards2.json).

## Why the Partial boundary remains difficult

Under current earlier-rule priority and observation gating, the existing affirmative warrants would permit a correct additional Partial grade on only 1 of the 26 current Partial errors. The cached regular judge contains a correct Partial alternative on 7 of those errors, but routing to it also introduces errors on current correct No cases. The new semantic expert-routing study does not outperform the best direct-rule candidate.

These are reference-informed correction-availability diagnostics, not executable policies or measured learned accuracies. They use the human label to determine whether an existing opinion/warrant could correct an error. The oracle statistics are isolated in a diagnostic artifact and never supplied to inference. They show some available expert headroom, while also showing that reliable Partial evidence/arbitration is the remaining weakness. Further work should distinguish meaningful goal-directed progress with a missing endpoint from no progress and from complete success.

- [Reference-informed diagnostics, not model results](../logs/exps/261025-balanced-search-audit-v145-r1/oracle_diagnostics.json).

## Method and validation

The final calibration study tests two class-score offsets and two ordered cutoffs on the statistical expected-grade index. It selects parameters by final balanced accuracy; guarded versions require existing grade warrants, and Pareto versions also veto any fitting class-recall decline. It does not improve the baseline. The ordinal index is a human-grade score, not a physical progress measure.

The semantic studies learn a maximum of four first-match corrections from bound named predicates. The independent-judge variant can select an existing regular judgment from disagreement plus a named semantic/view/rationale review cue, without pretending that uncertainty establishes a physical grade. The No→Partial-only arms structurally preserve all existing Partial and Yes decisions.

For all three small-policy studies, genuine inner-source-excluded teacher scores supply the fitting view; the fixed outer-fit v112 residual is reused on those views and is not independently inner-cross-fitted for this calibration. No outer-held source enters any component. Earlier v112 semantic/expert overrides are locked before new rules execute.

The moderate-weight study trains 18 main classifiers: exponents0.25/0.5/0.75 across the existing five outer folds and full-fit fold5. Each uses the same 1,200 depth-8 trees and original-case anchor search. It recomputes local review routing and view flags, reuses the frozen semantic head, and optionally reduces head strength only to retain original fitting cases. Earlier semantic/expert routing keeps its original teacher context. Every arm remains below v112 balanced accuracy.

All 37 arms retain 99 original cases and 144 original evaluation slots in every fit. Upstream coverage stays 273/276, and every evaluation keeps all 276 cases in its denominator. The existing v112 artifacts and default selector are unchanged.

The independent small-policy audit re-induces 168 calibration/rule models and compares 153,720 scalar/native prediction rows. The separate moderate-weight audit checks 18 native main classifiers and frozen heads on 32,940 rows, including class-weight receipts, source masks, view/routing reconstruction, protected strength selection and predictions. Metrics independently match scikit-learn ordinary accuracy, balanced accuracy and macro F1. Twenty-four focused tests pass.

CatBoost 1.2.10 was restored from public PyPI into an isolated temporary target after the earlier temporary Python modules had been cleaned up. The project environment is unchanged and no task data is uploaded. The selected inference path itself remains independent of CatBoost fitting modules.

## Evidence

- [Compact calibration results](../logs/exps/261025-compact-balanced-v143-r1/results.json).
- [Semantic correction results](../logs/exps/261025-balanced-patches-v144-r1/results.json).
- [Semantic expert-routing results](../logs/exps/261025-balanced-experts-v146-r1/results.json).
- [Moderate weighting results](../logs/exps/261025-tempered-balance-v147-r1/results.json).
- [Small-policy independent audit](../logs/exps/261025-balanced-search-audit-v145-r1/verification.json).
- [Moderate-weight independent audit](../logs/exps/261025-tempered-audit-v148-r1/verification.json).
- [Machine-readable summary](experiments/calitree_balanced_accuracy_v148.json).
