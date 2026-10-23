# AURORA pilot: regular judge versus v27 and v28

**Completed within the approved request and token limits.** The semantic merges increased coverage in two banks but reduced accuracy in both. All seven newly accepted v28 outputs were incorrect against the frozen human labels.

## Accuracy and coverage

Primary scores include all 80 outputs, retaining transport failures as specified. Accuracy is the complete hybrid system, including regular-judge fallback. Accepted accuracy applies only to tree decisions.

| Arm | Correct / 80 | Overall accuracy | Macro-F1 | Tree coverage | Accuracy when tree accepts |
|---|---:|---:|---:|---:|---:|---:|
| regular | 53/80 | 66.25% | 0.535 | — | — |
| v27_split1 | 57/80 | 71.25% | 0.571 | 15/80 (18.8%) | 86.7% |
| v28_split1 | 56/80 | 70.00% | 0.559 | 16/80 (20.0%) | 81.2% |
| v27_split2 | 50/80 | 62.50% | 0.521 | 14/80 (17.5%) | 64.3% |
| v28_split2 | 50/80 | 62.50% | 0.521 | 14/80 (17.5%) | 64.3% |
| v27_split3 | 50/80 | 62.50% | 0.539 | 25/80 (31.2%) | 60.0% |
| v28_split3 | 47/80 | 58.75% | 0.487 | 31/80 (38.8%) | 48.4% |

v27 bank 1 gains four correct answers over the regular judge; v28 bank 1 gains three. Banks 2 and 3 do not improve on the regular judge. The three banks were frozen replications, not candidates selected using this pilot. The paired source-cluster interval for v27 bank 1’s +5-point gain is −1.25 to +11.25 percentage points; this small pilot does not establish a robust gain.

The labels are 60 No, 15 Partial and 5 Yes. An always-No baseline therefore scores 75% accuracy, above every tested arm, but only about 0.286 macro-F1. Report both measures: overall accuracy alone favors the majority class.

## What the semantic merges changed

| Bank | Additional accepted outputs | Correct among additional accepts | Wins versus regular | Losses versus regular |
|---|---:|---:|---:|---:|
| 1 | 1 | 0 | 0 | 1 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 6 | 0 | 0 | 3 |

All seven are distinct outputs from three source tasks. All received Yes from v28: six have human label No and one Partial. Four had correct regular answers that the new acceptance replaced; the other three were already wrong under the regular judge. There are no gains from the added coverage.

The requests concern changing a particular cylinder’s color, standing fully upright while looking at one’s hands, and adding banana-shaped candles. No label was adjudicated or changed after evaluation. Passing the unchanged full-bank veto and contributor check was insufficient to protect these newly widened Yes regions.

**Recommendation:** keep v28 experimental. Its extra coverage is harmful on this pilot. v27 bank 1 is a promising observation, but it should not be promoted by choosing the best bank after seeing these results. No gate or policy was changed in response to this evaluation.

## Exposure breakdown

Forty outputs come from eight sources with no recorded prior repository exposure; forty come from eight sources with disclosed older references. All sixteen are disjoint from the 244 recent-study exclusion groups and the 98 current training/gate-calibration source groups. Exposure groups have different task compositions, so their difference is not a causal estimate of prior-exposure effects.

| Arm | Previously unused sources: correct / 40 | Older referenced sources: correct / 40 |
|---|---:|---:|
| regular | 31/40 | 22/40 |
| v27_split1 | 33/40 | 24/40 |
| v28_split1 | 33/40 | 23/40 |
| v27_split2 | 28/40 | 22/40 |
| v28_split2 | 28/40 | 22/40 |
| v27_split3 | 27/40 | 23/40 |
| v28_split3 | 27/40 | 20/40 |

All seven additional v28 acceptances occur in the older-referenced subgroup, although those sources are excluded from the recent CaliTree study. v27 and v28 have identical results on the previously unused subgroup in this pilot.

## Failed requests and paired sensitivity

There were two regular-judge transport failures and one observation transport failure. The observation failure uses its saved regular response; failed regular responses remain unresolved unless a covered tree supplies a verdict. No request was retried and no case was replaced.

On the 77 cases with both successful regular judgment and successful extraction:

| Arm | Correct / 77 | Accuracy |
|---|---:|---:|
| regular | 53/77 | 68.83% |
| v27_split1 | 57/77 | 74.03% |
| v28_split1 | 56/77 | 72.73% |
| v27_split2 | 50/77 | 64.94% |
| v28_split2 | 50/77 | 64.94% |
| v27_split3 | 50/77 | 64.94% |
| v28_split3 | 47/77 | 61.04% |

The relative accuracy changes persist on this common-successful subset. The primary table retains the full planned denominator of 80.

## Execution, recovery and budget

The first collector attempt failed locally while constructing requests because the adapter rejects an explicit Luna reasoning argument. Three slots were reserved, but no HTTP request reached the provider. Those artifacts are preserved in the prepared directory. The corrected version omits that local argument; the unchanged serializer still emits reasoning_effort=none, temperature=0 and the same model. Its budget was reduced by the three attempts and 24,576 reserved tokens rather than resetting the approved allowance.

- API attempts: **255**; completed responses: **252**.
- Combined counted attempts, including local failures: **258/272**.
- Reported input tokens: **685,915**; completion tokens: **131,110**.
- Completion tokens plus conservative failed-slot reservations: **176,166/2,392,064**.
- Recorded usage priced at the reviewed Standard rates: **$0.1341**; charging all input at the cache-write rate gives **$0.1513**. These are usage-priced estimates, not an invoice; failed-request charges and provider cache accounting are not resolved by the normalized ledger.
- Stages: 16 compiler calls, 80 regular calls, 80 observation calls and 79 interpretation calls. No compiler repair was needed; one interpretation was skipped after an observation failure.

## Verification and artifacts

The completion audit checks every frozen request identity, payload, schema, prompt, media hash, model identity, stage count, response usage and aggregate allowance. It replays all six gates and reproduces the reports. The three pre-HTTP failures are separately verified. Eleven relevant collector/adapter tests pass. Source-cluster bootstrap comparisons use 16 clusters and do not treat the bank replicas as independent data.

Completed run: `logs/exps/261020-aurora-pilot80-v29-run1`. Initial local failure: `logs/exps/261020-aurora-pilot80-v29/ledger`.

Primary collection, request audit and replay are sealed in `completion_seal.json`. The derived paired comparison is linked through `analysis_seal.json`. Compact comparison and audit are copied to `docs/experiments/calitree_aurora_pilot_v29_results.json` and `docs/experiments/calitree_aurora_pilot_v29_completion_audit.json`.
