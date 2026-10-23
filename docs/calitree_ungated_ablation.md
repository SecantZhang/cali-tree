# Ungated expert-vote ablation on the cached AURORA pilot

**Completed offline.** For the fixed equal-vote policy, removing coverage checks substantially worsens accuracy in all three banks. No model calls, fitting, alternative tie-rule search or changes to existing gates were made.

## Rules fixed before scoring

- One equal vote per distinct deployed expert tree. Banks contain four, three and two experts, respectively. Support counts and numbers of regions do not give extra votes.
- Highest vote count wins (plurality; an absolute majority is not required).
- If the top vote counts tie, choose Partial when Partial is among the tied labels. Otherwise choose No for a No/Yes tie. Never choose a label outside the tied winners.
- Bypass all task, region, semantic-support, counterexample and disagreement gates. Preserve evidence-contract validation.
- Missing/failed extraction or an invalid expert vote yields unresolved, with no regular fallback. All 80 planned outputs remain in the accuracy denominator.
- The original regular responses and v27 gates are frozen. Banks are reported separately. No best-bank selection is made.

The protocol was written before this ablation computed scores. The pilot outcomes were already reviewed in preceding experiments, so this is an exploratory ablation on existing development evidence, not a new held-out evaluation.

## Overall comparison

The regular judge scores **53/80 (66.25%)**, macro-F1 **0.535**. The data contain 60 No, 15 Partial and 5 Yes labels; an always-No baseline scores 75% accuracy and about 0.286 macro-F1.

| Bank | Experts | v27 correct / 80 | v27 accuracy | Ungated correct / 80 | Ungated accuracy | v27 macro-F1 | Ungated macro-F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 57/80 | 71.25% | 43/80 | 53.75% | 0.571 | 0.384 |
| 2 | 3 | 50/80 | 62.50% | 35/80 | 43.75% | 0.521 | 0.424 |
| 3 | 2 | 50/80 | 62.50% | 27/80 | 33.75% | 0.539 | 0.280 |

Ungated voting emits a verdict on **79/80 cases (98.75%)**. This is its forced decision rate, not evidence that those cases are safely covered. One observation failure remains unresolved. v27 tree acceptance rates are 18.75%, 17.5% and 31.25%; it uses the regular judge for the remaining cases.

## What happens to cases v27 rejects

| Bank | v27-deferred cases | Regular correct on these cases | Ungated correct on these cases |
|---:|---:|---:|---:|
| 1 | 65 | 44/65 (67.69%) | 30/65 (46.15%) |
| 2 | 66 | 41/66 (62.12%) | 26/66 (39.39%) |
| 3 | 55 | 35/55 (63.64%) | 13/55 (23.64%) |

The gate is preventing substantial harm on these cases. Relative to v27, ungated voting gains/losses are 8/22, 8/23 and 5/28, for net losses of 14, 15 and 23 correct decisions. Source-cluster bootstrap intervals for the accuracy differences are −28.75 to −6.25, −27.5 to −10, and −38.75 to −17.5 percentage points. These are descriptive intervals from sixteen source clusters.

On v27-accepted cases, ungated predictions are identical in banks 1 and 2. In bank 3, four accepted predictions change because all experts now vote, including ones the supported-expert selection did not trust for that case. Correct answers in that accepted subset fall 15→14. Most degradation still comes from forced decisions on deferred cases (35→13 correct).

## Ties and sensitivity

| Bank | Tied cases | Correct tie decisions | Unanimous cases |
|---:|---:|---:|---:|
| 1 | 10 | 4 | 3 |
| 2 | 9 | 1 | 16 |
| 3 | 46 | 11 | 33 |

The two-expert bank relies on the tie rule for 46/79 valid cases. This is a result for the predefined plurality/tie policy, not proof that every possible ungated policy must fail. No alternative tie rule was selected after observing these outcomes.

On the 77 cases with successful regular judgment and successful extraction, the regular judge scores 53/77. v27 scores 57/77, 50/77 and 50/77; ungated voting scores 42/77, 34/77 and 27/77. The same ordering holds without the three failed-request cases.

**Recommendation:** retain the coverage gate for these expert banks. If broader coverage is desired, improve applicability and judgment rules rather than forcing every expert to vote on every input. This ablation changes both abstention and supported-expert selection, which are both parts of the current coverage mechanism.

## Provenance and verification

- Same cached 80 outputs, sixteen source clusters, and disclosed older exposure for eight sources. No provider requests or new extraction.
- Same frozen v27 expert trees, existing regular responses, reference labels and feature projection.
- Independent audit walks every expert tree and verifies **720 expert outputs** and **240 bank predictions**, including unresolved outputs for the failed extraction. It reproduces the metrics and verifies that the parent API budget is unchanged.
- **26 focused tests pass**, including fifteen new voting/order/invalid-input tests and eleven existing pilot/recovery tests.
- A first draft’s audit found integer-versus-string JSON keys in the prediction-count summary. The report serialization was corrected; voting rules and all predictions stayed unchanged. The draft source snapshot is retained.

Final run: `logs/exps/261020-ungated-ablation-v30-r1`. The fixed protocol, per-expert traces, per-case votes, paired comparisons and verification are sealed there. Compact results/audit are in `docs/experiments/calitree_ungated_ablation_v30.json` and `docs/experiments/calitree_ungated_ablation_completion_audit.json`.

```bash
PYTHONPATH=. python run/calitree_ungated_ablation_v30.py \
  --parent-run logs/exps/261020-aurora-pilot80-v29-run1 \
  --output-dir logs/exps/NEW_UNGATED_RUN
PYTHONPATH=. python run/calitree_ungated_ablation_v30.py \
  --verify --output-dir logs/exps/NEW_UNGATED_RUN
```
