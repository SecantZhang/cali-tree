# Class-balanced training of the existing model

The fixed primary class-balanced model scores **217/276 (78.6%)**, versus **227/276 (82.2%)** for the reproduced current control. Balanced accuracy is **67.4% versus 67.9%**, and macro F1 is 66.6% versus 70.6%. Balancing only the semantic correction reaches 221/276 (80.1%) and 64.4% balanced accuracy. No class-balanced arm improves both metrics over the current full pipeline.

## Method

All 915 fitting-pool examples remain available: 636 No, 197 Partial and 82 Yes. In each actual training fold, weights are computed using that fold’s fitting labels only and each grade receives exactly one-third of the total training weight. This is class-balanced weighted training, without downsampling or synthetic examples. The semantic residual begins with the existing inverse source-size weights before class normalization. The visual booster begins with the existing equal-row weights before class normalization. Original-case anchor multipliers are applied within classes and re-normalized, so protection does not destroy equal class mass.

The visual model remains depth 8 with 1,200 MultiClass trees; the contextual semantic correction remains depth 2 with 128 MultiRMSE trees. Feature columns, seeds, learning rates, regularization, original-case veto, tie order and positive-warrant guard remain fixed. Original 99-case/144-slot protection passes for all arms and all six fits. Earlier v72/v87 rules keep their original teacher context and priority.

Evaluation uses the same 276 reviewed development cases and five source-held outer folds. All held-source sibling outputs are removed from every inner and outer training fit. Thirty-six class-balanced main teachers supply fresh source-excluded fitting scores for the correction. Fold 5 fits all 915 for local retention and artifact analysis, and contributes no headline evaluation rows. No held-case label enters class weights, original-weight selection or residual-strength selection.

## Results

| Training / composition | Correct | Accuracy | Balanced accuracy | Macro F1 |
|---|---:|---:|---:|---:|
| Existing weighting (control) | 227/276 | 82.2% | 67.9% | 70.6% |
| Balanced semantic head only | 221/276 | 80.1% | 64.4% | 65.7% |
| Balanced main classifier + prior experts | 219/276 | 79.3% | 66.9% | 67.9% |
| Balanced main + balanced retrained head (primary) | 217/276 | 78.6% | 67.4% | 66.6% |
| Balanced main classifier, regular fallback | 216/276 | 78.3% | 65.6% | 66.7% |
| Balanced main + frozen semantic head | 217/276 | 78.6% | 67.0% | 67.4% |
| Balanced main + source-weighted retrained head | 217/276 | 78.6% | 65.3% | 66.3% |

The primary arm was declared before evaluation; these diagnostic arms are reported without selecting a new policy from their development scores. The unchanged control reproduces every existing fold prediction and the 227 headline.

## Why balancing does not win here

| Human grade | Existing correct / total | Balanced primary correct / total | Existing recall | Balanced recall |
|---|---:|---:|---:|---:|
| No | 179/187 | 170/187 | 95.7% | 90.9% |
| Partial | 30/56 | 25/56 | 53.6% | 44.6% |
| Yes | 18/33 | 22/33 | 54.5% | 66.7% |

The primary arm fixes 10 decisions but breaks 20 previously correct decisions. Net correct counts change by −9 No, −5 Partial and +4 Yes. It predicts Yes on 40 cases instead of 24; true Yes predictions rise 18→22, while false Yes predictions rise 6→18. Yes precision falls 75%→55%. The minority-grade benefit is concentrated in Yes and is offset by poorer No and Partial recognition.

Balancing only the semantic head makes six changes, all incorrect Partial→Yes upgrades, and produces no new correct decisions. Equalizing grade contributions changes the learned boundary; the existing evidence does not support all of the additional full-success predictions. This result does not establish that other balancing methods or stronger evidence would behave the same way.

## Routing and protection

Upstream bound-evidence coverage stays 273/276 for every arm, and all 276 cases remain in the denominator. Recomputing the local review gate changes 83 review cases to 86, with 82→79 usable cached observations. Twenty-four cases enter review and 21 leave it. All seven newly reviewed cases without observations retain the corresponding base prediction; six of those predictions are already correct. Even perfect correction of the one remaining missing-observation error would only raise the primary result 217→218, holding all other decisions fixed. Missing observations cannot explain the ten-case decline.

All 99 original training cases and 144 original evaluation slots remain correct in every arm and every fit. These are protected fitting cases and are separate from the 276-case evaluation denominator.

## Verification and recovery

The independent audit checks 36 native main teachers on 32,940 cached rows, re-induces 24 semantic heads, and compares 21,960 native residuals with their executable shared terms. Maximum teacher difference is 0; maximum residual difference is 6.11e-16. Metrics additionally match scikit-learn accuracy, balanced accuracy and macro F1. Twenty focused unit tests pass, including a regression for parallel outer/inner directory creation and unresolved-case metric denominators.

The initial r1 parallel run was stopped after identifying a parent-directory race: an inner job could create a fold directory before its outer job. The fix permits an existing parent in the fresh run. The r2 run recovers 11 complete fits only after input/target/weight/model checks and an AST check proving the fitting function is identical apart from that directory correction. Partial fits are rerun locally; r1 remains explicitly interrupted.

There are zero new API, encoder or local-observer calls, no reserved-set access, and no serving-default change. This is a development comparison on previously reviewed data. The verified 227/276, 60-term policy remains available unchanged.

## Reproduce

```bash
PYTHONPATH=/tmp/calitree-catboost-v62:. /Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/.venv/bin/python -m run.calitree_class_balanced_v141 --output-dir NEW_RUN --workers 3
PYTHONPATH=/tmp/calitree-catboost-v62:. /Users/zzhang/Documents/Projects/Adobe/calitree-mlsys/.venv/bin/python -m run.verify_calitree_class_balanced_v142 --study NEW_RUN --output-dir NEW_AUDIT
```

- [Frozen protocol](../logs/exps/261023-class-balanced-v141-r2/protocol.json).
- [Complete comparison](../logs/exps/261023-class-balanced-v141-r2/results.json).
- [Independent verification](../logs/exps/261023-class-balanced-audit-v142-r1/verification.json).
- [Paired predictions](../logs/exps/261023-class-balanced-audit-v142-r1/predictions.json).
- [Routing/error analysis](../logs/exps/261023-class-balanced-audit-v142-r1/error_analysis.json).
- [Primary full-fit executable rubric](../logs/exps/261023-class-balanced-v141-r2/heads/fold5/balanced_base_balanced_head/rubric.txt).
