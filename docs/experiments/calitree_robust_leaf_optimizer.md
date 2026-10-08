# Robust local leaf optimizer: six-case pilot

## Implementation and offline verification

The v3 implementation adds conditional leaf programs, native node-level TextGrad backward feedback, typed structural transactions, label-blind semantic audits, greedy/Pareto selection, confidence gates and fresh final verification. See [usage and semantics](../calitree_robust_leaf_optimizer.md).

Before the live attempt, the full offline unit suite passed **1,186 tests, with 23 skipped**. The focused new suite passed 44 tests; combined new and legacy optimizer suites passed 98 tests. A standalone synthetic demonstration repaired a mismatching low-confidence check and passed five fresh final draws. These are software-contract checks, not evidence of real-model accuracy.

## Frozen experiment

- Six previously observed AURORA cases: first two IDs lexicographically in each reference class from `logs/exps/261006-optimizer-comparison-v1/manifest.json`.
- Four arms: flat–greedy, flat–Pareto, tree–greedy, tree–Pareto.
- GPT-6 Luna, official OpenAI endpoint, temperature zero, reasoning `none`.
- At most four nodes and depth four, two proposal rounds, native textual gradients, five confirmation and five final draws.
- Success requires an accepted semantic audit, at least 4/5 matching labels, 5/5 resolved labels, requirement/assessed-node consistency ≥0.8, and self-reported confidence ≥0.8 on every executed check.
- Global ceilings: 3,600 calls and 4,608,000 completion tokens, including failures. Final verification is reserved before search.

## Attempt 1: stopped before model execution

Directory: `logs/exps/261007-robust-leaf-v3`.

Preflight verified all six case identities, existing image hashes and distinct source-pixel groups. The process then encountered three consecutive DNS failures resolving `api.openai.com` inside the execution sandbox. Each was durably recorded as a compilation transport failure. The runner stopped according to the frozen protocol.

| Measurement | Result |
|---|---:|
| Reserved/attempted slots | 3 |
| Successful model responses | 0 |
| Charged or reserved completion tokens | 6,144 |
| Completed case-arm comparisons | 0 / 24 |
| Measured model accuracy or robustness | Unavailable |

The manifest, code snapshot, attempted jobs, per-slot errors, budget ledger and failure report remain saved. No failed slot was retried and no alternate model was substituted. Aggregate zero values in the machine report reflect missing/unresolved cases, not measured predictions.

A read-only DNS check outside the sandbox succeeded. The user subsequently authorized a network-enabled restart. Attempt 2 is recorded in `logs/exps/261007-robust-leaf-v3-network`; its manifest pins the stopped attempt and deducts three calls and 6,144 reserved tokens. Attempt 1 remains inconclusive and is not treated as model evidence.

## Attempt 2: network-enabled comparison

The network-enabled run **completed** all 24 case–arm optimizations and all 240 scheduled fresh final draws. Every returned model identity was `gpt-6-luna`. The original attempt remains unchanged.

### Fresh final results

Agreement is the mean of six per-case target-match fractions, each measured with five fresh draws. Unresolved draws count as nonmatches. Robust status additionally requires the semantic audit, full coverage, confidence and repeat-consistency gates.

| Arm | Seed agreement | Selected agreement | Seed → selected robust cases | Selected coverage | Selected label consistency |
|---|---:|---:|---:|---:|---:|
| Flat–greedy | 43.3% | 46.7% | 3 → 3 / 6 | 100% | 96.7% |
| Flat–Pareto | 36.7% | 66.7% | 2 → 4 / 6 | 100% | 100% |
| Tree–greedy | 43.3% | 80.0% | 2 → 4 / 6 | 96.7% | 96.7% |
| Tree–Pareto | 46.7% | 66.7% | 3 → 4 / 6 | 100% | 100% |

These arm-level observations do not establish a method ranking: there are only six previously observed local-fit cases, independent repeated calls vary, and transport failures affected some draws. Even unchanged seed/selected programs can have different measured agreement because their final slots are fresh.

### What the optimizer actually changed

**Every seed, candidate and selected program contained one fulfillment check and no conditional branches.** Across 73 candidate records, the proposer used 17 binding edits and 32 checker revisions; it proposed no node additions, splits, removals, or routing edits. Eight candidate audits rejected semantic changes. The selected artifact changed in one flat–greedy case and three cases in each other arm.

Consequently, this run demonstrates executable local criterion/binding repair, semantic rejection, confidence/repeat verification and durable accounting. It **does not test whether a decomposed tree is more robust than one prompt**. The flat/tree arm labels did not correspond to a difference in executed topology in this cohort. The larger nominal gain in tree–greedy cannot be attributed to conditional routing.

### Per-case selected agreement

| Instruction | Reference | Flat–greedy | Flat–Pareto | Tree–greedy | Tree–Pareto |
|---|---|---:|---:|---:|---:|
| Transform the black DVD into a white DVD | no | 0/5 | 5/5 | 5/5 | 5/5 |
| Make her close her jacket fully | yes | 0/5 | 0/5 | 0/5 | 0/5 |
| Change the image into pencil drawing | partial | 5/5 | 5/5 | 5/5 | 5/5 |
| Give the woman a helmet | yes | 5/5 | 5/5 | 4/5* | 5/5 |
| Move the mug to the right of the headphones | partial | 0/5 | 0/5 | 5/5 | 0/5 |
| Move the book behind the flower | no | 4/5 | 5/5 | 5/5 | 5/5 |

*The tree–greedy helmet result includes one transport failure and therefore fails the full-coverage robustness requirement. The jacket case remained a stable reference mismatch in every arm. Such agreement/disagreement does not by itself certify the atomic visual reasoning or determine whether the reference is correct.

### Usage and failures

| Scope | Search/preparation calls | Final calls | Completion tokens or conservative reservations |
|---|---:|---:|---:|
| Shared preparation | 12 | 0 | 1,767 |
| Flat–greedy | 140 | 60 | 21,763 |
| Flat–Pareto | 148 | 60 | 18,140 |
| Tree–greedy | 121 | 60 | 17,377 |
| Tree–Pareto | 127 | 60 | 15,119 |
| Prior stopped attempt | 3 | 0 | 6,144 |
| **Combined** | **551** | **240** | **80,310** |

The restarted run used 788 calls: 781 completed responses and seven retained TLS transport failures. Five failures occurred during search and two during final checking. The final failures affected the flat–Pareto pencil-drawing **seed** and the tree–greedy helmet **selected** program. There were no failed-slot retries, no model substitutions, and no three-consecutive-failure stop in the restarted run.

Including the prior attempt, the experiment charged **791 calls and 80,310 completion tokens/reservations**, within the original 3,600-call and 4,608,000-token ceilings. Successful responses used 1,517,184 input tokens. Costs here are token/call measurements, not a billed-dollar estimate. Final per-case check counts, token costs, confidence values, conditional-node statistics and failure reasons are saved in `results.json`, `analysis.json`, and the generated reports.

### Verification and reproduction

- Protocol audit passed: 788 durable jobs, 24 frozen selections and 240 scheduled final draws; model identities, label isolation, per-scope limits, output caps and final-only execution ordering verified.
- All final results were replayed from a temporary artifact copy with model engine creation forbidden. All 24 case–arm results and the budget matched exactly, with **zero additional model calls**. The original live artifacts were not modified by replay.
- Offline suite: **1,188 passed, 23 skipped**. Focused robust-leaf suite: 46 passed.
- No final outcome was used to repair or reselect a candidate. No commit or push was made.

```bash
# The completed runner resumes only unattempted slots; a complete replay makes no new calls.
.venv/bin/python -m run.calitree_robust_leaf_optimization --live --resume \
  --output-dir logs/exps/261007-robust-leaf-v3-network

# These commands are read-only with respect to models and make no API calls.
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-leaf-v3-network/verify.py
PYTHONPATH=. .venv/bin/python logs/exps/261007-robust-leaf-v3-network/analyze.py
```

Artifacts: `logs/exps/261007-robust-leaf-v3-network/{manifest.json,source_snapshot/,prepared/,frozen/,jobs/,observations.jsonl,budget.json,leaves.json,results.json,summary.json,report.md,analysis.json,assessment.md,replay_verification.json,run.log,llm-histories.log}`. The manifest pins the prior attempt and its budget hashes. The source snapshot and frozen programs preserve the exact experiment configuration.

A future test of the tree hypothesis should deliberately include multi-outcome instructions and verify that the compiled programs actually contain multiple separately executed decisions and meaningful gates. That would require a separately specified experiment; no extra cases or model calls were added here.
